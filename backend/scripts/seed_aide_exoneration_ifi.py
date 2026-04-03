"""Insert Exonération IFI aid into Supabase aides_v2 tables."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

aide = supabase.table("aides_v2").insert({
    "nom": "Exonération partielle de l'IFI pour les monuments historiques",
    "nom_court": "Exo. IFI MH",
    "description": "Exemption partielle de l'Impôt sur la Fortune Immobilière (IFI) pour les monuments classés ou inscrits, à hauteur de 75 % de la valeur du bien.",
    "description_longue": "Les propriétaires de monuments historiques classés ou inscrits bénéficient d'une exonération partielle de l'IFI portant sur 75 % de la valeur imposable du bien, sous réserve de respecter les conditions de conservation et de maintenance.",
    "categorie": "fiscalite",
    "type": "exoneration",
    "organisme": "État français - Direction Générale des Finances Publiques",
    "montant_max": None,
    "taux_max": 75,
    "montant_min": None,
    "plancher": None,
    "base_ttc": False,
    "commune_max_population": None,
    "cofinancement_requis": False,
    "architecte_requis": False,
    "conditions_eligibilite_detail": """- Classification : immeubles classés au titre des monuments historiques ou inscrits à l'inventaire supplémentaire des monuments historiques (ISMH)
- Durée minimale de conservation : 15 ans
- Taux d'exonération : 75 % de la valeur imposable
- Calcul de l'IFI : seuls 25 % de la valeur de l'immeuble entrent dans le patrimoine taxable à l'IFI
- Conditions supplémentaires :
  • Bien destiné à l'usage professionnel ou commercial
  • OU immeuble ouvert à la visite publique payante
  • Ouverture minimum : environ 100 jours par an (variable selon accords avec DRAC)
- Obligation d'entretien : maintien du bien en bon état
- Perte d'exonération : en cas de non-respect des conditions ou de vente du bien""",
    "demarche_description": "1. Vérifier le classement ou l'inscription de l'immeuble\n2. Évaluer la valeur du patrimoine à inclure dans le calcul de l'IFI\n3. Calculer l'IFI avec la réduction de 75 %\n4. Déclarer le bien au formulaire CERFA d'IFI\n5. Joindre les justificatifs de classement/inscription\n6. Respecter les obligations d'entretien et d'accès public",
    "documents_requis": ["decision_classement_ou_inscription", "evaluation_immobiliere", "declaration_ifi", "justificatif_entretien"],
    "delai_instruction": "Variable selon direction des finances",
    "date_ouverture": None,
    "date_limite": None,
    "permanent": True,
    "url_officielle": "https://bofip.impots.gouv.fr/bofip/11552-PGP.html/identifiant=BOI-RES-PAT-000020-20210309",
    "formulaire_url": None,
    "tags": ["exoneration_fiscale", "monument_historique", "ifi"]
}).execute()

aide_id = aide.data[0]["id"]

# Critères structurés
supabase.table("aides_protections").insert([
    {"aide_id": aide_id, "protection_code": "classe"},
    {"aide_id": aide_id, "protection_code": "inscrit"},
]).execute()

supabase.table("aides_proprietaires").insert([
    {"aide_id": aide_id, "proprietaire_code": "prive_personne_physique"},
]).execute()

print(f"✓ Aide insérée : Exonération IFI MH ({aide_id})")
