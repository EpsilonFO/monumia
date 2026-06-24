"""
Seed: Fonds de dotation — Patrimoine.

Run:
    cd backend && uv run python3 scripts/seeds/seed_aide_fonds_dotation.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── 1. Aide principale ──────────────────────────────────────────────

aide = (
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Fonds de dotation pour le patrimoine",
            "nom_court": "Fonds de dotation",
            "description": "Création d'un fonds de dotation dédié au patrimoine permettant de collecter des dons (particuliers et entreprises) ouvrant droit à des réductions fiscales pour financer la restauration d'un monument.",
            "description_longue": (
                "Le fonds de dotation, créé par la loi du 4 août 2008 (loi LME), est une personne morale "
                "de droit privé à but non lucratif qui reçoit et gère des biens et droits pour accomplir "
                "une mission d'intérêt général. Appliqué au patrimoine, il permet à un propriétaire de "
                "monument (privé, associatif ou public) de créer une structure dédiée à la collecte de dons "
                "pour financer des travaux de restauration. Les donateurs bénéficient de réductions fiscales : "
                "66 % de l'impôt sur le revenu (dans la limite de 20 % du revenu imposable) pour les "
                "particuliers, et 60 % de l'impôt sur les sociétés (dans la limite de 0,5 % du CA HT, "
                "ou 20 000 € pour les TPE depuis 2020) pour les entreprises. Le fonds de dotation est "
                "plus souple qu'une fondation reconnue d'utilité publique : il peut être créé par une seule "
                "personne avec un capital initial de seulement 15 000 €, sans autorisation administrative "
                "préalable. Il est soumis au contrôle du préfet et doit publier ses comptes annuels."
            ),
            "categorie": "mecenat",
            "type": "mecenat",
            "organisme": "Fonds de dotation (structure créée par le porteur de projet)",
            "montant_max": None,
            "taux_max": None,
            "montant_min": None,
            "plancher": 15000,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": (
                "- Cadre juridique : loi n° 2008-776 du 4 août 2008 (loi LME), articles 140 à 141\n"
                "- Dotation initiale minimale : 15 000 € (apportée de manière irrévocable)\n"
                "- Le fonds doit avoir une mission d'intérêt général : la restauration/préservation du patrimoine en est une\n"
                "- Créateur : toute personne physique ou morale (propriétaire privé, association, collectivité, entreprise)\n"
                "- Le fonds ne peut pas redistribuer de bénéfices ; il consacre ses ressources à sa mission\n"
                "- Gouvernance obligatoire : conseil d'administration d'au moins 3 membres\n"
                "- Obligation de nommer un commissaire aux comptes dès la création\n"
                "- Publication des comptes annuels au Journal officiel\n"
                "- Contrôle de la préfecture (droit de visite, demande de comptes)\n"
                "- Avantages fiscaux pour les donateurs :\n"
                "  • Particuliers (IR) : réduction de 66 % du don, dans la limite de 20 % du revenu imposable\n"
                "  • Entreprises (IS) : réduction de 60 % du don, dans la limite de 0,5 % du CA HT "
                "(ou 20 000 € pour les TPE/PME, plafond alternatif depuis 2020)\n"
                "  • Dons en nature et mécénat de compétences également éligibles\n"
                "- Le fonds peut recevoir des legs et donations (exonérés de droits de mutation)\n"
                "- Les biens immobiliers du fonds sont exonérés de taxe foncière\n"
                "- Le fonds peut lancer des campagnes de souscription publique\n"
                "- Il peut coexister avec d'autres sources de financement (subventions DRAC, région, etc.)\n"
                "- La dissolution du fonds impose le transfert de l'actif net à un autre organisme d'intérêt général\n"
                "- Pas de contrainte de protection MH : le monument peut être classé, inscrit ou non protégé\n"
                "- Pas de contrainte géographique : dispositif national\n"
                "- Le fonds peut financer tous types de travaux liés à sa mission patrimoniale"
            ),
            "demarche_description": (
                "1. Définir la mission d'intérêt général du fonds (restauration du monument X)\n"
                "2. Rédiger les statuts du fonds de dotation avec un conseil d'administration (min. 3 membres)\n"
                "3. Réunir la dotation initiale de 15 000 € minimum\n"
                "4. Déclarer le fonds en préfecture du siège social\n"
                "5. Publication au Journal officiel (délai : environ 2 semaines)\n"
                "6. Nommer un commissaire aux comptes\n"
                "7. Ouvrir un compte bancaire au nom du fonds\n"
                "8. Lancer les campagnes de collecte (dons, mécénat, souscription publique)\n"
                "9. Émettre des reçus fiscaux aux donateurs (Cerfa n° 11580*04)\n"
                "10. Publier les comptes annuels et rendre compte à la préfecture"
            ),
            "documents_requis": [
                "Statuts du fonds de dotation signés",
                "PV de l'assemblée constitutive",
                "Liste des membres du conseil d'administration",
                "Justificatif de la dotation initiale (15 000 €)",
                "Déclaration en préfecture (formulaire Cerfa)",
                "Nomination du commissaire aux comptes",
            ],
            "delai_instruction": "2 à 4 semaines (création du fonds)",
            "permanent": True,
            "url_officielle": "https://www.service-public.fr/associations/vosdroits/F31023",
            "formulaire_url": None,
            "tags": [
                "fonds de dotation",
                "mécénat",
                "dons",
                "fiscalité",
                "réduction IR",
                "réduction IS",
                "souscription",
                "intérêt général",
                "collecte",
                "patrimoine",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]
print(f"✓ Aide insérée : {aide_id}")

# ── 2. Critères structurés ──────────────────────────────────────────

# Protection : pas de contrainte (tout monument)

# Propriétaires : tous types (le fonds peut être créé par n'importe qui)

# Travaux : pas de contrainte

# Régions : aide nationale → pas de contrainte

# Segments : tous segments
# (pas de contrainte → pas d'insertion)

# État de conservation : pas de contrainte

print(f"\n✅ Fonds de dotation inséré avec succès (id: {aide_id})")
