import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { toast } from 'sonner';
import { IconAttention, IconRafraichir, IconRecherche } from '@/components/icons';
import { PageHeader } from '@/components/shared/PageHeader';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { adminService } from '@/services/admin.service';
import { ApiError } from '@/lib/api-error';
import {
  NON_CHIFFRE,
  basculerTri,
  filtrerTerritoires,
  formaterCouverture,
  formaterHeure,
  formaterMontant,
  formaterTaux,
  masquerVides,
  trierLignes,
  type SensTri,
  type Tri,
} from '@/lib/admin-stats';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import type {
  GroupeStats,
  StatistiquesCatalogue,
  StatsNature,
  StatsTerritoire,
} from '@/types/admin.types';

/**
 * Le catalogue en chiffres : combien d'aides par territoire, et lesquelles.
 *
 * Page d'exploitation, atteinte depuis `/admin` et soumise au même garde. Elle
 * ne MODIFIE rien : c'est la carte de ce qui est couvert et de ce qui ne l'est
 * pas, celle qu'on regarde avant de décider la prochaine région à prospecter.
 *
 * **Un seul chiffre par ligne, et les noms nus derrière.** La page a eu treize
 * colonnes (financeur, typage, guichet, taux, plafonds) : personne ne les
 * lisait, et chercher « combien d'aides pour la Bretagne ? » demandait de
 * choisir entre six nombres. Elle répond maintenant à cette question-là, puis
 * à « lesquelles ? » quand on déplie une ligne — le NOM seul, sans organisme
 * ni chiffres, qui rallongeaient chaque puce sans rien apprendre. Le reste se
 * lit dans les autres onglets de `/admin`, où il est à sa place.
 *
 * **Les lignes classent par FINANCEUR, pas par périmètre.** « Les aides du
 * département de l'Isère » veut dire celles que le Conseil départemental
 * finance — pas celles qui s'y appliquent, qui sont aussi celles de la Région
 * et de l'État. Un dispositif régional limité à trois départements reste sur
 * la ligne de sa Région, et la délégation Rhône-Alpes d'une fondation va dans
 * « autres financeurs ».
 *
 * Les quatre échelons sont DISJOINTS et s'additionnent : Conseil régional,
 * Conseil départemental, périmètre national, autres financeurs. Le quatrième
 * n'est pas une poubelle : sans lui, une aide de fondation ouverte à huit
 * départements serait soit invisible, soit comptée comme une aide du
 * Département, ce qu'elle n'est pas.
 *
 * Deux choses que la page refuse de faire, parce qu'elles mentiraient :
 *
 * - additionner des plafonds. Les aides ne s'additionnent pas, elles se
 *   cumulent sous plafond public : une « enveloppe disponible » n'existe pas ;
 * - afficher `0 €` là où la source ne chiffre rien. C'est `n.c.`, et le
 *   dépliant dit sur combien d'aides la fourchette porte.
 *
 * Le rafraîchissement : la page se rappelle toute seule chaque minute, et à
 * chaque retour d'onglet. Elle suit ainsi les retraits enregistrés depuis
 * `/admin` (cache serveur d'une minute). Un nouveau LOT D'AIDES, lui, entre
 * par les YAML, que le backend lit au démarrage : il apparaît au déploiement
 * qui l'amène, pas à la minute où le loader tourne.
 */

const INTERVALLE_MS = 60_000;

/** En-tête cliquable. Le sens par défaut dépend de la colonne : un nom part de
 *  A, un compte part du plus gros — c'est ce qu'on cherche dans les deux cas. */
function EnTete<T>({
  cle,
  tri,
  setTri,
  defaut = 'desc',
  align = 'left',
  children,
}: {
  cle: keyof T;
  tri: Tri<T>;
  setTri: (t: Tri<T>) => void;
  defaut?: SensTri;
  align?: 'left' | 'right';
  children: React.ReactNode;
}) {
  const actif = tri.cle === cle;
  return (
    <TableHead className={align === 'right' ? 'text-right' : ''}>
      <button
        type="button"
        onClick={() => setTri(basculerTri(tri, cle, defaut))}
        className={`inline-flex items-center gap-1 transition-colors hover:text-foreground ${
          actif ? 'font-semibold text-foreground' : ''
        }`}
      >
        {children}
        <span aria-hidden className={actif ? '' : 'opacity-0'}>
          {tri.sens === 'asc' ? '↑' : '↓'}
        </span>
      </button>
    </TableHead>
  );
}

/** Un compteur du bandeau de tête. */
function Vignette({ valeur, libelle, note }: { valeur: number; libelle: string; note?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <p className="text-[26px] leading-none tabular-nums" style={{ fontFamily: SERIF }}>
        {valeur}
      </p>
      <p className="mt-1.5 text-[13px] font-medium text-foreground">{libelle}</p>
      {note && <p className="text-[12px] text-muted-foreground">{note}</p>}
    </div>
  );
}

/**
 * Le dépliant d'une ligne : le chiffrage du groupe, puis les aides par leur nom.
 *
 * C'est ici que vivent le taux et le plafond — pas en colonnes. Un groupe vide
 * le dit en une phrase plutôt que d'ouvrir un cadre vide : sur cent un
 * départements, la plupart n'ont encore rien.
 */
/** Les aides d'un groupe, par leur nom et rien d'autre. Une seule
 *  implémentation : les dépliants et les deux onglets de liste s'en servent. */
function ListeAides({ slugs, aides }: { slugs: string[]; aides: Record<string, string> }) {
  return (
    <ul className="space-y-1 text-[13px] leading-snug text-foreground">
      {slugs.map((slug) => {
        const nom = aides[slug];
        // Un slug sans nom ne peut venir que d'une réponse tronquée : on saute
        // la ligne plutôt que d'afficher une puce vide.
        if (!nom) return null;
        return <li key={slug}>{nom}</li>;
      })}
    </ul>
  );
}

/** La ligne de chiffrage d'un groupe : ce qui reste des colonnes d'argent. */
function Chiffrage({ groupe }: { groupe: GroupeStats }) {
  return (
    <p className="text-[12.5px] text-muted-foreground">
      Taux : <span className="text-foreground">{formaterTaux(groupe)}</span> · Plafond médian :{' '}
      <span className="text-foreground">{formaterMontant(groupe.montantMedian)}</span> · chiffrées :{' '}
      {formaterCouverture(groupe.nbAvecMontant, groupe.nb)}
    </p>
  );
}

function Depliant({
  groupe,
  aides,
  colonnes,
}: {
  groupe: GroupeStats;
  aides: Record<string, string>;
  colonnes: number;
}) {
  return (
    <TableRow className="hover:bg-transparent">
      <TableCell colSpan={colonnes} className="bg-secondary/40 px-4 py-3">
        {groupe.nb === 0 ? (
          <p className="text-[13px] text-muted-foreground">
            Aucune aide de cette collectivité dans le catalogue.
          </p>
        ) : (
          <>
            <div className="mb-2">
              <Chiffrage groupe={groupe} />
            </div>
            <ListeAides slugs={groupe.slugs} aides={aides} />
          </>
        )}
      </TableCell>
    </TableRow>
  );
}

/**
 * Le tableau des territoires : un nom, un nombre, et le détail au clic.
 *
 * `avecRegion` ajoute la seule colonne qui distingue les deux onglets — la
 * région de rattachement d'un département. Le reste est identique, et deux
 * composats jumeaux dériveraient l'un de l'autre à la première retouche.
 */
function TableauTerritoires({
  lignes,
  titre,
  colonneNb,
  avecRegion = false,
  aides,
}: {
  lignes: StatsTerritoire[];
  titre: string;
  /** Ce que le nombre compte. « Aides » tout court laisserait croire au total
   *  applicable sur le territoire, qui est une autre question. */
  colonneNb: string;
  avecRegion?: boolean;
  aides: Record<string, string>;
}) {
  const [tri, setTri] = useState<Tri<StatsTerritoire>>({ cle: 'nb', sens: 'desc' });
  const [ouvert, setOuvert] = useState<string | null>(null);
  const visibles = trierLignes(lignes, tri);
  const colonnes = avecRegion ? 3 : 2;

  if (visibles.length === 0) {
    return (
      <p className="px-4 py-8 text-center text-[14px] text-muted-foreground">
        Aucun territoire ne correspond à votre recherche.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <EnTete<StatsTerritoire> cle="label" tri={tri} setTri={setTri} defaut="asc">
            {titre}
          </EnTete>
          {avecRegion && (
            <EnTete<StatsTerritoire> cle="regionLabel" tri={tri} setTri={setTri} defaut="asc">
              Région
            </EnTete>
          )}
          <EnTete<StatsTerritoire> cle="nb" tri={tri} setTri={setTri} align="right">
            {colonneNb}
          </EnTete>
        </TableRow>
      </TableHeader>
      <TableBody>
        {visibles.map((ligne) => (
          <Fragment key={ligne.code}>
            <TableRow
              onClick={() => setOuvert(ouvert === ligne.code ? null : ligne.code)}
              className={`cursor-pointer ${ouvert === ligne.code ? 'bg-secondary' : ''}`}
            >
              <TableCell className="font-medium text-foreground whitespace-nowrap">
                <span aria-hidden className="mr-2 inline-block w-2 text-muted-foreground">
                  {ouvert === ligne.code ? '▾' : '▸'}
                </span>
                {avecRegion && (
                  <span className="mr-2 font-mono text-[11.5px] text-muted-foreground">
                    {ligne.code}
                  </span>
                )}
                {ligne.label}
              </TableCell>
              {avecRegion && (
                <TableCell className="text-[13px] text-muted-foreground whitespace-nowrap">
                  {ligne.regionLabel}
                </TableCell>
              )}
              <TableCell
                className={`text-right tabular-nums ${ligne.nb === 0 ? 'text-muted-foreground' : ''}`}
              >
                {ligne.nb}
              </TableCell>
            </TableRow>
            {ouvert === ligne.code && (
              <Depliant groupe={ligne} aides={aides} colonnes={colonnes} />
            )}
          </Fragment>
        ))}
      </TableBody>
    </Table>
  );
}

/** Même tableau, pour les regroupements qui ne sont pas des territoires. */
function TableauNature({
  titre,
  colonne,
  lignes,
  aides,
}: {
  titre: string;
  colonne: string;
  lignes: StatsNature[];
  aides: Record<string, string>;
}) {
  const [tri, setTri] = useState<Tri<StatsNature>>({ cle: 'nb', sens: 'desc' });
  const [ouvert, setOuvert] = useState<string | null>(null);
  const visibles = trierLignes(lignes, tri);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <p className="border-b border-border px-4 py-3 text-[14px] font-semibold text-foreground">
        {titre}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <EnTete<StatsNature> cle="label" tri={tri} setTri={setTri} defaut="asc">
              {colonne}
            </EnTete>
            <EnTete<StatsNature> cle="nb" tri={tri} setTri={setTri} align="right">
              Aides
            </EnTete>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibles.map((ligne) => (
            <Fragment key={ligne.code}>
              <TableRow
                onClick={() => setOuvert(ouvert === ligne.code ? null : ligne.code)}
                className={`cursor-pointer ${ouvert === ligne.code ? 'bg-secondary' : ''}`}
              >
                <TableCell className="font-medium text-foreground">
                  <span aria-hidden className="mr-2 inline-block w-2 text-muted-foreground">
                    {ouvert === ligne.code ? '▾' : '▸'}
                  </span>
                  {ligne.label}
                </TableCell>
                <TableCell
                  className={`text-right tabular-nums ${ligne.nb === 0 ? 'text-muted-foreground' : ''}`}
                >
                  {ligne.nb}
                </TableCell>
              </TableRow>
              {ouvert === ligne.code && <Depliant groupe={ligne} aides={aides} colonnes={2} />}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/**
 * L'écart entre le corpus servi et `aides_v3`. Une aide absente de la table
 * est proposée par le diagnostic mais répond « Aide introuvable » à la
 * création de dossier : c'est une panne à réparer (`load_aides_yaml.py`), pas
 * une statistique. D'où l'encart rouge, et le silence quand tout va bien.
 */
function Synchronisation({ stats }: { stats: StatistiquesCatalogue }) {
  const sync = stats.synchronisation;
  if (!sync.lisible || sync.nbManquantes === 0) return null;
  return (
    <div
      className="flex items-start gap-3 rounded-xl border px-4 py-3"
      style={{ borderColor: C.danger, background: C.paleDanger }}
    >
      <IconAttention className="mt-0.5 h-4 w-4 flex-shrink-0" style={{ color: C.danger }} />
      <div className="text-[13.5px]">
        <p className="font-semibold text-foreground">
          {sync.nbManquantes} aide{sync.nbManquantes > 1 ? 's' : ''} absente
          {sync.nbManquantes > 1 ? 's' : ''} de la base
        </p>
        <p className="mt-0.5 text-muted-foreground">
          Le diagnostic les propose, mais la création de dossier répondra « Aide introuvable ».
          Relancer <code className="font-mono">scripts/load_aides_yaml.py</code> pour les pousser.
        </p>
        <p className="mt-1 font-mono text-[11.5px] text-muted-foreground">
          {sync.manquantes.join(', ')}
          {sync.nbManquantes > sync.manquantes.length && '…'}
        </p>
      </div>
    </div>
  );
}

export function AdminStatsPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<StatistiquesCatalogue | null>(null);
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState('');
  const [masquerVidesActif, setMasquerVidesActif] = useState(false);

  // Une erreur de fond ne doit pas effacer les chiffres déjà affichés : la page
  // reste lisible, un toast signale que le rafraîchissement a échoué.
  const monte = useRef(true);
  useEffect(() => {
    monte.current = true;
    return () => {
      monte.current = false;
    };
  }, []);

  const charger = useCallback(
    async (silencieux: boolean) => {
      try {
        const reponse = await adminService.statistiques();
        if (monte.current) setStats(reponse);
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          toast.error('Accès réservé à l’administration');
          navigate(ROUTES.DASHBOARD, { replace: true });
          return;
        }
        if (!silencieux)
          toast.error(err instanceof Error ? err.message : 'Statistiques indisponibles');
      } finally {
        if (monte.current) setChargement(false);
      }
    },
    [navigate],
  );

  // Rafraîchissement : une fois par minute, et au retour sur l'onglet. Un
  // onglet caché ne tire rien — laisser tourner l'intervalle sur une page
  // oubliée en arrière-plan ferait travailler le serveur pour personne.
  useEffect(() => {
    void charger(false);
    const timer = window.setInterval(() => {
      if (!document.hidden) void charger(true);
    }, INTERVALLE_MS);
    const auRetour = () => {
      if (!document.hidden) void charger(true);
    };
    document.addEventListener('visibilitychange', auRetour);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', auRetour);
    };
  }, [charger]);

  const regions = stats
    ? masquerVides(filtrerTerritoires(stats.regions, recherche), masquerVidesActif)
    : [];
  const departements = stats
    ? masquerVides(filtrerTerritoires(stats.departements, recherche), masquerVidesActif)
    : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Le catalogue en chiffres"
        description="Combien d’aides finance chaque Conseil régional, chaque Conseil départemental, et combien valent partout. Cliquer une ligne déplie leurs noms."
        action={
          <div className="flex items-center gap-3">
            {stats && (
              <span className="text-[12.5px] text-muted-foreground">
                à jour à {formaterHeure(stats.genereLe)}
              </span>
            )}
            <button
              type="button"
              onClick={() => void charger(false)}
              className="inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-[14px] font-medium transition-colors hover:bg-[var(--secondary)]"
              style={{ borderColor: C.border, color: C.blue }}
            >
              <IconRafraichir className="h-4 w-4" />
              Rafraîchir
            </button>
          </div>
        }
      />

      <Link to={ROUTES.ADMIN} className="inline-block text-[13.5px]" style={{ color: C.blue }}>
        ← Administration du catalogue
      </Link>

      {chargement && !stats ? (
        <p className="px-4 py-8 text-center text-[14px] text-muted-foreground">Chargement…</p>
      ) : !stats ? (
        <p className="px-4 py-8 text-center text-[14px] text-muted-foreground">
          Statistiques indisponibles.
        </p>
      ) : (
        <>
          <Synchronisation stats={stats} />

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Vignette
              valeur={stats.corpus.nb}
              libelle="Aides au catalogue"
              note={
                stats.corpus.retirees > 0
                  ? `${stats.corpus.retirees} retirée${stats.corpus.retirees > 1 ? 's' : ''}, non comptée${stats.corpus.retirees > 1 ? 's' : ''}`
                  : undefined
              }
            />
            <Vignette
              valeur={stats.corpus.nationales}
              libelle="Nationales"
              note="État, fiscalité, fondations nationales"
            />
            <Vignette
              valeur={stats.corpus.regionales}
              libelle="Conseils régionaux"
              note="quel que soit leur périmètre"
            />
            <Vignette
              valeur={stats.corpus.departementales}
              libelle="Conseils départementaux"
              note="quel que soit leur périmètre"
            />
            <Vignette
              valeur={stats.corpus.autres}
              libelle="Autres financeurs"
              note="fondations, Europe, mécénat"
            />
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1 sm:max-w-md">
              <IconRecherche
                className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
                strokeWidth={1.8}
              />
              <Input
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
                placeholder="Filtrer un territoire (nom, code INSEE, région)…"
                className="h-10 pl-9 text-[14px]"
              />
            </div>
            <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
              <Switch checked={masquerVidesActif} onCheckedChange={setMasquerVidesActif} />
              Masquer les territoires sans aide
            </label>
          </div>

          <Tabs defaultValue="regions">
            <TabsList>
              <TabsTrigger value="regions">Régions</TabsTrigger>
              <TabsTrigger value="departements">Départements</TabsTrigger>
              <TabsTrigger value="national">National</TabsTrigger>
              <TabsTrigger value="autres">Autres financeurs</TabsTrigger>
              <TabsTrigger value="nature">Nature</TabsTrigger>
            </TabsList>

            <TabsContent value="regions" className="mt-4 space-y-2">
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <TableauTerritoires
                  lignes={regions}
                  titre="Région"
                  colonneNb="Aides du Conseil régional"
                  aides={stats.aides}
                />
              </div>
              <p className="text-[12.5px] text-muted-foreground">
                Les aides financées par chaque Conseil régional, y compris celles qu’il limite à
                quelques départements. Ce que la Région finance, pas ce qui s’applique sur son
                territoire : les aides de l’État et des Départements sont sur leurs propres
                onglets.
              </p>
            </TabsContent>

            <TabsContent value="departements" className="mt-4 space-y-2">
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <TableauTerritoires
                  lignes={departements}
                  titre="Département"
                  colonneNb="Aides du Conseil départemental"
                  avecRegion
                  aides={stats.aides}
                />
              </div>
              <p className="text-[12.5px] text-muted-foreground">
                Les aides financées par chaque Conseil départemental. Un zéro ne veut pas dire
                qu’un monument du département n’a droit à rien : il voit aussi les aides de sa
                région, les nationales et celles des autres financeurs. Il veut dire qu’il reste un
                Département entier à prospecter.
              </p>
            </TabsContent>

            <TabsContent value="national" className="mt-4 space-y-2">
              <div className="overflow-hidden rounded-xl border border-border bg-card px-4 py-4">
                <p className="text-[14px] font-medium text-foreground">
                  {stats.corpus.nationales} aides sans filtre géographique
                </p>
                <div className="mt-0.5 mb-3">
                  <Chiffrage groupe={stats.national} />
                </div>
                <ListeAides slugs={stats.national.slugs} aides={stats.aides} />
              </div>
            </TabsContent>

            <TabsContent value="autres" className="mt-4 space-y-2">
              <div className="overflow-hidden rounded-xl border border-border bg-card px-4 py-4">
                <p className="text-[14px] font-medium text-foreground">
                  {stats.corpus.autres} aides d’un financeur sans échelon territorial
                </p>
                <div className="mt-0.5 mb-3">
                  <Chiffrage groupe={stats.autres} />
                </div>
                <ListeAides slugs={stats.autres.slugs} aides={stats.aides} />
              </div>
              <p className="text-[12.5px] text-muted-foreground">
                Fondations, Europe, mécénat : leur périmètre est local sans qu’un euro vienne d’une
                collectivité. Les compter comme des aides de Département serait faux, les cacher
                les ferait disparaître de la page.
              </p>
            </TabsContent>

            <TabsContent value="nature" className="mt-4 grid gap-4 xl:grid-cols-2">
              <TableauNature
                titre="Par financeur"
                colonne="Catégorie"
                lignes={stats.categories}
                aides={stats.aides}
              />
              <TableauNature
                titre="Par dispositif"
                colonne="Type"
                lignes={stats.types}
                aides={stats.aides}
              />
            </TabsContent>
          </Tabs>

          <p className="text-[12.5px] text-muted-foreground">
            Les quatre chiffres de tête s’additionnent : une aide est comptée une seule fois, sur
            l’échelon qui la finance. {NON_CHIFFRE} = la source n’annonce ni taux ni montant : rien
            n’est déduit, rien n’est additionné. Les aides retirées du catalogue ne sont ni
            comptées ni listées.
          </p>
        </>
      )}
    </div>
  );
}
