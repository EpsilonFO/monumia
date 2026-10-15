import { ApiError } from '@/lib/api-error';
import { aideService } from '@/services/aide.service';
import { useDossierStore } from '@/stores/useDossierStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import type { AideFermee } from '@/types';

/**
 * Une aide sortie du catalogue alors que l'utilisateur y travaillait
 * (`backend/services/aides_fermees.py`). Le serveur la signale de deux façons :
 * `dossier.aideFermee` sur ses dossiers, et un 410 sur `GET /aides/{id}`.
 * Pour qui ne l'avait vue que dans un diagnostic, rien : elle a disparu.
 */

/** L'aide fermée que porte une erreur de `GET /aides/{id}`, sinon `null`. */
export function aideFermeeDe(err: unknown): AideFermee | null {
  if (!(err instanceof ApiError) || err.status !== 410) return null;
  const d = err.detail as Partial<AideFermee> & { code?: string } | undefined;
  if (d?.code !== 'aide_fermee' || typeof d.nom !== 'string') return null;
  return { nom: d.nom, fermeeLe: d.fermeeLe ?? '', deposee: d.deposee === true };
}

/**
 * Le panneau a été lu : le serveur le retient pour ce compte, et les dossiers
 * en préparation sur cette aide quittent les stores tout de suite (le serveur
 * ne les renverra plus). Une demande déjà déposée reste. Un échec réseau
 * n'empêche pas de les retirer de l'écran : au pire, ils reviennent au
 * prochain chargement et le panneau se rouvre.
 */
export async function oublierAideFermee(slug: string): Promise<void> {
  await aideService.marquerFermeeVue(slug).catch(console.error);
  const { dossiers, deleteDossier } = useDossierStore.getState();
  const partis = dossiers.filter((d) => d.aideId === slug && !d.aideFermee?.deposee);
  for (const d of partis) deleteDossier(d.id);
  const suivis = useSuiviStore.getState();
  for (const projetId of new Set(partis.map((d) => d.projetId))) suivis.remove(projetId, slug);
}
