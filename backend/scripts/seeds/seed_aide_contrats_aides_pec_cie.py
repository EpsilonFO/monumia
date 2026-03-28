"""
Seed: Contrats aidés — Parcours Emploi Compétences (PEC) et CUI-CIE.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_contrats_aides_pec_cie.py
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = supabase.table("aides_v2").insert({
    "nom": "Contrats aidés — Parcours Emploi Compétences (PEC) et CUI-CIE",
    "nom_court": "PEC / CIE",
    "description": "Contrats de travail subventionnés par l'État permettant aux communes, associations et entreprises du patrimoine d'embaucher des personnes éloignées de l'emploi pour des missions liées à l'entretien, la valorisation ou la restauration de monuments.",
    "description_longue": (
        "Les contrats aidés, dans le cadre des Parcours Emploi Compétences (PEC, secteur "
        "non-marchand) et des Contrats Uniques d'Insertion — Contrat Initiative Emploi (CUI-CIE, "
        "secteur marchand), permettent de financer partiellement l'embauche de personnes "
        "éloignées du marché du travail. Dans le domaine du patrimoine, ils sont utilisés par "
        "les communes pour l'entretien courant des monuments et édifices publics, par les "
        "associations de sauvegarde du patrimoine pour des missions de valorisation, de médiation "
        "ou d'entretien, et par les entreprises du BTP patrimoine via le CIE. Le PEC associe "
        "une aide financière à l'employeur (prise en charge d'une partie du SMIC) à un "
        "accompagnement et une formation obligatoire du salarié. Depuis mars 2025, l'aide PEC "
        "est de 30 % du SMIC horaire brut pour 20h/semaine. Le CIE concerne le secteur marchand "
        "et son taux de prise en charge varie selon les régions (fixé par arrêté préfectoral). "
        "La durée du contrat va de 6 mois à 24 mois maximum (renouvellements inclus)."
    ),
    "categorie": "etat_drac",
    "type": "subvention",
    "organisme": "France Travail / DREETS / Préfectures",
    "montant_max": None,
    "taux_max": 60,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": (
        "- Deux types de contrats :\n"
        "  • PEC (Parcours Emploi Compétences) : secteur non-marchand uniquement (communes, associations, établissements publics)\n"
        "  • CUI-CIE (Contrat Initiative Emploi) : secteur marchand (entreprises du BTP, artisans du patrimoine)\n"
        "- Le PEC est le dispositif principal depuis 2018 (les anciens CUI-CAE sont remplacés par les PEC)\n"
        "- Bénéficiaires du contrat : personnes éloignées du marché du travail, notamment :\n"
        "  • Demandeurs d'emploi de longue durée\n"
        "  • Chômeurs de plus de 57 ans\n"
        "  • Travailleurs handicapés (RQTH)\n"
        "  • Résidents des quartiers prioritaires (QPV)\n"
        "  • Bénéficiaires du RSA, ASS, AAH\n"
        "- Aide financière PEC (depuis mars 2025) : 30 % du SMIC horaire brut, pour 20h hebdomadaires\n"
        "  • Taux antérieur (avant mars 2025) : 40 à 60 % du SMIC selon le profil\n"
        "- Aide financière CIE : taux fixé par arrêté préfectoral régional, généralement 30 à 47 % du SMIC\n"
        "- Durée du contrat : CDD de 6 mois minimum (3 mois pour certains cas dérogatoires) à 24 mois maximum (renouvellements inclus)\n"
        "- Le contrat peut être en CDI ou CDD\n"
        "- Rémunération du salarié : au moins le SMIC horaire ou le minimum conventionnel\n"
        "- Obligations de l'employeur PEC :\n"
        "  • Mettre en place un accompagnement du salarié\n"
        "  • Permettre l'accès à la formation professionnelle\n"
        "  • Désigner un tuteur\n"
        "- La prescription du PEC est faite par France Travail (ex Pôle emploi), les missions locales ou Cap emploi\n"
        "- Le CIE est prescrit par France Travail\n"
        "- Dans le domaine du patrimoine, les missions éligibles incluent : entretien courant des monuments, petits travaux de maintenance, médiation culturelle, accueil du public, gestion de chantiers bénévoles, administration d'associations patrimoniales\n"
        "- Le PEC n'est PAS adapté pour des travaux de restauration lourde nécessitant des qualifications spécifiques\n"
        "- L'employeur doit démontrer que le poste permet une montée en compétences du salarié"
    ),
    "demarche_description": (
        "1. Identifier le besoin en personnel pour l'entretien ou la valorisation du patrimoine\n"
        "2. Contacter France Travail, la mission locale ou Cap emploi pour vérifier l'éligibilité au PEC ou au CIE\n"
        "3. Identifier un candidat éligible (demandeur d'emploi éloigné du marché du travail)\n"
        "4. Constituer le dossier de demande d'aide avec France Travail (description du poste, plan de formation, engagement d'accompagnement)\n"
        "5. Signature du contrat de travail (CDD ou CDI) et de la convention PEC/CIE tripartite\n"
        "6. Versement de l'aide par l'ASP (Agence de Services et de Paiement) sur toute la durée du contrat\n"
        "7. Mise en œuvre de la formation et de l'accompagnement du salarié"
    ),
    "documents_requis": [
        "Formulaire de demande de convention PEC ou CIE (via France Travail)",
        "Description du poste et des missions",
        "Plan de formation et d'accompagnement du salarié",
        "Engagement de tutorat",
        "Contrat de travail signé",
    ],
    "delai_instruction": "2 à 4 semaines",
    "permanent": True,
    "url_officielle": "https://travail-emploi.gouv.fr/emploi-et-insertion/parcours-emploi-competences/pec",
    "formulaire_url": None,
    "tags": [
        "PEC", "CIE", "contrats aidés", "emploi", "insertion",
        "patrimoine", "entretien", "valorisation", "France Travail",
    ],
}).execute()

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : tous niveaux (l'aide porte sur l'emploi, pas sur la protection)
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
    {"aide_id": aide_id, "protection_code": "non_protege"},
]).execute()
print("  ✓ Protections insérées")

# Propriétaires : PEC = secteur non-marchand, CIE = secteur marchand
supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "public_commune"},
    {"aide_id": aide_id, "proprietaire_code": "public_departement"},
    {"aide_id": aide_id, "proprietaire_code": "public_region"},
    {"aide_id": aide_id, "proprietaire_code": "public_etat"},
    {"aide_id": aide_id, "proprietaire_code": "association"},
]).execute()
print("  ✓ Propriétaires insérés")

# Travaux : entretien courant, valorisation (pas restauration lourde)
supabase.table("aides_travaux").insert([
    {"aide_id": aide_id, "travaux_code": "restauration_generale"},
    {"aide_id": aide_id, "travaux_code": "parcs_jardins"},
    {"aide_id": aide_id, "travaux_code": "mise_en_securite"},
    {"aide_id": aide_id, "travaux_code": "accessibilite"},
]).execute()
print("  ✓ Travaux insérés")

# Régions : nationale

# Segments : communes et BTP
supabase.table("aides_segments").insert([
    {"aide_id": aide_id, "segment_code": "commune"},
    {"aide_id": aide_id, "segment_code": "btp"},
]).execute()
print("  ✓ Segments insérés")

print(f"\n✅ Contrats aidés PEC/CIE inséré avec succès (id: {aide_id})")
