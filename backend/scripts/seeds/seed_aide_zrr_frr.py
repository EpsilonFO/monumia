"""
Seed: ZRR / France Ruralités Revitalisation (FRR) — Exonérations fiscales en zone rurale.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_zrr_frr.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "France Ruralités Revitalisation (ZFRR / ZFRR+) — Exonérations fiscales en zone rurale",
    "nom_court": "ZRR / FRR",
    "description": "Exonérations fiscales (impôt sur les bénéfices, taxe foncière, CFE) pour les entreprises et activités créées ou reprises en zones France Ruralités Revitalisation, incluant les exploitations de monuments historiques.",
    "description_longue": (
        "Les zones France Ruralités Revitalisation (ZFRR) ont remplacé les anciennes ZRR "
        "(Zones de Revitalisation Rurale) à compter du 1er juillet 2024. Un niveau renforcé "
        "ZFRR+ concerne les territoires les plus fragiles depuis le 1er janvier 2025. "
        "Les entreprises créées ou reprises dans ces zones bénéficient d'exonérations "
        "significatives : exonération totale d'impôt sur les bénéfices pendant 5 ans "
        "(puis dégressif sur 3 ans), exonération de CFE (cotisation foncière des entreprises) "
        "et de taxe foncière sur les propriétés bâties (TFPB) sur délibération de la commune. "
        "Ces exonérations sont plafonnées à 300 000 € sur 3 ans glissants (règle de minimis UE). "
        "Pour les monuments historiques exploités en zone ZFRR/ZFRR+ (gîtes, chambres d'hôtes, "
        "visites, événementiel), ces exonérations peuvent considérablement réduire la charge "
        "fiscale pendant la phase de lancement de l'activité."
    ),
    "categorie": "fiscalite",
    "type": "exoneration",
    "organisme": "Direction Générale des Finances Publiques (DGFiP) / Communes",
    "montant_max": 300000,
    "taux_max": 100,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": 30000,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- La commune d'implantation doit être classée en zone ZFRR ou ZFRR+. "
        "Les ZFRR concernent les communes de moins de 30 000 habitants répondant "
        "à des critères de densité et de revenu. Les ZFRR+ sont les communes les plus "
        "fragiles (indice synthétique sur 10 ans : revenus, population, emploi).\n"
        "- ZFRR : création ou reprise d'entreprise entre le 1er juillet 2024 et le 31 décembre 2029.\n"
        "- ZFRR+ : création ou reprise entre le 1er janvier 2025 et le 31 décembre 2029.\n"
        "\n"
        "EXONÉRATION D'IMPÔT SUR LES BÉNÉFICES :\n"
        "- Exonération totale pendant 5 ans, puis : 75 % (année 6), 50 % (année 7), 25 % (année 8).\n"
        "- ZFRR : l'entreprise doit être au régime réel d'imposition (micro-fiscal exclu).\n"
        "- ZFRR+ : tous les régimes fiscaux éligibles, y compris micro-entreprise.\n"
        "- Plafond de minimis UE : 300 000 € sur 3 ans glissants.\n"
        "\n"
        "EXONÉRATION DE CFE (Cotisation Foncière des Entreprises) :\n"
        "- Même durée et dégressivité que l'impôt sur les bénéfices.\n"
        "- Nécessite une délibération de la commune ou EPCI avant le 1er octobre N pour N+1.\n"
        "\n"
        "EXONÉRATION DE TAXE FONCIÈRE (TFPB) :\n"
        "- Mêmes proportions et durée que la CFE.\n"
        "- Nécessite une délibération communale.\n"
        "- Déclaration au service foncier avant le 1er janvier de l'année d'exonération.\n"
        "- ZFRR+ : délai étendu au 31 décembre 2025 pour les impositions 2026.\n"
        "\n"
        "CONDITIONS D'EFFECTIF :\n"
        "- ZFRR : moins de 11 salariés.\n"
        "- ZFRR+ création : micro-entreprises (<10) ou PME (<250).\n"
        "- ZFRR+ reprise : moins de 11 salariés.\n"
        "\n"
        "CONTRAINTES TERRITORIALES :\n"
        "- ZFRR : implantation principale en zone (max 25 % du CA réalisé hors zone).\n"
        "- ZFRR+ : activité non sédentaire tolérée jusqu'à 25 % du CA hors zone "
        "(exonération proportionnelle).\n"
        "\n"
        "EXCLUSIONS :\n"
        "- Activités agricoles et civiles exclues.\n"
        "- Reprises dans le cadre familial exclues (sauf descendant 1re génération).\n"
        "- Non cumulable avec QPV, JEI, ZFU, BER, BUD.\n"
        "- Choix irrévocable dans les 6 mois suivant la création.\n"
        "\n"
        "APPLICATION AU PATRIMOINE :\n"
        "- Les monuments historiques exploités commercialement en ZFRR/ZFRR+ "
        "(gîtes, chambres d'hôtes, visites payantes, location événementielle) "
        "peuvent bénéficier de ces exonérations via la structure d'exploitation.\n"
        "- L'exonération de TFPB est particulièrement intéressante pour les "
        "propriétaires de monuments avec forte valeur locative cadastrale."
    ),
    "demarche_description": (
        "1. Vérifier que la commune est classée en ZFRR ou ZFRR+ sur le site du ministère "
        "(ecologie.gouv.fr/dossiers/france-ruralites)\n"
        "2. Créer ou reprendre l'entreprise dans la commune éligible\n"
        "3. Pour l'exonération d'impôt sur les bénéfices : opter dans les 6 mois suivant "
        "la création lors de la déclaration de résultats\n"
        "4. Pour la CFE : vérifier auprès de la commune qu'elle a délibéré en faveur "
        "de l'exonération\n"
        "5. Pour la TFPB : déclarer les locaux au service foncier avant le 1er janvier\n"
        "6. Joindre l'attestation de minimis à la déclaration fiscale"
    ),
    "documents_requis": [
        "Kbis ou extrait d'immatriculation",
        "Justificatif d'implantation en zone ZFRR/ZFRR+",
        "Déclaration de résultats avec option pour l'exonération",
        "Attestation de minimis (montant des aides reçues sur 3 ans)",
        "Déclaration foncière pour l'exonération de TFPB",
    ],
    "delai_instruction": "Automatique (sur déclaration fiscale)",
    "permanent": False,
    "url_officielle": "https://entreprendre.service-public.gouv.fr/vosdroits/F31139",
    "formulaire_url": None,
    "tags": [
        "ZRR", "ZFRR", "FRR", "France Ruralités Revitalisation",
        "exonération fiscale", "impôt bénéfices", "taxe foncière",
        "CFE", "zone rurale", "création entreprise",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protections : pas de contrainte (MH ou non, mais MH exploité commercialement)

# Propriétaires : entreprises et structures d'exploitation
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
    {"aide_id": aide_id, "proprietaire_code": "prive_sci"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires éligibles insérés")

# Travaux : pas directement une aide aux travaux mais liée à l'exploitation
# → pas de contrainte sur les travaux (on n'insère rien)

# Régions : aide nationale mais uniquement en communes ZFRR → pas de contrainte régionale
# (le matching LLM gère via conditions_eligibilite_detail)

# Segments : privé uniquement
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "prive"},
]).execute()
print("  ✓ Segments insérés")

print(f"\n✅ ZRR / France Ruralités Revitalisation inséré avec succès (id: {aide_id})")
