import { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { monumentService } from '@/services/monument.service';
import { dossierService } from '@/services/dossier.service';
import { aideService } from '@/services/aide.service';
import { suiviService } from '@/services/suivi.service';
import { projectsDataReady } from '@/lib/projects-data-ready';

/**
 * Charge tout ce dont les cartes projet ont besoin (monuments, dossiers,
 * diagnostics d'aides, suivis) et dit quand l'ensemble est prêt à s'afficher.
 *
 * `loading` ne retombe qu'une fois TOUTES ces données réunies — pas seulement
 * la liste des monuments — pour que les squelettes couvrent aussi le nombre
 * d'aides et l'avancement du parcours (sinon les cartes s'affichent vides puis
 * « sautent » à l'arrivée des diagnostics). Au retour sur l'onglet, les stores
 * sont déjà garnis : l'affichage en cache reste visible pendant le
 * rafraîchissement, comme avant.
 */
export function useProjectsData(): { loading: boolean } {
  const token = useAuthStore((s) => s.token);
  const monuments = useMonumentStore((s) => s.monuments);
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const dossiersLoaded = useDossierStore((s) => s.loaded);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);
  const loadedSuivis = useSuiviStore((s) => s.loadedMonuments);

  // « Réglé » = l'appel est terminé, succès OU échec. Le store, lui, n'est
  // renseigné qu'en cas de succès : sans ce suivi, un appel en échec
  // laisserait le squelette affiché pour toujours.
  const [monumentsSettled, setMonumentsSettled] = useState(monuments.length > 0);
  const [dossiersSettled, setDossiersSettled] = useState(dossiersLoaded);
  const [settledDiags, setSettledDiags] = useState<Record<string, boolean>>({});
  const [settledSuivis, setSettledSuivis] = useState<Record<string, boolean>>({});

  // Rafraîchir au montage : revenir sur l'onglet reflète les changements
  // (projets/dossiers) faits par les autres membres, sans recharger la page.
  useEffect(() => {
    if (!token) return;
    monumentService
      .getAll()
      .then(setMonuments)
      .catch(console.error)
      .finally(() => setMonumentsSettled(true));
    dossierService
      .fetchAll()
      .catch(console.error)
      .finally(() => setDossiersSettled(true));
  }, [token, setMonuments]);

  // Diagnostic d'aides + suivis par monument absent du store, à chaque
  // changement de liste. On dépend uniquement de `[monuments]` : inclure les
  // stores relancerait l'effet à chaque stockage — le garde par-id dédoublonne.
  useEffect(() => {
    for (const m of monuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService
          .runProjectDiagnostic(m.id, m.questionnaire)
          .then((result) => setDiagnostic(m.id, result))
          .catch(console.error)
          .finally(() => setSettledDiags((s) => (s[m.id] ? s : { ...s, [m.id]: true })));
      }
      if (!loadedSuivis[m.id]) {
        suiviService
          .fetchByMonument(m.id)
          .catch(console.error)
          .finally(() => setSettledSuivis((s) => (s[m.id] ? s : { ...s, [m.id]: true })));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monuments]);

  const loading = useMemo(
    () =>
      !projectsDataReady({
        monumentsSettled,
        dossiersSettled: dossiersLoaded || dossiersSettled,
        monumentIds: monuments.map((m) => m.id),
        diagnostics: diagnosticsByMonument,
        settledDiags,
        loadedSuivis,
        settledSuivis,
      }),
    [
      monumentsSettled,
      dossiersLoaded,
      dossiersSettled,
      monuments,
      diagnosticsByMonument,
      settledDiags,
      loadedSuivis,
      settledSuivis,
    ],
  );

  return { loading };
}
