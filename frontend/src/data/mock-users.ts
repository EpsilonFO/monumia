import type { User } from '@/types';

export const mockUserBtp: User = {
  id: 'user-btp-1',
  segment: 'btp',
  email: 'thomas.renard@renaissancebtp.fr',
  prenom: 'Thomas',
  nom: 'Renard',
  telephone: '02 31 45 67 89',
  btp: {
    raisonSociale: 'Renaissance BTP',
    siret: '48291034700019',
    specialites: ['maconnerie', 'charpente', 'couverture', 'restauration_pierre'],
    regions: ['normandie', 'hauts-de-france', 'bretagne'],
    effectifs: '10-49',
    caAnnuel: 2400000,
  },
  onboardingComplete: true,
  notificationPreferences: {
    urgentDeadlines: true,
    newAidesMatched: true,
    dossierUpdates: true,
    emailNotifications: true,
  },
  createdAt: '2025-10-01T08:00:00Z',
};

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
  mockUserBtp,
];
