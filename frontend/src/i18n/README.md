# Internationalisation (i18n)

Bibliothèque : `i18next` + `react-i18next` (+ `i18next-browser-languagedetector`).
Le site vitrine (`landing/src/i18n/`) suit le même modèle avec ses propres namespaces.

## Où sont les textes

```
src/i18n/
  index.ts            initialisation, langue courante, changerLangue()
  ressources.ts       la liste des namespaces (JSON français importés)
  i18next.d.ts        typage des clés sur les JSON français
  format.ts           localeIntl(), localeDateFns() : dates et nombres selon la langue
  SelecteurLangue.tsx la bascule FR / EN
  locales/fr/<ns>.json
  locales/en/<ns>.json
```

- **Le français est la langue par défaut et la langue de repli.** Il est embarqué dans
  le bundle ; l'anglais se charge à la demande avant le premier rendu.
- **La langue est fixe pour la durée de vie de la page** : `changerLangue()` mémorise
  le choix (localStorage + cookie `monumia_langue` sur le domaine parent, partagé avec
  le site vitrine) et recharge. Conséquence : un libellé calculé hors React reste juste.
- Un namespace par domaine du code (`projets`, `documents`, `aide`…), plus `common`
  pour les mots d'action génériques (Annuler, Enregistrer…).
- Les clés sont **typées** : `t('projets:cle.absente')` ne compile pas. Le test
  `src/i18n/__tests__/parite.test.ts` vérifie que chaque langue a exactement les clés
  du français, avec les mêmes variables `{{x}}` et les mêmes balises.

## Écrire du code traduit

Dans un composant :

```tsx
import { Trans, useTranslation } from 'react-i18next';

const { t } = useTranslation(['projets', 'common']); // le premier est le namespace par défaut
t('ProjetDetailPage.titre');                       // clé du namespace par défaut
t('common:actions.annuler');                       // clé d'un autre namespace, qui doit
                                                   // figurer dans la liste (sinon ne compile pas)
t('ProjetDetailPage.aidesTrouvees', { count: n }); // pluriel : clés `_one` / `_other`
t('ProjetDetailPage.bonjour', { nom });            // JSON : "Bonjour {{nom}}"
<Trans t={t} i18nKey="ProjetDetailPage.cgu" components={{ lien: <Link to="/cgu" /> }} />
// JSON : "J'accepte les <lien>conditions</lien>"
```

Hors composant (lib, stores, services) :

```ts
import i18n from '@/i18n';
i18n.t('core:erreurs.reseau');
```

Règles :

- **Jamais de `t` au niveau module** (constante calculée à l'import). Une table de
  libellés devient une fonction, ou la table garde des CLÉS qu'on traduit au rendu.
- Clés en camelCase français, groupées par composant ou par fichier :
  `NomDuComposant.cleCourte`. Le texte français est recopié **à l'identique** dans le
  JSON (apostrophes typographiques, espaces insécables, guillemets « »).
- Une phrase reste entière dans une clé : pas de concaténation de morceaux traduits
  (l'ordre des mots change d'une langue à l'autre). Variables et `<Trans>` à la place.
- Clé dynamique : `t(\`statut.${s}\`)` compile si `s` est une union dont chaque valeur
  existe comme clé. Sinon, une table explicite `{ a: t('statut.a'), … }`.
- Dates et nombres : `localeIntl()` (`'fr-FR'` / `'en-GB'`) pour `Intl.*` et
  `toLocale*String`, `localeDateFns()` pour date-fns, à la place de `'fr-FR'` et `fr`.
- Pluriels : le français classe 0 au singulier (`_one`), l'anglais au pluriel.

Ce qui **ne se traduit pas** : identifiants et valeurs d'énumérations envoyés à l'API,
routes, classes CSS, logs console, noms d'événements d'analytics, commentaires, tests,
noms propres (DRAC, Fondation du Patrimoine, Mérimée, Monumia, noms de régions et de
départements), et tout ce qui vient du serveur (nom et fiche des aides, questions du
questionnaire, messages d'erreur de l'API) : c'est de la donnée, traduite (ou non)
côté serveur.

## Lister ce qui reste en dur

```bash
node scripts/i18n-reste.mjs src/components/aide      # une ligne par texte candidat
node scripts/i18n-reste.mjs --compte src             # un total par fichier
```

Heuristique : un identifiant technique peut sortir, un mot isolé sans accent peut passer.

## Glossaire français → anglais

Anglais britannique (orthographe et dates, cohérent avec `en-GB`). Vouvoiement → « you ».
Pas de tiret cadratin dans les textes anglais : virgule, deux-points ou parenthèses.

| Français | English |
|---|---|
| aide (dispositif) | funding scheme (court : scheme) ; « les aides » au sens large : funding |
| subvention | grant |
| prêt | loan |
| dispositif fiscal | tax scheme |
| financeur | funder |
| monument | monument |
| projet (chantier sur un monument) | project |
| dossier (de demande) | application |
| suivi d'aide / suivre une aide | tracked scheme / track a scheme |
| diagnostic (d'éligibilité) | eligibility check |
| éligible / potentiellement éligible / non éligible | eligible / potentially eligible / not eligible |
| critère, condition | criterion, condition |
| questionnaire | questionnaire |
| Disponibles bientôt | Opening soon |
| guichet (ouvert / fermé) | application window (open / closed) |
| échéance / échéancier | deadline / timeline |
| pièces (à déposer), pièces justificatives | supporting documents |
| dépôt, déposer | submission, submit |
| règlement (du financeur) | (funder's) rules |
| travaux | works |
| propriétaire | owner |
| commune | municipality |
| association | association |
| particulier, propriétaire privé | private owner |
| maître d'ouvrage / maître d'œuvre | project owner / project manager |
| monument historique (MH) | historic monument (MH) |
| classé / inscrit (au titre des MH) | listed (classé) / registered (inscrit) |
| abords, périmètre délimité des abords | surroundings, protected surroundings |
| site patrimonial remarquable (SPR) | outstanding heritage site (SPR) |
| état sanitaire, en péril | condition, at risk |
| équipe, membre, co-propriétaire (rôle) | team, member, co-owner |
| inviter, invitation | invite, invitation |
| tableau de bord | dashboard |
| offre Gratuit / Veille / Multi-monuments | Free / Watch / Multi-monument plan |
| Sur demande | On request |
| Nous contacter | Contact us |
| Tarifs | Pricing |
| mon compte, profil | my account, profile |
| se connecter / créer un compte | log in / sign up |
| base Mérimée | Mérimée database |
