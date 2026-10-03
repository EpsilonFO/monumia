# MCP en lecture seule sur les bases prod et beta

Deux serveurs MCP, `monumia-prod` et `monumia-beta`, pour interroger les bases Supabase depuis Claude Code sans pouvoir y écrire.

Trois barrières, dans l'ordre de ce qui protège vraiment :

1. **Le rôle Postgres `mcp_lecture`** ([role-lecture.sql](role-lecture.sql)) : `SELECT` sur le schéma `public` et sur la vue `lecture.auth_users`, aucun droit d'écriture nulle part. C'est lui la frontière : même une requête qui contourne le serveur MCP se heurte à `permission denied`.
2. **Le serveur `postgres-mcp` en `--access-mode=restricted`** : il n'accepte que des lectures et les exécute dans une transaction READ ONLY (timeout de 30 s, en plus des 15 s du rôle).
3. **Le secret dans le trousseau macOS** : [lancer.sh](lancer.sh) le lit au démarrage, et refuse de partir si la chaîne ne se connecte pas en `mcp_lecture`.

`auth.users` n'est lisible qu'à travers `lecture.auth_users` : email, dates d'inscription, de confirmation et de connexion, fournisseur OAuth. Le hash du mot de passe et les jetons n'y figurent pas. Le schéma `lecture` n'est pas exposé à PostgREST et reste fermé à `anon`/`authenticated`.

## Mise en place (une fois par environnement)

Pour la prod, puis la beta, en remplaçant `prod` par `beta` :

1. **Créer le rôle.** Dans Supabase Studio > SQL Editor, coller [role-lecture.sql](role-lecture.sql) et l'exécuter, puis poser un mot de passe (un différent par environnement) :

   ```sql
   alter role mcp_lecture password '<sortie de : openssl rand -hex 32>';
   ```

2. **Ranger la chaîne dans le trousseau.** Dans Studio > Connect, prendre la chaîne du **Session pooler** (la connexion directe est en IPv6 seulement) et y remplacer `postgres.<project_ref>` par `mcp_lecture.<project_ref>` :

   ```bash
   security add-generic-password -U -s monumia-mcp-prod -a mcp_lecture \
     -w 'postgresql://mcp_lecture.<project_ref>:<mot de passe>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require'
   ```

3. **Vérifier.** Toutes les lignes doivent dire `OK`, aucune `ECHEC` :

   ```bash
   psql "$(security find-generic-password -s monumia-mcp-prod -w)" -f scripts/mcp/verifier-lecture.sql
   ```

   Relire aussi la liste des fonctions `SECURITY DEFINER` affichée en fin de sortie : celles des extensions Supabase (`graphql`…) sont attendues, une fonction de `public` qui écrit ne l'est pas.

4. **Déclarer le serveur à Claude Code**, en portée locale (ce projet, cette machine, rien de commité) :

   ```bash
   claude mcp add monumia-prod --scope local -- "$PWD/scripts/mcp/lancer.sh" prod
   ```

   `/mcp` dans une session doit ensuite le montrer connecté.

## Exploitation

- Changer le mot de passe : `alter role mcp_lecture password '…'` dans Studio, puis `security add-generic-password -U …` avec la nouvelle chaîne.
- Couper l'accès sur-le-champ : `alter role mcp_lecture nologin;` (le script le rouvre s'il est rejoué).
- Les tables des migrations futures sont lisibles sans rien rejouer (`alter default privileges`). Rejouer [role-lecture.sql](role-lecture.sql) ne sert que si une table a été créée par un autre rôle que `postgres`, ou pour ajouter une colonne à la vue.
- Le rôle est limité à 3 connexions simultanées et à 15 s par requête : une analyse lourde se fait sur une copie, pas sur la prod.
