/**
 * Mesure d'audience anonyme (PostHog), partie PURE : quelle clé, quels
 * événements, et le nettoyage de tout ce qui part vers PostHog. Le chargement
 * de la bibliothèque et les appels vivent dans `lib/posthog.ts`.
 *
 * Le parti pris, et ce qui le rend tenable sans bandeau de consentement :
 * aucune donnée ne doit permettre de remonter à un compte. Ni cookie ni
 * stockage local (`cookieless_mode`), ni profil de personne, ni replay de
 * sessions, ni texte lu à l'écran. Reste un piège propre à Monumia : les
 * adresses de l'application portent des identifiants (`/app/monuments/<uuid>`)
 * qu'on sait relier à un compte en base, et des jetons (`/invitation/<jeton>`,
 * `?code=` au retour Google, `#access_token=` sur la réinitialisation du mot de
 * passe). `nettoyerEvenement` les retire de chaque événement avant l'envoi.
 */

/**
 * La clé du projet PostHog, ou `undefined` si la mesure ne doit pas démarrer.
 * C'est le seul interrupteur : sans `VITE_POSTHOG_KEY` (développement local,
 * tests, build sans mesure), la bibliothèque n'est même pas téléchargée.
 *
 * Cette clé est publique par nature (elle part dans chaque navigateur) : elle
 * permet d'ENVOYER des événements, pas de les lire.
 */
export function clePostHog(): string | undefined {
  // Accès littéral : Vite ne substitue `import.meta.env.X` qu'écrit en clair.
  const cle = (import.meta.env.VITE_POSTHOG_KEY as string | undefined)?.trim();
  return cle ? cle : undefined;
}

/**
 * L'opposition à la mesure, que la CNIL exige même pour une mesure exemptée de
 * consentement. Retenue dans le navigateur (le seul stockage que la mesure
 * s'autorise, et il ne sert qu'à se taire) : elle vaut pour ce navigateur, pas
 * pour le compte, puisque la mesure ignore justement de quel compte il s'agit.
 * Un stockage indisponible (navigation privée stricte) vaut « pas de refus ».
 */
const CLE_REFUS = 'monumia-mesure-audience-refusee';

export function mesureRefusee(): boolean {
  try {
    return localStorage.getItem(CLE_REFUS) === '1';
  } catch {
    return false;
  }
}

export function enregistrerRefusMesure(refus: boolean): void {
  try {
    if (refus) localStorage.setItem(CLE_REFUS, '1');
    else localStorage.removeItem(CLE_REFUS);
  } catch {
    // Rien à faire : sans stockage, le choix ne peut pas être retenu.
  }
}

/**
 * Les événements métier, en plus des pages vues et des clics que PostHog
 * capte seul. Liste fermée : un nom libre finirait en doublons orthographiques
 * dans les entonnoirs. Les propriétés ne portent jamais d'identifiant de
 * compte, de monument ni de projet, seulement des valeurs d'énumération et des
 * slugs d'aides (publics : ils viennent du catalogue).
 */
export type EvenementMesure =
  | { nom: 'inscription'; proprietes: { canal: 'email' | 'google'; viaInvitation: boolean } }
  | { nom: 'monument_cree' }
  | { nom: 'projet_cree' }
  | { nom: 'aide_suivie'; proprietes: { aide: string; statut: string } }
  | { nom: 'dossier_cree'; proprietes: { aide: string } }
  | { nom: 'dossier_depose' }
  | { nom: 'invitation_envoyee'; proprietes: { niveau: 'monument' | 'projet' } }
  | { nom: 'invitation_acceptee' };

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
/** Jeton d'invitation (`secrets.token_urlsafe`) : il vaut accès, il ne sort pas. */
const JETON_INVITATION = /(\/invitation\/)[^/?#"'\s]+/g;
/** Une adresse email (un lien `mailto:` vers un membre de l'équipe, par exemple). */
const EMAIL = /[^\s"'<>/:?#]+@[^\s"'<>/?#]+\.[a-z]{2,}/gi;
/** Le seul paramètre d'URL gardé : l'onglet ouvert, utile et sans rien de privé. */
const PARAMETRES_GARDES = new Set(['tab']);

/** Remplace les identifiants et les jetons où qu'ils soient dans la chaîne. */
export function nettoyerChaine(texte: string): string {
  return texte
    .replace(UUID, ':id')
    .replace(JETON_INVITATION, '$1:jeton')
    .replace(EMAIL, ':email');
}

/**
 * Une URL sans ce qui pourrait identifier : chemin nettoyé, paramètres réduits
 * à `tab`, fragment retiré (c'est là que Supabase pose ses jetons). Une URL
 * relative reste relative.
 */
export function nettoyerUrl(url: string): string {
  // Ni adresse ni chemin (`$direct`, `mailto:…`, `#ancre`) : rien à découper.
  if (!/^(https?:\/\/|\/)/i.test(url)) return nettoyerChaine(url);
  let lue: URL;
  try {
    lue = new URL(url, 'http://relative.invalid');
  } catch {
    return nettoyerChaine(url);
  }
  const gardes = new URLSearchParams();
  lue.searchParams.forEach((valeur, cle) => {
    if (PARAMETRES_GARDES.has(cle)) gardes.append(cle, nettoyerChaine(valeur));
  });
  const requete = gardes.toString();
  const chemin = nettoyerChaine(lue.pathname) + (requete ? `?${requete}` : '');
  return lue.origin === 'http://relative.invalid' ? chemin : lue.origin + chemin;
}

/** Les propriétés PostHog qui contiennent une URL ou un chemin. */
const CLE_URL = /url|href|referr?er|pathname/i;
const RESSEMBLE_URL = /^https?:\/\//i;

function nettoyerValeur(valeur: unknown, cle?: string): unknown {
  if (typeof valeur === 'string') {
    if (cle !== undefined && CLE_URL.test(cle)) return nettoyerUrl(valeur);
    // La chaîne des éléments cliqués (`$elements_chain`) cite les liens en
    // `href="…"` : chacun y passe comme une URL à part entière.
    return nettoyerChaine(valeur).replace(
      /href="([^"]*)"/g,
      (_, lien: string) => `href="${nettoyerUrl(lien)}"`,
    );
  }
  if (Array.isArray(valeur)) return valeur.map((v) => nettoyerValeur(v));
  if (valeur !== null && typeof valeur === 'object') {
    const propre: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(valeur)) {
      // Les heatmaps rangent leurs points sous des CLÉS qui sont des URL.
      const nouvelleCle = RESSEMBLE_URL.test(k) ? nettoyerUrl(k) : nettoyerChaine(k);
      propre[nouvelleCle] = nettoyerValeur(v, k);
    }
    return propre;
  }
  return valeur;
}

/** Ce que `before_send` reçoit et rend (sous-ensemble de `CaptureResult`). */
export interface EvenementBrut {
  event: string;
  properties: Record<string, unknown>;
  $set?: Record<string, unknown>;
  $set_once?: Record<string, unknown>;
}

/**
 * Le filtre posé sur chaque envoi. Rend `null` (l'événement ne part pas) pour
 * un compte administrateur : l'équipe passe ses journées dans l'application et
 * fausserait tous les entonnoirs.
 */
export function nettoyerEvenement<T extends EvenementBrut>(
  evenement: T | null,
  compteInterne: boolean,
): T | null {
  if (!evenement || compteInterne) return null;
  return {
    ...evenement,
    properties: nettoyerValeur(evenement.properties) as Record<string, unknown>,
    ...(evenement.$set ? { $set: nettoyerValeur(evenement.$set) } : {}),
    ...(evenement.$set_once ? { $set_once: nettoyerValeur(evenement.$set_once) } : {}),
  };
}
