import { useCallback, useEffect, useRef, useState } from 'react';
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
  BlocStats,
  StatistiquesCatalogue,
  StatsDepartement,
  StatsNature,
  StatsRegion,
} from '@/types/admin.types';

/**
 * Le catalogue en chiffres : combien d'aides, sur quel territoire, à quel taux.
 *
 * Page d'exploitation, atteinte depuis `/admin` et soumise au même garde. Elle
 * ne MODIFIE rien : c'est la carte de ce qui est couvert et de ce qui ne l'est
 * pas, celle qu'on regarde avant de décider la prochaine région à prospecter.
 *
 * La distinction qui porte toute la page : le PÉRIMÈTRE d'une aide (où elle
 * s'applique, `hard_filters`) n'est pas son FINANCEUR (qui paye, `categorie`).
 * Une aide de la Fondation du Patrimoine peut n'être ouverte qu'à huit
 * départements sans qu'un euro vienne d'un Département. D'où deux familles de
 * colonnes, et jamais un chiffre qui mélange les deux.
 *
 * Trois choses qu'elle refuse de faire, parce qu'elles mentiraient :
 *
 * - additionner des plafonds. Les aides ne s'additionnent pas, elles se
 *   cumulent sous plafond public : une « enveloppe disponible » n'existe pas ;
 * - afficher `0 €` là où la source ne chiffre rien. C'est `n.c.`, et la
 *   colonne « chiffrées » dit sur combien d'aides la fourchette porte ;
 * - masquer les territoires vides. Un zéro en face d'un département EST le
 *   chiffre qu'on vient chercher. L'interrupteur existe, il n'est pas l'état
 *   initial.
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
  align = 'right',
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

function Chiffre({ valeur, muet = false }: { valeur: number; muet?: boolean }) {
  return (
    <TableCell
      className={`text-right tabular-nums ${muet && valeur === 0 ? 'text-muted-foreground' : ''}`}
    >
      {valeur}
    </TableCell>
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

/** Les trois colonnes d'argent, identiques dans les quatre tableaux. */
function Argent({ bloc }: { bloc: BlocStats }) {
  return (
    <>
      <TableCell className="text-right tabular-nums whitespace-nowrap">
        {formaterTaux(bloc)}
      </TableCell>
      <TableCell className="text-right tabular-nums whitespace-nowrap">
        {formaterMontant(bloc.montantMedian)}
      </TableCell>
      <TableCell className="text-right tabular-nums text-muted-foreground whitespace-nowrap">
        {formaterCouverture(bloc.nbAvecMontant, bloc.nb)}
      </TableCell>
    </>
  );
}

function TableRegions({ lignes }: { lignes: StatsRegion[] }) {
  const [tri, setTri] = useState<Tri<StatsRegion>>({ cle: 'nb', sens: 'desc' });
  const visibles = trierLignes(lignes, tri);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <EnTete<StatsRegion> cle="label" tri={tri} setTri={setTri} defaut="asc" align="left">
            Région
          </EnTete>
          <EnTete<StatsRegion> cle="nb" tri={tri} setTri={setTri}>
            Aides
          </EnTete>
          <EnTete<StatsRegion> cle="regionales" tri={tri} setTri={setTri}>
            Toute la région
          </EnTete>
          <EnTete<StatsRegion> cle="locales" tri={tri} setTri={setTri}>
            Périmètre étroit
          </EnTete>
          <EnTete<StatsRegion> cle="couvertureMax" tri={tri} setTri={setTri}>
            Couv. max
          </EnTete>
          <EnTete<StatsRegion> cle="conseilRegional" tri={tri} setTri={setTri}>
            Conseil régional
          </EnTete>
          <EnTete<StatsRegion> cle="conseilsDepartementaux" tri={tri} setTri={setTri}>
            Conseils dép.
          </EnTete>
          <EnTete<StatsRegion> cle="typees" tri={tri} setTri={setTri}>
            Typées
          </EnTete>
          <EnTete<StatsRegion> cle="bientot" tri={tri} setTri={setTri}>
            Bientôt
          </EnTete>
          <EnTete<StatsRegion> cle="retirees" tri={tri} setTri={setTri}>
            Retirées
          </EnTete>
          <EnTete<StatsRegion> cle="tauxMax" tri={tri} setTri={setTri}>
            Taux
          </EnTete>
          <EnTete<StatsRegion> cle="montantMedian" tri={tri} setTri={setTri}>
            Plafond médian
          </EnTete>
          <TableHead className="text-right">Chiffrées</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {visibles.map((ligne) => (
          <TableRow key={ligne.code}>
            <TableCell className="font-medium text-foreground">{ligne.label}</TableCell>
            <Chiffre valeur={ligne.nb} muet />
            <Chiffre valeur={ligne.regionales} muet />
            <Chiffre valeur={ligne.locales} muet />
            <Chiffre valeur={ligne.couvertureMax} />
            <Chiffre valeur={ligne.conseilRegional} muet />
            <Chiffre valeur={ligne.conseilsDepartementaux} muet />
            <Chiffre valeur={ligne.typees} muet />
            <Chiffre valeur={ligne.bientot} muet />
            <Chiffre valeur={ligne.retirees} muet />
            <Argent bloc={ligne} />
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TableDepartements({ lignes }: { lignes: StatsDepartement[] }) {
  const [tri, setTri] = useState<Tri<StatsDepartement>>({ cle: 'couverture', sens: 'desc' });
  const visibles = trierLignes(lignes, tri);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <EnTete<StatsDepartement> cle="label" tri={tri} setTri={setTri} defaut="asc" align="left">
            Département
          </EnTete>
          <EnTete<StatsDepartement>
            cle="regionLabel"
            tri={tri}
            setTri={setTri}
            defaut="asc"
            align="left"
          >
            Région
          </EnTete>
          <EnTete<StatsDepartement> cle="locales" tri={tri} setTri={setTri}>
            Périmètre local
          </EnTete>
          <EnTete<StatsDepartement> cle="regionales" tri={tri} setTri={setTri}>
            + régionales
          </EnTete>
          <EnTete<StatsDepartement> cle="nationales" tri={tri} setTri={setTri}>
            + nationales
          </EnTete>
          <EnTete<StatsDepartement> cle="couverture" tri={tri} setTri={setTri}>
            Couverture
          </EnTete>
          <EnTete<StatsDepartement> cle="conseilDepartemental" tri={tri} setTri={setTri}>
            Conseil dép.
          </EnTete>
          <EnTete<StatsDepartement> cle="typees" tri={tri} setTri={setTri}>
            Typées
          </EnTete>
          <EnTete<StatsDepartement> cle="retirees" tri={tri} setTri={setTri}>
            Retirées
          </EnTete>
          <EnTete<StatsDepartement> cle="tauxMax" tri={tri} setTri={setTri}>
            Taux
          </EnTete>
          <EnTete<StatsDepartement> cle="montantMedian" tri={tri} setTri={setTri}>
            Plafond médian
          </EnTete>
          <TableHead className="text-right">Chiffrées</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {visibles.map((ligne) => (
          <TableRow key={ligne.code}>
            <TableCell className="font-medium text-foreground whitespace-nowrap">
              <span className="mr-2 font-mono text-[11.5px] text-muted-foreground">
                {ligne.code}
              </span>
              {ligne.label}
            </TableCell>
            <TableCell className="text-[13px] text-muted-foreground whitespace-nowrap">
              {ligne.regionLabel}
            </TableCell>
            <Chiffre valeur={ligne.locales} muet />
            <Chiffre valeur={ligne.regionales} muet />
            <Chiffre valeur={ligne.nationales} muet />
            <Chiffre valeur={ligne.couverture} />
            <Chiffre valeur={ligne.conseilDepartemental} muet />
            <Chiffre valeur={ligne.typees} muet />
            <Chiffre valeur={ligne.retirees} muet />
            <Argent bloc={ligne} />
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TableNature({
  titre,
  colonne,
  lignes,
}: {
  titre: string;
  colonne: string;
  lignes: StatsNature[];
}) {
  const [tri, setTri] = useState<Tri<StatsNature>>({ cle: 'nb', sens: 'desc' });
  const visibles = trierLignes(lignes, tri);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <p className="border-b border-border px-4 py-3 text-[14px] font-semibold text-foreground">
        {titre}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <EnTete<StatsNature> cle="label" tri={tri} setTri={setTri} defaut="asc" align="left">
              {colonne}
            </EnTete>
            <EnTete<StatsNature> cle="nb" tri={tri} setTri={setTri}>
              Aides
            </EnTete>
            <EnTete<StatsNature> cle="typees" tri={tri} setTri={setTri}>
              Typées
            </EnTete>
            <EnTete<StatsNature> cle="tauxMax" tri={tri} setTri={setTri}>
              Taux
            </EnTete>
            <EnTete<StatsNature> cle="montantMedian" tri={tri} setTri={setTri}>
              Plafond médian
            </EnTete>
            <TableHead className="text-right">Chiffrées</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibles.map((ligne) => (
            <TableRow key={ligne.code}>
              <TableCell className="font-medium text-foreground">{ligne.label}</TableCell>
              <Chiffre valeur={ligne.nb} muet />
              <Chiffre valeur={ligne.typees} muet />
              <Argent bloc={ligne} />
            </TableRow>
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
        if (!silencieux) toast.error(err instanceof Error ? err.message : 'Statistiques indisponibles');
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
        description="Les aides servies aujourd’hui, par territoire et par nature. Lecture seule : les retraits se font dans l’administration du catalogue."
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

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Vignette
              valeur={stats.corpus.nb}
              libelle="Aides servies"
              note={
                stats.corpus.retirees > 0
                  ? `${stats.corpus.retirees} retirée${stats.corpus.retirees > 1 ? 's' : ''} du catalogue`
                  : `sur ${stats.corpus.total} au corpus`
              }
            />
            <Vignette
              valeur={stats.corpus.nationales}
              libelle="Nationales"
              note="sans filtre de territoire"
            />
            <Vignette
              valeur={stats.corpus.regionales}
              libelle="Régionales"
              note="toute une région"
            />
            <Vignette
              valeur={stats.corpus.locales}
              libelle="Périmètre local"
              note="un ou quelques départements"
            />
            <Vignette
              valeur={stats.corpus.typees}
              libelle="Typées"
              note="traitées par le moteur"
            />
            <Vignette
              valeur={stats.corpus.bientot}
              libelle="Guichet fermé"
              note="« disponibles bientôt »"
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
              Masquer les territoires sans aide propre
            </label>
          </div>

          <Tabs defaultValue="regions">
            <TabsList>
              <TabsTrigger value="regions">Régions</TabsTrigger>
              <TabsTrigger value="departements">Départements</TabsTrigger>
              <TabsTrigger value="nature">Nature</TabsTrigger>
            </TabsList>

            <TabsContent value="regions" className="mt-4 space-y-2">
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <TableRegions lignes={regions} />
              </div>
              <p className="text-[12.5px] text-muted-foreground">
                Les trois premières colonnes disent le PÉRIMÈTRE : « Toute la région » vaut partout
                dans la région, « Périmètre étroit » ne vaut que sur les départements nommés. « Couv.
                max » y ajoute les {stats.corpus.nationales} aides nationales : c’est un maximum
                régional, pas un acquis. Les deux dernières disent le FINANCEUR, qui est une autre
                question : un appel à projets de Région peut être limité à trois départements, et
                une fondation couvrir toute la région.
              </p>
            </TabsContent>

            <TabsContent value="departements" className="mt-4 space-y-2">
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <TableDepartements lignes={departements} />
              </div>
              <p className="text-[12.5px] text-muted-foreground">
                « Couverture » est exacte : c’est ce qu’un monument de ce département voit, les
                trois étages additionnés, sans double compte. « Périmètre local » retient les aides
                qui nomment ce département, quel qu’en soit le financeur ; « Conseil dép. » ne
                retient que celles du Département lui-même — un zéro en face d’une couverture
                élevée désigne un financeur entier à prospecter. Les colonnes d’argent portent sur
                les seules aides locales : les régionales sont chiffrées sur leur propre ligne.
              </p>
            </TabsContent>

            <TabsContent value="nature" className="mt-4 grid gap-4 xl:grid-cols-2">
              <TableNature titre="Par financeur" colonne="Catégorie" lignes={stats.categories} />
              <TableNature titre="Par dispositif" colonne="Type" lignes={stats.types} />
            </TabsContent>
          </Tabs>

          <p className="text-[12.5px] text-muted-foreground">
            « Taux » donne la fourchette du groupe, « Plafond médian » la médiane des montants
            maximum annoncés, « Chiffrées » sur combien d’aides ce plafond porte. {NON_CHIFFRE} =
            la source n’annonce pas de montant : rien n’est déduit, rien n’est additionné.
          </p>
        </>
      )}
    </div>
  );
}
