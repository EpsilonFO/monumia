export interface ProjectsDataReadyInput {
  /** L'appel liste des monuments est terminé (succès ou échec). */
  monumentsSettled: boolean;
  /** Les dossiers sont chargés, ou leur appel est terminé. */
  dossiersSettled: boolean;
  monumentIds: string[];
  /** Diagnostics d'aides déjà en store, par monument. */
  diagnostics: Record<string, unknown>;
  /** Appels de diagnostic terminés sans résultat (échec réseau), par monument. */
  settledDiags: Record<string, boolean>;
  /** Suivis chargés en store, par monument. */
  loadedSuivis: Record<string, boolean>;
  /** Appels de suivis terminés sans résultat (échec réseau), par monument. */
  settledSuivis: Record<string, boolean>;
}

/**
 * Les cartes projet peuvent-elles s'afficher sans « sauter » ? Vrai quand tout
 * ce qu'elles montrent (nombre/montant d'aides, avancement, échéances) est
 * arrivé : monuments, dossiers, et pour CHAQUE monument son diagnostic d'aides
 * et ses suivis. Un appel en échec compte comme réglé — on préfère une carte
 * dégradée à un squelette éternel.
 */
export function projectsDataReady(input: ProjectsDataReadyInput): boolean {
  if (!input.monumentsSettled || !input.dossiersSettled) return false;
  return input.monumentIds.every(
    (id) =>
      (input.diagnostics[id] !== undefined || input.settledDiags[id]) &&
      (input.loadedSuivis[id] || input.settledSuivis[id]),
  );
}
