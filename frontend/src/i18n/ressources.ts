// Ressources françaises, embarquées dans le bundle : le français est la langue par
// défaut et la langue de repli, et c'est sur elles que se calquent les types des
// clés (cf. i18next.d.ts). Les autres langues se chargent à la demande (index.ts).
//
// Un namespace par domaine du code. Ajouter un namespace = créer son JSON dans
// CHAQUE dossier de langue et l'inscrire ici ; le test de parité vérifie le reste.
import admin from './locales/fr/admin.json';
import aide from './locales/fr/aide.json';
import blog from './locales/fr/blog.json';
import common from './locales/fr/common.json';
import compte from './locales/fr/compte.json';
import constants from './locales/fr/constants.json';
import core from './locales/fr/core.json';
import dashboard from './locales/fr/dashboard.json';
import documents from './locales/fr/documents.json';
import dossier from './locales/fr/dossier.json';
import libAides from './locales/fr/libAides.json';
import monuments from './locales/fr/monuments.json';
import project from './locales/fr/project.json';
import projets from './locales/fr/projets.json';
import shell from './locales/fr/shell.json';

export const ressourcesFr = {
  admin,
  aide,
  blog,
  common,
  compte,
  constants,
  core,
  dashboard,
  documents,
  dossier,
  libAides,
  monuments,
  project,
  projets,
  shell,
};

export type Namespace = keyof typeof ressourcesFr;

export const NAMESPACES = Object.keys(ressourcesFr) as Namespace[];
