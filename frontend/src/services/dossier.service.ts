import type {
  Dossier,
  DossierStep,
  DossierStatus,
  ChecklistItem,
  DossierSection,
  DossierCollaborateur,
  DossierEcheance,
  Aide,
  Monument,
  User,
  WorkType,
} from '@/types';
import { useDossierStore } from '@/stores/useDossierStore';
import { checklistTemplates } from '@/data/mock-checklist-templates';
import { generateId } from '@/lib/format-utils';

export const dossierService = {
  getAll(): Dossier[] {
    return useDossierStore.getState().dossiers;
  },

  getById(id: string): Dossier | undefined {
    return useDossierStore.getState().getDossier(id);
  },

  getByUser(userId: string): Dossier[] {
    return useDossierStore.getState().getDossiersByUser(userId);
  },

  getByMonument(monumentId: string): Dossier[] {
    return useDossierStore.getState().getDossiersByMonument(monumentId);
  },

  getByStatus(status: DossierStatus): Dossier[] {
    return useDossierStore.getState().getDossiersByStatus(status);
  },

  createFromAide(aide: Aide, monument: Monument, user: User, travauxPrevus: WorkType[]): Dossier {
    const templateKey = getTemplateKey(aide);
    const template = templateKey ? checklistTemplates[templateKey] : undefined;

    const checklist: ChecklistItem[] = template
      ? template.map((item) => ({
          ...item,
          id: `cl-${generateId()}`,
          statut: 'manquant' as const,
        }))
      : [];

    const sections: DossierSection[] = [
      {
        id: `sec-${generateId()}`,
        titre: 'Description du monument',
        type: 'texte_libre',
        contenu: monument.descriptionGenerale ?? '',
        champsAutoremplis: [
          { champ: 'Dénomination', valeur: monument.denomination, source: 'monument' },
          { champ: 'Commune', valeur: monument.commune, source: 'monument' },
          { champ: 'Protection', valeur: monument.protection, source: 'monument' },
        ],
        ordre: 1,
      },
      {
        id: `sec-${generateId()}`,
        titre: 'Description des travaux envisagés',
        type: 'texte_libre',
        contenu: monument.descriptionEtat ?? '',
        ordre: 2,
      },
      {
        id: `sec-${generateId()}`,
        titre: 'Justification',
        type: 'texte_libre',
        contenu: '',
        ordre: 3,
      },
    ];

    const echeances: DossierEcheance[] = [];
    if (aide.dateLimite) {
      echeances.push({
        id: `ech-${generateId()}`,
        label: 'Date limite de dépôt',
        date: aide.dateLimite,
        type: 'limite',
        accomplie: false,
      });
    }

    const now = new Date().toISOString();
    const dossier: Dossier = {
      id: `dos-${generateId()}`,
      monumentId: monument.id,
      aideId: aide.id,
      userId: user.id,
      titre: `${aide.nomCourt} — ${monument.nom} — ${travauxPrevus[0] ?? 'Travaux'}`,
      description: `Demande ${aide.nomCourt} pour ${monument.nom}`,
      etapeActuelle: 1,
      statut: 'brouillon',
      progressionPourcentage: 0,
      travauxPrevus,
      checklist,
      sections,
      echeances,
      collaborateurs: [],
      dateCreation: now,
      dateDerniereModification: now,
    };

    useDossierStore.getState().addDossier(dossier);
    return dossier;
  },

  updateStep(id: string, step: DossierStep): void {
    const statusMap: Record<DossierStep, DossierStatus> = {
      1: 'brouillon',
      2: 'en_cours',
      3: 'en_cours',
      4: 'complet',
      5: 'soumis',
    };
    useDossierStore.getState().updateDossier(id, {
      etapeActuelle: step,
      statut: statusMap[step],
    });
  },

  updateChecklistItem(
    dossierId: string,
    itemId: string,
    statut: ChecklistItem['statut'],
    documentId?: string
  ): void {
    useDossierStore.getState().updateChecklistItem(dossierId, itemId, statut, documentId);
    recalculateProgress(dossierId);
  },

  updateSection(dossierId: string, sectionId: string, contenu: string): void {
    useDossierStore.getState().updateSection(dossierId, sectionId, contenu);
  },

  addCollaborateur(dossierId: string, collab: Omit<DossierCollaborateur, 'id'>): void {
    useDossierStore.getState().addCollaborateur(dossierId, {
      ...collab,
      id: `collab-${generateId()}`,
    });
  },

  removeCollaborateur(dossierId: string, collabId: string): void {
    useDossierStore.getState().removeCollaborateur(dossierId, collabId);
  },

  submit(id: string): void {
    useDossierStore.getState().updateDossier(id, {
      statut: 'soumis',
      etapeActuelle: 5,
      progressionPourcentage: 100,
      dateSoumission: new Date().toISOString(),
    });
  },

  delete(id: string): void {
    useDossierStore.getState().deleteDossier(id);
  },
};

function getTemplateKey(aide: Aide): string | undefined {
  if (aide.categorie === 'etat_drac' && aide.type === 'subvention') return 'drac_subvention';
  if (aide.id === 'aide-4') return 'fip';
  if (aide.categorie === 'fondation_patrimoine' && aide.type === 'label') return 'fondation_label';
  if (aide.categorie === 'region') return 'region_subvention';
  if (aide.categorie === 'departement') return 'departement_subvention';
  return undefined;
}

function recalculateProgress(dossierId: string): void {
  const dossier = useDossierStore.getState().getDossier(dossierId);
  if (!dossier) return;

  const obligatoires = dossier.checklist.filter((c) => c.obligatoire);
  if (obligatoires.length === 0) return;

  const fournis = obligatoires.filter((c) => c.statut === 'fourni').length;
  const progression = Math.round((fournis / obligatoires.length) * 100);

  useDossierStore.getState().updateDossier(dossierId, {
    progressionPourcentage: progression,
  });
}
