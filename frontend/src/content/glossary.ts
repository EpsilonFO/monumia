export interface GlossaryTerm {
  /** Libellé affiché par défaut dans la bulle (si pas de children). */
  label: string;
  /** Définition courte (1–2 phrases) affichée au survol. */
  short: string;
  /** Article de blog associé (optionnel). */
  articleSlug?: string;
}

export const GLOSSARY: Record<string, GlossaryTerm> = {
  'monument-classe': {
    label: 'Classé Monument Historique',
    short:
      "Plus haut niveau de protection de l'État. Tous travaux sont soumis à autorisation et au contrôle scientifique et technique de l'État.",
    articleSlug: 'classe-ou-inscrit',
  },
  'monument-inscrit': {
    label: 'Inscrit Monument Historique',
    short:
      "Protection de niveau intermédiaire. Les travaux doivent être déclarés à l'administration, qui peut imposer des prescriptions.",
    articleSlug: 'classe-ou-inscrit',
  },
  spr: {
    label: 'Site Patrimonial Remarquable',
    short:
      "Périmètre protégeant un ensemble urbain ou paysager d'intérêt patrimonial. Les travaux y sont encadrés, même sans protection individuelle.",
    articleSlug: 'site-patrimonial-remarquable',
  },
  'perimetre-abords': {
    label: "Périmètre / abords d'un MH",
    short:
      "Zone (souvent 500 m) autour d'un Monument Historique. Les travaux visibles depuis ou avec le monument y sont soumis à avis.",
    articleSlug: 'perimetre-et-abords',
  },
  merimee: {
    label: 'Référence Mérimée',
    short:
      "Identifiant du bien dans la base Mérimée, l'inventaire national du patrimoine architectural tenu par le ministère de la Culture.",
    articleSlug: 'base-merimee',
  },
  'etat-conservation': {
    label: 'État de conservation',
    short:
      "Appréciation de l'état général du bâti (de « bon » à « en péril »). Elle pèse fortement sur l'éligibilité aux aides.",
    articleSlug: 'etat-de-conservation',
  },
  'urgence-travaux': {
    label: 'Urgence des travaux',
    short:
      "Niveau de priorité des interventions. Une urgence élevée peut justifier des aides ou des procédures accélérées.",
    articleSlug: 'etat-de-conservation',
  },
  'maitrise-ouvrage': {
    label: "Maîtrise d'ouvrage",
    short:
      "Le maître d'ouvrage est le commanditaire des travaux (vous, en tant que propriétaire). Il décide, finance et porte le projet.",
    articleSlug: 'maitrise-ouvrage-oeuvre',
  },
  'maitrise-oeuvre': {
    label: "Maîtrise d'œuvre",
    short:
      "Le maître d'œuvre (architecte, bureau d'études) conçoit le projet et dirige l'exécution des travaux pour le compte du maître d'ouvrage.",
    articleSlug: 'maitrise-ouvrage-oeuvre',
  },
  'taux-maximum': {
    label: 'Taux maximum',
    short:
      "Pourcentage maximal de la dépense éligible que l'aide peut couvrir. Le montant réel dépend aussi du plafond et de la base éligible.",
    articleSlug: 'taux-plafond-base-eligible',
  },
  'montant-maximum': {
    label: 'Montant maximum',
    short:
      "Plafond en euros de l'aide : même si le taux donnerait davantage, vous ne pouvez pas dépasser ce montant.",
    articleSlug: 'taux-plafond-base-eligible',
  },
  'base-eligible': {
    label: 'Base éligible',
    short:
      "Part des dépenses prise en compte pour calculer l'aide, exprimée TTC ou HT. Le taux s'applique à cette base, pas au coût total.",
    articleSlug: 'taux-plafond-base-eligible',
  },
  'etude-prealable': {
    label: 'Étude préalable',
    short:
      "Étude technique et historique réalisée avant les travaux sur un Monument Historique. Souvent obligatoire et parfois subventionnée.",
    articleSlug: 'etude-prealable',
  },
  diagnostic: {
    label: 'Diagnostic',
    short:
      "État des lieux du bien et de ses besoins. Il oriente le projet et conditionne l'accès à certaines aides.",
    articleSlug: 'diagnostic-prealable',
  },
  subvention: {
    label: 'Subvention',
    short:
      "Aide financière que vous n'avez pas à rembourser, contrairement à une avance remboursable ou à un prêt.",
    articleSlug: 'subvention-vs-pret',
  },
  cofinancement: {
    label: 'Cofinancement',
    short:
      "Participation de plusieurs financeurs à un même projet. De nombreuses aides l'exigent et ne couvrent jamais 100 % du coût.",
    articleSlug: 'cofinancement',
  },
  drac: {
    label: 'DRAC',
    short:
      "Direction régionale des affaires culturelles : service de l'État, interlocuteur de référence pour le patrimoine protégé et certaines aides.",
    articleSlug: 'drac',
  },
};

export function getTerm(key: string): GlossaryTerm | undefined {
  return GLOSSARY[key];
}

/** Mappe la valeur de protection d'un monument (DB) vers une clé de glossaire. */
export const PROTECTION_TERM_KEY: Record<string, keyof typeof GLOSSARY> = {
  classe: 'monument-classe',
  inscrit: 'monument-inscrit',
  abords: 'perimetre-abords',
  spr: 'spr',
};
