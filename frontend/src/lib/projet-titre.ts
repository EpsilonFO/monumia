import { WORK_TYPES } from '@/constants/monument-options';
import { RAISON_OPTIONS, readRaisons } from '@/constants/raisons';
import type { Projet } from '@/types';

const WORK_LABELS = Object.fromEntries(WORK_TYPES.map((w) => [w.value, w.label]));
const RAISON_LABELS = Object.fromEntries(RAISON_OPTIONS.map((r) => [r.value, r.label]));

/**
 * Ce que le projet fait AU monument, selon l'intention choisie à sa création.
 * `de` : l'action se construit avec « de » (« Préparer les travaux du
 * Château… »), sinon le nom est complément direct (« Restaurer le Château… »).
 */
const ACTION_PAR_RAISON: Record<string, { verbe: string; de: boolean }> = {
  restauration_travaux: { verbe: 'Restaurer', de: false },
  valorisation_rayonnement: { verbe: 'Faire vivre', de: false },
  etude_ingenierie: { verbe: 'Préparer les travaux', de: true },
  fiscalite: { verbe: 'Optimiser la fiscalité', de: true },
};

/**
 * Genre du premier mot des noms de monuments courants (c'est la forme des
 * notices Mérimée : « Château de… », « Église Saint-… »). Un mot absent de la
 * liste ne reçoit pas d'article : « Restaurer Notre-Dame de Bon-Secours » se
 * lit bien, « Restaurer le Notre-Dame » non.
 */
const MASCULINS = new Set([
  'chateau', 'manoir', 'moulin', 'lavoir', 'pigeonnier', 'colombier', 'hotel', 'logis', 'prieure',
  'couvent', 'domaine', 'pont', 'four', 'puits', 'calvaire', 'temple', 'fort', 'donjon', 'beffroi',
  'theatre', 'jardin', 'parc', 'musee', 'presbytere', 'clocher', 'oratoire', 'palais', 'cloitre',
  'portail', 'monument', 'kiosque', 'lycee', 'college', 'hopital', 'hospice', 'haras', 'phare',
  'aqueduc', 'viaduc', 'bastion', 'rempart', 'chai', 'pavillon', 'immeuble', 'ensemble', 'site',
  'cinema', 'cimetiere', 'marche', 'relais', 'mas', 'bourg', 'village', 'fortin', 'reduit', 'orgue',
]);
const FEMININS = new Set([
  'eglise', 'chapelle', 'abbaye', 'maison', 'tour', 'ferme', 'cathedrale', 'basilique', 'collegiale',
  'villa', 'halle', 'fontaine', 'grange', 'demeure', 'synagogue', 'croix', 'porte', 'bastide',
  'commanderie', 'gentilhommiere', 'forge', 'usine', 'fortification', 'citadelle', 'enceinte',
  'muraille', 'gare', 'mairie', 'ecole', 'batterie', 'redoute', 'filature', 'manufacture', 'minoterie',
  'distillerie', 'brasserie', 'cour', 'motte', 'chartreuse', 'folie', 'propriete', 'residence',
  'orangerie', 'glaciere', 'poudriere', 'loge', 'salle', 'cite', 'station',
]);
const ARTICLES = new Set(['le', 'la', 'les', "l'"]);

const sansAccents = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Mots à h aspiré de la liste : « la Halle », « le Haras », sans élision. */
const H_ASPIRES = new Set(['halle', 'haras']);

/** Vrai si le mot s'élide (« l'Abbaye », « l'Hôtel ») : voyelle ou h muet. */
function elide(mot: string): boolean {
  const m = sansAccents(mot).split('-')[0];
  return /^[aeiouy]/.test(m) || (m.startsWith('h') && !H_ASPIRES.has(m));
}

/**
 * Le nom du monument précédé de ce qu'il faut pour suivre le verbe : « le
 * Château de Villandry », « l'Église Saint-Martin », « du Moulin de Maître
 * Cornille ». Rien devant un nom qu'on ne sait pas accorder.
 */
function nomAccorde(nom: string, de: boolean): string {
  const [tete, ...reste] = nom.split(/\s+/);
  const suite = reste.join(' ');
  const teteNorm = sansAccents(tete);

  // Le nom commence déjà par un article : « Le Clos Lucé », « L'Hermitage ».
  const apostrophe = /^l['’]/i.test(tete);
  if (ARTICLES.has(teteNorm) || apostrophe) {
    if (apostrophe) return `${de ? 'de ' : ''}l'${tete.slice(2)}${suite ? ` ${suite}` : ''}`;
    const article = teteNorm;
    const apres = suite;
    if (!de) return `${article} ${apres}`;
    if (article === 'le') return `du ${apres}`;
    if (article === 'les') return `des ${apres}`;
    return `de la ${apres}`;
  }

  // Seul le premier mot compte, trait d'union compris : « Château-fort de… ».
  const motCle = teteNorm.split('-')[0];
  const genre = MASCULINS.has(motCle) ? 'm' : FEMININS.has(motCle) ? 'f' : null;
  if (!genre) return de ? `de ${nom}` : nom;
  if (elide(tete)) return `${de ? 'de ' : ''}l'${nom}`;
  if (genre === 'm') return `${de ? 'du' : 'le'} ${nom}`;
  return `${de ? 'de ' : ''}la ${nom}`;
}

/**
 * Titre affiché d'un projet. Fonction pure.
 *
 * Le champ `titre` est nullable en base : on ne force personne à nommer son
 * chantier avant de savoir ce qu'il contient. À défaut, on le nomme par
 * l'intention choisie à la création, appliquée au monument quand on connaît
 * son nom : « Restaurer le Château de Villandry », « Faire vivre l'Abbaye de
 * Noirlac ». Sans le nom, le libellé de l'intention seul ; sans intention (les
 * projets d'avant l'étape « Votre projet »), ses travaux. Jamais de chaîne
 * vide : la carte et le fil d'Ariane ont toujours quelque chose à afficher.
 */
export function projetTitre(projet: Projet, monumentNom?: string | null): string {
  if (projet.titre?.trim()) return projet.titre.trim();

  const raison = readRaisons(projet.questionnaire)[0];
  const nom = monumentNom?.trim();
  if (raison) {
    const action = ACTION_PAR_RAISON[raison];
    if (action && nom) return `${action.verbe} ${nomAccorde(nom, action.de)}`;
    if (RAISON_LABELS[raison]) return RAISON_LABELS[raison];
  }

  const travaux = projet.travauxEnvisages ?? [];
  if (travaux.length > 0) {
    const noms = travaux.slice(0, 3).map((t) => WORK_LABELS[t] ?? t);
    const reste = travaux.length - noms.length;
    return reste > 0 ? `${noms.join(', ')} +${reste}` : noms.join(', ');
  }

  return 'Projet de travaux';
}

/**
 * Ce que le projet vise, en une ligne sous son titre : ses travaux en clair
 * (« Toiture, charpente, couverture »), à défaut son intention. Null quand il
 * n'y a rien à dire, ou rien que le titre ne dise déjà (un projet sans titre
 * est nommé par ses travaux).
 */
export function projetSousTitre(projet: Projet, monumentNom?: string | null): string | null {
  const travaux = projet.travauxEnvisages ?? [];
  let ligne: string | null = null;
  if (travaux.length > 0) {
    const noms = travaux.slice(0, 3).map((t) => WORK_LABELS[t] ?? t);
    const reste = travaux.length - noms.length;
    const liste = noms.map((n, i) => (i === 0 ? n : n.charAt(0).toLowerCase() + n.slice(1))).join(', ');
    ligne = reste > 0 ? `${liste} +${reste}` : liste;
  } else {
    const raison = readRaisons(projet.questionnaire)[0];
    ligne = (raison && RAISON_LABELS[raison]) || null;
  }
  if (!ligne) return null;
  const titre = projetTitre(projet, monumentNom);
  return sansAccents(titre) === sansAccents(ligne) ? null : ligne;
}

/** Adjectifs qui précèdent parfois le nom commun : « Ancienne abbaye de… ». */
const ADJECTIFS_DE_TETE = new Set([
  'ancien', 'ancienne', 'vieux', 'vieil', 'vieille', 'grand', 'grande', 'petit', 'petite',
]);

/**
 * Le monument désigné par son nom commun, comme on en parle : « l'abbaye »
 * pour « Ancienne abbaye de Doue », « le château » pour « Château de Bar »,
 * « la chapelle » pour « La Chapelle Saint-Roch ». Avec `de` : « de
 * l'abbaye », « du château », « de la chapelle ».
 *
 * Null quand le nom ne commence pas par un nom commun dont on connaît le
 * genre (mêmes listes que les titres de projet) : l'appelant écrit alors « ce
 * monument » plutôt qu'un article inventé.
 */
export function monumentNomCourt(nom: string, de = false): string | null {
  const mots = nom.trim().split(/\s+/).filter(Boolean);
  let i = 0;
  // Un article en tête (« La Chapelle… ») : le nom commun est le mot suivant.
  if (mots[i] && ARTICLES.has(sansAccents(mots[i]))) i += 1;
  else if (mots[i] && /^l['’]/i.test(mots[i])) mots[i] = mots[i].slice(2);
  if (mots[i] && ADJECTIFS_DE_TETE.has(sansAccents(mots[i]))) i += 1;
  const tete = mots[i];
  if (!tete) return null;

  const motCle = sansAccents(tete).split('-')[0];
  const genre = MASCULINS.has(motCle) ? 'm' : FEMININS.has(motCle) ? 'f' : null;
  if (!genre) return null;

  const commun = tete.toLowerCase();
  if (elide(tete)) return `${de ? 'de ' : ''}l'${commun}`;
  if (genre === 'm') return `${de ? 'du' : 'le'} ${commun}`;
  return `${de ? 'de ' : ''}la ${commun}`;
}
