import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { IconAjouter, IconMonument, IconRecherche } from '@/components/icons';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { MonumentCard } from '@/components/monument/MonumentCard';
import { ProjectListSkeleton } from '@/components/skeletons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { computeMonumentStats } from '@/lib/project-stats';
import { useProjectsData } from '@/hooks/useProjectsData';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';

type MonumentSortKey = 'recent' | 'oldest' | 'name' | 'modified';

export function MonumentsListPage() {
  const monuments = useMonumentStore((s) => s.monuments);
  const projets = useProjetStore((s) => s.projets);
  const dossiers = useDossierStore((s) => s.dossiers);
  const digestsByProjet = useAideStore((s) => s.digestsByProjet);

  // Charge monuments, projets, dossiers, diagnostics et suivis ; `loading` ne
  // retombe qu'une fois TOUT arrivé, pour que le squelette couvre aussi le
  // nombre d'aides (sinon les cartes s'affichent vides puis sautent).
  const { loading } = useProjectsData();

  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<MonumentSortKey>('recent');

  const visibleMonuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = q
      ? monuments.filter(
          (m) =>
            m.nom.toLowerCase().includes(q) ||
            (m.commune?.toLowerCase().includes(q) ?? false)
        )
      : monuments;

    const sorted = [...filtered];
    switch (sortKey) {
      case 'recent':
        sorted.sort(
          (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
        break;
      case 'oldest':
        sorted.sort(
          (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        );
        break;
      case 'name':
        sorted.sort((a, b) => a.nom.localeCompare(b.nom, 'fr', { sensitivity: 'base' }));
        break;
      case 'modified':
        sorted.sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
        break;
    }
    return sorted;
  }, [monuments, search, sortKey]);

  const newMonumentButton = (
    <Link
      to={ROUTES.MONUMENT_NEW}
      className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[13px] font-semibold text-white transition-all hover:shadow-md"
      style={{ background: C.orange }}
    >
      <IconAjouter className="h-3.5 w-3.5" strokeWidth={2} />
      Nouveau monument
    </Link>
  );

  return (
    /* Colonne resserrée et centrée : une carte par monument, tenue à une largeur
       de lecture confortable plutôt qu'étirée sur les 1200 px du gabarit. */
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-[28px]" style={{ fontFamily: SERIF, color: C.ink }}>
            Mes monuments
          </h1>
          <p className="text-[14px] text-muted-foreground">
            Chaque monument, ses projets de travaux et les aides qui vont avec.
          </p>
        </div>
        {newMonumentButton}
      </div>

      {loading ? (
        <ProjectListSkeleton />
      ) : monuments.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center gap-4 rounded-xl border py-16 text-center"
          style={{ background: C.card, borderColor: C.border }}
        >
          <IconMonument className="h-8 w-8" style={{ color: C.blueLight }} strokeWidth={1.5} />
          <div className="space-y-1">
            <h2 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
              Aucun monument pour le moment
            </h2>
            <p className="max-w-md text-[14px] text-muted-foreground">
              Décrivez votre monument, puis lancez autant de projets de travaux que
              nécessaire pour identifier les aides mobilisables.
            </p>
          </div>
          {newMonumentButton}
        </div>
      ) : (
        <>
          {/* Recherche et tri : utiles seulement quand la liste devient longue.
              La plupart des comptes ont 1-2 monuments — on leur épargne ce bruit. */}
          {monuments.length > 3 && (
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1 sm:max-w-md">
                <IconRecherche
                  className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
                  strokeWidth={1.8}
                />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Rechercher un monument..."
                  className="h-10 pl-9 text-[14px]"
                  style={{ background: C.card, borderColor: C.border }}
                />
              </div>

              <Select value={sortKey} onValueChange={(v) => setSortKey(v as MonumentSortKey)}>
                <SelectTrigger
                  className="h-10 w-full text-[14px] sm:w-56"
                  style={{ background: C.card, borderColor: C.border }}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recent">Créés récemment</SelectItem>
                  <SelectItem value="oldest">Plus anciens</SelectItem>
                  <SelectItem value="modified">Récemment modifiés</SelectItem>
                  <SelectItem value="name">Nom (A → Z)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {visibleMonuments.length === 0 ? (
            <div
              className="rounded-xl border py-12 text-center text-[14px] text-muted-foreground"
              style={{ background: C.card, borderColor: C.border }}
            >
              Aucun monument ne correspond à votre recherche.
            </div>
          ) : (
            /* Liste verticale (façon Doctolib) : une carte horizontale par
               monument, lisible de haut en bas — même rendu avec 1, 2 ou 20. */
            <div className="space-y-4">
              {visibleMonuments.map((monument) => (
                <MonumentCard
                  key={monument.id}
                  monument={monument}
                  stats={computeMonumentStats(monument, projets, digestsByProjet, dossiers)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
