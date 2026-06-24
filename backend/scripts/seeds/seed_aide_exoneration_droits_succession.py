"""Insert Exonération Droits Succession/Donation aid into Supabase aides_v3 tables."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

aide = (
    supabase.table("aides_v3")
    .insert(
        {
            "nom": "Exonération des droits de succession et de donation pour les monuments historiques",
            "nom_court": "Exo. Droits Succession/Donation MH",
            "description": "Exemption complète des droits de succession et de donation pour les monuments classés ou inscrits, sous conditions de conservation et d'accès public.",
            "description_longue": "L'article 795 A du code général des impôts exonère de droits de mutation à titre gratuit les immeubles classés ou inscrits au titre des monuments historiques. Cette exonération s'applique aux donations, donations-partages et successions, sous condition de signature d'une convention avec l'État.",
            "categorie": "fiscalite",
            "type": "exoneration",
            "organisme": "État français - Ministère de la Culture et des Finances",
            "montant_max": None,
            "taux_max": 100,
            "montant_min": None,
            "plancher": None,
            "base_ttc": False,
            "commune_max_population": None,
            "cofinancement_requis": False,
            "architecte_requis": False,
            "conditions_eligibilite_detail": """- Classification : immeubles totalement classés ou inscrits au titre des monuments historiques
- Ou : immeubles dont les façades et couvertures sont protégées en totalité
- Ou : immeubles dont les principaux volumes intérieurs et leurs décors sont protégés
- Ou : parcs et jardins ordonnancés des édifices en cause
- Biens meubles : meubles constituant le complément historique de l'immeuble
- Convention obligatoire : convention à durée indéterminée signée entre les héritiers/donataires et les ministres de la Culture et des Finances
- Contenu de la convention :
  • Engagement de conservation et d'entretien des biens exonérés
  • Conditions de présentation du bien
  • Modalités d'accès du public :
    - 60 jours par an minimum (pour certains biens)
    - OU 80 jours par an minimum (pour autres biens)
- Durée : convention à durée indéterminée
- Non-respect : perte immédiate du bénéfice de l'exonération en cas de violation des obligations
- Exonération : 100 % des droits de mutation à titre gratuit""",
            "demarche_description": "1. Identifier les biens exonérables (immeuble + meubles historiques)\n2. Contacter les ministères de la Culture et des Finances\n3. Préparer une convention de conservation et d'accès public\n4. Signer la convention avec l'État\n5. Transmettre les biens en succession ou donation\n6. Déclarer l'exonération auprès du centre des finances publiques\n7. Respecter les obligations d'entretien et d'accès public",
            "documents_requis": [
                "decision_classement_ou_inscription",
                "convention_etat",
                "acte_succession_ou_donation",
                "plan_immeuble",
                "inventaire_meubles",
            ],
            "delai_instruction": "3 à 6 mois pour la convention",
            "date_ouverture": None,
            "date_limite": None,
            "permanent": True,
            "url_officielle": "https://bofip.impots.gouv.fr/bofip/2318-PGP.html/identifiant=BOI-ENR-DMTG-10-20-30-60-20200629",
            "formulaire_url": None,
            "tags": [
                "exoneration_fiscale",
                "monument_historique",
                "succession",
                "donation",
            ],
        }
    )
    .execute()
)

aide_id = aide.data[0]["id"]

# Critères structurés
supabase.table("aides_protections").insert(
    [
        {"aide_id": aide_id, "protection_code": "classe"},
        {"aide_id": aide_id, "protection_code": "inscrit"},
    ]
).execute()

supabase.table("aides_proprietaires").insert(
    [
        {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
        {"aide_id": aide_id, "proprietaire_code": "public_commune"},
        {"aide_id": aide_id, "proprietaire_code": "public_departement"},
        {"aide_id": aide_id, "proprietaire_code": "public_region"},
        {"aide_id": aide_id, "proprietaire_code": "association"},
    ]
).execute()

print(f"✓ Aide insérée : Exonération droits succession/donation MH ({aide_id})")
