"""
Port of frontend/src/services/dossier.service.ts — createFromAide logic.
Builds the initial Dossier structure from an aide + monument + user.
"""

import uuid
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Checklist templates (port of mock-checklist-templates.ts)
# ---------------------------------------------------------------------------

CHECKLIST_TEMPLATES: dict[str, list[dict]] = {
    "drac_subvention": [
        {
            "label": "Formulaire CERFA de demande de subvention",
            "description": "Formulaire officiel de demande de subvention.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 1,
        },
        {
            "label": "Extrait cadastral",
            "description": "Extrait du plan cadastral identifiant la parcelle.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 2,
        },
        {
            "label": "Titre de propriété ou délibération du conseil municipal",
            "description": "Pour les communes : délibération autorisant les travaux.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 3,
        },
        {
            "label": "Programme détaillé des travaux",
            "description": "Description technique des travaux, établie par un architecte du patrimoine.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 4,
        },
        {
            "label": "Devis détaillé des entreprises",
            "description": "Devis détaillé (HT pour les communes) des entreprises pressenties.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 5,
        },
        {
            "label": "Plan de financement prévisionnel",
            "description": "Tableau récapitulatif de toutes les sources de financement.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 6,
        },
        {
            "label": "Photos de l'état actuel",
            "description": "Reportage photographique montrant les dégradations.",
            "obligatoire": True,
            "categorie": "photographique",
            "ordre": 7,
        },
        {
            "label": "Plan de situation",
            "description": "Plan de localisation du monument dans la commune.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 8,
        },
        {
            "label": "Avis de l'ABF",
            "description": "Avis de l'Architecte des Bâtiments de France.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 9,
        },
        {
            "label": "Note historique",
            "description": "Courte notice historique du monument.",
            "obligatoire": False,
            "categorie": "technique",
            "ordre": 10,
        },
    ],
    "fip": [
        {
            "label": "Formulaire de demande FIP",
            "description": "Formulaire spécifique au Fonds Incitatif et Partenarial.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 1,
        },
        {
            "label": "Délibération du conseil municipal",
            "description": "Délibération autorisant les travaux et le plan de financement.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 2,
        },
        {
            "label": "Justificatif de population",
            "description": "Attestation INSEE confirmant < 10 000 habitants.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 3,
        },
        {
            "label": "Programme de travaux",
            "description": "Description technique des travaux.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 4,
        },
        {
            "label": "Devis détaillé HT",
            "description": "Devis détaillé hors taxes des travaux.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 5,
        },
        {
            "label": "Plan de financement avec co-financement régional",
            "description": "Le FIP exige une contrepartie régionale d'au moins 15 %.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 6,
        },
        {
            "label": "Photos état actuel",
            "description": "Documentation photographique du monument.",
            "obligatoire": True,
            "categorie": "photographique",
            "ordre": 7,
        },
        {
            "label": "Extrait cadastral",
            "description": "Plan cadastral de la parcelle.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 8,
        },
    ],
    "fondation_label": [
        {
            "label": "Formulaire de demande de label",
            "description": "Formulaire disponible sur le site de la Fondation du Patrimoine.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 1,
        },
        {
            "label": "Titre de propriété",
            "description": "Document prouvant la propriété du bien.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 2,
        },
        {
            "label": "Photos du bien",
            "description": "Photographies de l'extérieur montrant l'intérêt patrimonial.",
            "obligatoire": True,
            "categorie": "photographique",
            "ordre": 3,
        },
        {
            "label": "Description des travaux envisagés",
            "description": "Description des travaux de restauration prévus.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 4,
        },
        {
            "label": "Devis estimatif",
            "description": "Estimation du coût des travaux (TTC pour les particuliers).",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 5,
        },
        {
            "label": "Avis de l'ABF",
            "description": "Avis favorable de l'Architecte des Bâtiments de France.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 6,
        },
    ],
    "region_subvention": [
        {
            "label": "Formulaire de demande régionale",
            "description": "Formulaire spécifique de la Région.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 1,
        },
        {
            "label": "Pièce d'identité ou délibération",
            "description": "Pour les communes : délibération du conseil municipal.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 2,
        },
        {
            "label": "Extrait cadastral",
            "description": "Plan cadastral de la parcelle.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 3,
        },
        {
            "label": "Programme de travaux",
            "description": "Description détaillée des travaux.",
            "obligatoire": True,
            "categorie": "technique",
            "ordre": 4,
        },
        {
            "label": "Devis détaillé",
            "description": "Devis des entreprises pour les travaux.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 5,
        },
        {
            "label": "Plan de financement",
            "description": "Tableau des financements.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 6,
        },
        {
            "label": "Photos état actuel",
            "description": "Documentation photographique.",
            "obligatoire": True,
            "categorie": "photographique",
            "ordre": 7,
        },
        {
            "label": "RIB",
            "description": "Relevé d'identité bancaire.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 8,
        },
        {
            "label": "Attestation URSSAF",
            "description": "Attestation de régularité de moins de 6 mois.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 9,
        },
    ],
    "departement_subvention": [
        {
            "label": "Formulaire de demande départementale",
            "description": "Formulaire du Conseil Départemental.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 1,
        },
        {
            "label": "Titre de propriété ou délibération",
            "description": "Justificatif de propriété du monument.",
            "obligatoire": True,
            "categorie": "administratif",
            "ordre": 2,
        },
        {
            "label": "Devis des travaux",
            "description": "Devis des travaux envisagés.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 3,
        },
        {
            "label": "Photos de l'état actuel",
            "description": "Documentation photographique.",
            "obligatoire": True,
            "categorie": "photographique",
            "ordre": 4,
        },
        {
            "label": "Plan de financement",
            "description": "Tableau des financements prévus.",
            "obligatoire": True,
            "categorie": "financier",
            "ordre": 5,
        },
    ],
}


def _get_template_key(aide: dict) -> str | None:
    categorie = aide.get("categorie") or aide.get("categorie")
    aide_type = aide.get("type")
    if categorie == "etat_drac" and aide_type == "subvention":
        # FIP has its own template — detect by name (fragile but mirrors frontend logic)
        nom = (aide.get("nom_court") or aide.get("nomCourt") or "").lower()
        if "fip" in nom:
            return "fip"
        return "drac_subvention"
    if categorie == "fondation_patrimoine" and aide_type == "label":
        return "fondation_label"
    if categorie == "region":
        return "region_subvention"
    if categorie == "departement":
        return "departement_subvention"
    return None


def create_dossier_from_aide(
    aide: dict,
    monument: dict,
    user: dict,
    travaux_prevus: list[str],
) -> dict:
    # Use documents_requis from the aide (stored in aides_v2 as jsonb array of strings)
    documents_requis: list = aide.get("documents_requis") or aide.get("documentsRequis") or []

    checklist = []
    if documents_requis:
        for i, doc_name in enumerate(documents_requis):
            checklist.append(
                {
                    "id": str(uuid.uuid4()),
                    "label": doc_name,
                    "description": "",
                    "obligatoire": True,
                    "categorie": "document",
                    "ordre": i + 1,
                    "statut": "manquant",
                }
            )
    else:
        # Fallback to hardcoded templates if aide has no documents_requis
        template_key = _get_template_key(aide)
        template = CHECKLIST_TEMPLATES.get(template_key) if template_key else None
        if template:
            for item in template:
                checklist.append(
                    {
                        **item,
                        "id": str(uuid.uuid4()),
                        "statut": "manquant",
                    }
                )

    monument_nom = monument.get("nom") or ""
    monument_commune = monument.get("commune") or ""
    monument_protection = monument.get("protection") or ""
    aide_nom_court = aide.get("nom_court") or aide.get("nomCourt") or ""

    sections = [
        {
            "id": str(uuid.uuid4()),
            "titre": "Description du monument",
            "type": "texte_libre",
            "contenu": monument.get("description_generale")
            or monument.get("descriptionGenerale")
            or "",
            "champsAutoremplis": [
                {
                    "champ": "Dénomination",
                    "valeur": monument.get("denomination") or "",
                    "source": "monument",
                },
                {"champ": "Commune", "valeur": monument_commune, "source": "monument"},
                {
                    "champ": "Protection",
                    "valeur": monument_protection,
                    "source": "monument",
                },
            ],
            "ordre": 1,
        },
        {
            "id": str(uuid.uuid4()),
            "titre": "Description des travaux envisagés",
            "type": "texte_libre",
            "contenu": monument.get("description_etat") or monument.get("descriptionEtat") or "",
            "ordre": 2,
        },
        {
            "id": str(uuid.uuid4()),
            "titre": "Justification",
            "type": "texte_libre",
            "contenu": "",
            "ordre": 3,
        },
    ]

    echeances = []
    date_limite = aide.get("date_limite") or aide.get("dateLimite")
    if date_limite:
        echeances.append(
            {
                "id": str(uuid.uuid4()),
                "label": "Date limite de dépôt",
                "date": date_limite,
                "type": "limite",
                "accomplie": False,
            }
        )

    now = datetime.now(UTC).isoformat()
    travaux_label = travaux_prevus[0] if travaux_prevus else "Travaux"

    return {
        "id": str(uuid.uuid4()),
        "monument_id": monument["id"],
        "aide_id": aide["id"],
        "titre": f"{aide_nom_court} — {monument_nom} — {travaux_label}",
        "description": f"Demande {aide_nom_court} pour {monument_nom}",
        "etape_actuelle": 1,
        "statut": "brouillon",
        "progression_pourcentage": 0,
        "travaux_prevus": travaux_prevus,
        "checklist": checklist,
        "sections": sections,
        "echeances": echeances,
        "collaborateurs": [],
        "date_creation": now,
        "date_derniere_modification": now,
    }
