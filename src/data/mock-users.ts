import type { User } from '@/types';

export const mockUsers: User[] = [
  {
    id: 'user-1',
    segment: 'commune',
    email: 'marie.dupont@valognes.fr',
    prenom: 'Marie',
    nom: 'Dupont',
    telephone: '02 33 40 00 00',
    commune: {
      nom: 'Valognes',
      codeInsee: '50615',
      departement: '50',
      region: 'normandie',
      population: 7200,
      fonction: 'adjoint_patrimoine',
    },
    onboardingComplete: true,
    notificationPreferences: {
      urgentDeadlines: true,
      newAidesMatched: true,
      dossierUpdates: true,
      emailNotifications: true,
    },
    createdAt: '2025-11-15T10:00:00Z',
  },
  {
    id: 'user-2',
    segment: 'prive',
    email: 'jean.delaroche@gmail.com',
    prenom: 'Jean',
    nom: 'De La Roche',
    telephone: '06 12 34 56 78',
    prive: {
      typeProprietaire: 'personne_physique',
      regimeFiscal: 'monuments_historiques',
    },
    onboardingComplete: true,
    notificationPreferences: {
      urgentDeadlines: true,
      newAidesMatched: true,
      dossierUpdates: false,
      emailNotifications: true,
    },
    createdAt: '2025-12-01T14:30:00Z',
  },
];
