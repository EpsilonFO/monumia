#!/usr/bin/env python3
"""Réaligne supabase/seed.sql sur le schéma courant.

- Supprime les INSERT vers des tables disparues.
- Retire des colonnes (liste + valeurs positionnelles) sur monuments / aides_v2.

Parsing SQL « string-aware » (quotes simples, '' échappé ; pas de backslash ni
dollar-quoting dans ce dump, vérifié au préalable).
"""
import sys

SEED = "supabase/seed.sql"

# INSERT à supprimer entièrement (schema, table).
# - tables consolidées/supprimées par les migrations
# - storage.buckets : le bucket `documents` est désormais créé par la migration
#   20260421000000_ensure_documents_bucket (on conflict do nothing) -> doublon.
DROP_INSERTS = [
    ("public", "aides_departements"), ("public", "aides_etats_conservation"),
    ("public", "aides_proprietaires"), ("public", "aides_protections"),
    ("public", "aides_regions"), ("public", "aides_segments"),
    ("public", "aides_travaux"), ("public", "ref_segments"),
    ("storage", "buckets"),
]
DROP_COLUMNS = {
    "monuments": {
        "denomination", "affectataire", "periode_construction", "superficie",
        "materiaux", "type_couverture", "nombre_niveaux", "urgence_travaux",
        "diagnostic_realise", "derniers_travaux", "description_etat",
    },
    "aides_v2": {"tags"},
}

# Valeurs périmées -> valeurs autorisées par les contraintes CHECK courantes.
# (aides_v2_categorie_check ajoutée par 20260515093000_constrain_aides_v2_categorie_type)
VALUE_REMAP = {
    "'fondation_patrimoine'": "'fondation'",  # categorie : 1 occurrence unique
}

# Mot de passe de dev commun pour TOUS les comptes du seed (local uniquement :
# seed.sql est gitignoré). Les hashs d'origine viennent d'un dump de prod et sont
# inconnus -> on les remplace par un mot de passe connu, durable au `db reset`.
DEV_PASSWORD = "Monumia2026!"
DEV_PASSWORD_SQL = (
    "\n-- [dev local] mot de passe connu pour tous les comptes seedés\n"
    f"update auth.users set encrypted_password = extensions.crypt("
    f"'{DEV_PASSWORD}', extensions.gen_salt('bf'));\n"
)


def find_stmt_end(text, start):
    """Index du ';' qui termine l'instruction commençant à `start`."""
    i, n, in_str, depth = start, len(text), False, 0
    while i < n:
        c = text[i]
        if in_str:
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_str = False
            i += 1
        else:
            if c == "'":
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif c == ";" and depth == 0:
                return i
            i += 1
    raise ValueError("terminateur ';' introuvable")


def split_top_level(s):
    """Découpe une liste séparée par des virgules de niveau 0 (string-aware)."""
    vals, cur, in_str, depth, i, n = [], [], False, 0, 0, len(s)
    while i < n:
        c = s[i]
        if in_str:
            cur.append(c)
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    cur.append(s[i + 1])
                    i += 2
                    continue
                in_str = False
            i += 1
        else:
            if c == "'":
                in_str = True
                cur.append(c)
            elif c == "(":
                depth += 1
                cur.append(c)
            elif c == ")":
                depth -= 1
                cur.append(c)
            elif c == "," and depth == 0:
                vals.append("".join(cur).strip())
                cur = []
            else:
                cur.append(c)
            i += 1
    vals.append("".join(cur).strip())
    return vals


def parse_tuples(body):
    """Extrait le contenu interne de chaque tuple (...) de niveau 0."""
    tuples, i, n, in_str = [], 0, len(body), False
    while i < n:
        if not in_str and body[i] == "(":
            depth, j, buf = 1, i + 1, []
            while j < n:
                cj = body[j]
                if in_str:
                    buf.append(cj)
                    if cj == "'":
                        if j + 1 < n and body[j + 1] == "'":
                            buf.append(body[j + 1])
                            j += 2
                            continue
                        in_str = False
                    j += 1
                else:
                    if cj == "'":
                        in_str = True
                        buf.append(cj)
                    elif cj == "(":
                        depth += 1
                        buf.append(cj)
                    elif cj == ")":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                        buf.append(cj)
                    else:
                        buf.append(cj)
                    j += 1
            tuples.append("".join(buf))
            i = j
        else:
            i += 1
    return tuples


def rewrite_columns(text, table, drop):
    marker = f'INSERT INTO "public"."{table}" ('
    start = text.index(marker)
    end = find_stmt_end(text, start)
    stmt = text[start:end]  # sans le ';'

    paren_open = stmt.index("(")
    hdr_close = stmt.index(") VALUES")
    cols = split_top_level(stmt[paren_open + 1:hdr_close])
    names = [c.strip().strip('"').lower() for c in cols]
    keep = [k for k, name in enumerate(names) if name not in drop]
    removed = [name for name in names if name in drop]
    if set(removed) != drop:
        raise SystemExit(f"{table}: colonnes attendues {drop}, retirées {set(removed)}")

    new_cols = [cols[k] for k in keep]
    new_header = stmt[:paren_open + 1] + ", ".join(new_cols) + ") VALUES"

    body = stmt[hdr_close + len(") VALUES"):]
    tuples = parse_tuples(body)
    new_tuples = []
    for t in tuples:
        vals = split_top_level(t)
        if len(vals) != len(names):
            raise SystemExit(f"{table}: tuple à {len(vals)} valeurs, attendu {len(names)}")
        new_tuples.append("(" + ", ".join(vals[k] for k in keep) + ")")

    new_stmt = new_header + "\n\t" + ",\n\t".join(new_tuples) + ";"
    print(f"  {table}: {len(tuples)} lignes, {len(names)}→{len(new_cols)} colonnes (retiré {sorted(removed)})")
    return text[:start] + new_stmt + text[end + 1:]


def delete_insert(text, schema, table):
    marker = f'INSERT INTO "{schema}"."{table}" ('
    if marker not in text:
        print(f"  {schema}.{table}: déjà absent")
        return text
    start = text.index(marker)
    line_start = text.rfind("\n", 0, start) + 1
    end = find_stmt_end(text, start)
    after = end + 1
    while after < len(text) and text[after] in "\r\n":
        after += 1
    print(f"  {schema}.{table}: bloc INSERT supprimé")
    return text[:line_start] + text[after:]


def main():
    text = open(SEED, encoding="utf-8").read()
    print("Suppression des INSERT obsolètes :")
    for schema, t in DROP_INSERTS:
        text = delete_insert(text, schema, t)
    print("Réécriture des colonnes :")
    for table, drop in DROP_COLUMNS.items():
        text = rewrite_columns(text, table, drop)
    print("Remappage de valeurs hors-contrainte :")
    for old, new in VALUE_REMAP.items():
        n = text.count(old)
        text = text.replace(old, new)
        print(f"  {old} -> {new} ({n} occurrence(s))")
    text = text.rstrip() + "\n" + DEV_PASSWORD_SQL
    print(f"Mot de passe de dev appliqué à tous les comptes : {DEV_PASSWORD}")
    out = sys.argv[1] if len(sys.argv) > 1 else SEED
    open(out, "w", encoding="utf-8").write(text)
    print(f"Écrit -> {out}")


if __name__ == "__main__":
    main()
