import type { PersistOptions, PersistStorage, StorageValue } from 'zustand/middleware';

/**
 * Le cache local des stores de données : afficher les dernières données
 * connues au rechargement, puis rafraîchir derrière (stale-while-revalidate).
 *
 * Sans lui, chaque rechargement repartait de stores vides, donc d'un squelette
 * plein écran le temps que `GET /dashboard` revienne. Le risque assumé est
 * d'afficher, une seconde durant, un état vieux de quelques minutes.
 *
 * Quatre garde-fous, tenus ici et nulle part ailleurs :
 *
 *  - une clé par domaine, `monumia-cache-<domaine>`, que la déconnexion purge
 *    par préfixe ;
 *  - une VERSION du format, jetée si inconnue, jamais migrée (même patron que
 *    le brouillon découverte, cf. `useBrouillonInviteStore`) : ce n'est qu'un
 *    cache, le serveur le reconstruit en une requête ;
 *  - un TTL court, vérifié à la relecture ;
 *  - le COMPTE qui a écrit l'entrée, comparé à la relecture. C'est le garde-fou
 *    qui compte le plus : une session peut changer de compte sans passer par
 *    `logout()` (expiration, second onglet, invitation acceptée sous un autre
 *    compte), et les données d'un compte ne doivent jamais s'afficher sous un
 *    autre.
 *
 * Ce qui ouvre un droit n'entre JAMAIS ici — l'offre d'un monument notamment
 * (cf. `partialize` de `useMonumentStore`) : l'éditer dans la console suffirait
 * sinon à s'ouvrir une offre côté interface. Les zones gouvernées par l'offre
 * attendent donc le serveur ; seul le contenu s'affiche depuis le cache.
 */

export const PREFIXE_CACHE = 'monumia-cache-';

/** Au-delà, l'entrée est jetée à la relecture : trente minutes suffisent à
 *  couvrir un rechargement ou une fermeture d'onglet, sans afficher au retour
 *  de déjeuner un tableau de bord que les collaborateurs ont changé. */
export const TTL_CACHE_MS = 30 * 60 * 1000;

/** Le compte dont les caches sont ouverts. `null` = aucun : rien ne s'écrit. */
let compte: string | null = null;

interface Enveloppe<P> extends StorageValue<P> {
  compte: string;
  ecritLe: number;
}

/**
 * Le stockage des caches, sur `localStorage`. Chaque accès est protégé : en
 * navigation privée, avec des données de site bloquées ou un quota plein,
 * l'accesseur lève, et l'application doit alors marcher comme sans cache.
 */
function stockage<P>(): PersistStorage<P> {
  return {
    getItem: (name) => {
      try {
        const brut = localStorage.getItem(name);
        if (!brut) return null;
        const env = JSON.parse(brut) as Partial<Enveloppe<P>>;
        const valide =
          compte !== null &&
          env.compte === compte &&
          typeof env.ecritLe === 'number' &&
          Date.now() - env.ecritLe <= TTL_CACHE_MS &&
          env.state !== undefined;
        if (!valide) {
          // L'entrée d'un autre compte, ou périmée, part tout de suite : rien ne
          // justifie de la garder sur ce poste.
          localStorage.removeItem(name);
          return null;
        }
        return { state: env.state as P, version: env.version };
      } catch {
        return null;
      }
    },
    setItem: (name, value) => {
      if (compte === null) return;
      try {
        const env: Enveloppe<P> = { ...value, compte, ecritLe: Date.now() };
        localStorage.setItem(name, JSON.stringify(env));
      } catch {
        /* quota plein, stockage bloqué : le cache est une commodité */
      }
    },
    removeItem: (name) => {
      try {
        localStorage.removeItem(name);
      } catch {
        /* idem */
      }
    },
  };
}

interface OptionsCache<S, P> {
  /** Suffixe de la clé : `monumia-cache-<domaine>`. */
  domaine: string;
  /** Version du FORMAT persisté. À incrémenter dès qu'un champ change de forme. */
  version: number;
  /** Ce qui s'écrit. Tout ce qui ouvre un droit doit en être retiré. */
  partialize: (state: S) => P;
  /** Recompose l'état à la relecture, par exemple pour marquer ce qui vient du
   *  cache. Défaut : fusion superficielle. */
  relire?: (persiste: P, courant: S) => S;
}

/**
 * Les options `persist` d'un store de données. Le store n'est PAS relu à sa
 * création (`skipHydration`) : il l'est par `ouvrirCaches`, une fois le compte
 * connu, et c'est ce qui permet la comparaison des comptes.
 */
export function optionsDeCache<S, P>({
  domaine,
  version,
  partialize,
  relire,
}: OptionsCache<S, P>): PersistOptions<S, P> {
  return {
    name: `${PREFIXE_CACHE}${domaine}`,
    version,
    storage: stockage<P>(),
    partialize,
    skipHydration: true,
    // Une version inconnue est JETÉE : rendre `null` laisse l'état en place,
    // et `merge` ci-dessous l'ignore.
    migrate: () => null as P,
    merge: (persiste, courant) => {
      if (!persiste || typeof persiste !== 'object') return courant;
      return relire ? relire(persiste as P, courant) : { ...courant, ...(persiste as P) };
    },
  };
}

interface CacheEnregistre {
  persist: { rehydrate: () => Promise<void> | void; clearStorage: () => void };
  /** Remet l'état MÉMOIRE du store à vide. */
  vider: () => void;
}

const caches: CacheEnregistre[] = [];

/**
 * Inscrit un store persisté, pour que l'ouverture et la purge le touchent.
 *
 * Un store inscrit APRÈS l'ouverture des caches se relit aussitôt. Ce n'est pas
 * un cas d'école : les stores de données et le store d'auth s'importent en
 * cycle (`useProjetStore` → `projet.service` → `auth-fetch` → `useAuthStore`),
 * et selon le module par lequel l'application entre dans ce cycle, le profil
 * peut être relu — donc les caches ouverts — avant qu'un store ait fini de
 * s'évaluer. Sans ce rattrapage, ce store-là ne serait jamais relu.
 */
export function enregistrerCache(
  store: { persist: CacheEnregistre['persist'] },
  vider: () => void,
): void {
  caches.push({ persist: store.persist, vider });
  if (compte !== null) void store.persist.rehydrate();
}

/**
 * Ouvre les caches de `userId` : relit ce que ce compte a laissé, et écrit
 * désormais sous son nom. Appelé dès que le compte de la session est connu —
 * réhydratation du profil au démarrage, connexion, rafraîchissement du profil.
 *
 * Sans effet si c'est déjà le compte ouvert. Si un AUTRE compte l'était, les
 * états mémoire sont vidés avant la relecture : la session a changé de compte
 * sans passer par `logout()`, et rien du précédent ne doit rester à l'écran.
 */
export function ouvrirCaches(userId: string): void {
  if (compte === userId) return;
  const changement = compte !== null;
  compte = userId;
  for (const cache of caches) {
    if (changement) cache.vider();
    void cache.persist.rehydrate();
  }
}

/**
 * Ferme les caches et les efface du poste, y compris les entrées d'un format
 * ou d'un domaine abandonnés (purge par préfixe). Appelé par `logout()`.
 */
export function fermerCaches(): void {
  compte = null;
  for (const cache of caches) cache.persist.clearStorage();
  try {
    const cles: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const cle = localStorage.key(i);
      if (cle?.startsWith(PREFIXE_CACHE)) cles.push(cle);
    }
    for (const cle of cles) localStorage.removeItem(cle);
  } catch {
    /* stockage inaccessible : il n'y a rien à purger */
  }
}
