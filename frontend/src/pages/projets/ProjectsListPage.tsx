import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Plus, Landmark, Search, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ProjectCard } from '@/components/project/ProjectCard';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { monumentService } from '@/services/monument.service';
import { dossierService } from '@/services/dossier.service';
import { aideService } from '@/services/aide.service';
import { computeProjectStats } from '@/lib/project-stats';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';

type ProjectSortKey = 'recent' | 'oldest' | 'name' | 'modified';

export function ProjectsListPage() {
  const token = useAuthStore((s) => s.token);
  const monuments = useMonumentStore((s) => s.monuments);
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  const [loading, setLoading] = useState(monuments.length === 0);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<ProjectSortKey>('recent');

  useEffect(() => {
    if (!token) return;
    // Toujours rafraîchir au montage (revenir sur l'onglet doit refléter les
    // changements faits par les autres membres). On garde l'affichage en cache
    // pendant le rechargement — le spinner n'apparaît que si rien n'est encore là.
    monumentService
      .getAll()
      .then(setMonuments)
      .catch(console.error)
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (token) dossierService.fetchAll().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    for (const m of monuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService
          .runProjectDiagnostic(m.id, m.questionnaire)
          .then((result) => setDiagnostic(m.id, result))
          .catch(console.error);
      }
    }
    // Recalcule le diagnostic déterministe par monument à chaque changement de
    // liste ; le garde par-id évite les recalculs en double une fois stocké.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monuments]);

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

  const newProjectButton = (
    <Link
      to={ROUTES.PROJET_NEW}
      className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[13px] font-semibold text-white transition-all hover:shadow-md"
      style={{ background: C.orange }}
    >
      <Plus className="h-3.5 w-3.5" strokeWidth={2} />
      Nouveau projet
    </Link>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-[28px]" style={{ fontFamily: SERIF, color: C.ink }}>
            Mes projets
          </h1>
          <p className="text-[14px] text-muted-foreground">
            Chaque monument et ses aides, dossiers et échéances réunis.
          </p>
        </div>
        {newProjectButton}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : monuments.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center gap-4 rounded-xl border py-16 text-center"
          style={{ background: C.card, borderColor: C.border }}
        >
          <Landmark className="h-8 w-8" style={{ color: C.blueLight }} strokeWidth={1.5} />
          <div className="space-y-1">
            <h2 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
              Aucun projet pour le moment
            </h2>
            <p className="max-w-md text-[14px] text-muted-foreground">
              Créez votre premier projet pour identifier les aides mobilisables sur votre
              monument.
            </p>
          </div>
          {newProjectButton}
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1 sm:max-w-md">
              <Search
                className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
                strokeWidth={1.8}
              />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher un projet..."
                className="h-10 pl-9 text-[14px]"
                style={{ background: C.card, borderColor: C.border }}
              />
            </div>

            <Select value={sortKey} onValueChange={(v) => setSortKey(v as ProjectSortKey)}>
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

          {visibleMonuments.length === 0 ? (
            <div
              className="rounded-xl border py-12 text-center text-[14px] text-muted-foreground"
              style={{ background: C.card, borderColor: C.border }}
            >
              Aucun projet ne correspond à votre recherche.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {visibleMonuments.map((monument) => (
                <ProjectCard
                  key={monument.id}
                  monument={monument}
                  stats={computeProjectStats(
                    monument,
                    diagnosticsByMonument[monument.id] ?? null,
                    dossiers
                  )}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
