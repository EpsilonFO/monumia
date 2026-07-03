import {
  Archive,
  ArrowSquareOut,
  ArrowsClockwise,
  Bank,
  Bell,
  Blueprint,
  BookOpen,
  CalendarBlank,
  CalendarCheck,
  CalendarDots,
  ChatsCircle,
  CheckCircle,
  Clock,
  Coins,
  Compass,
  DownloadSimple,
  Envelope,
  EnvelopeOpen,
  Eye,
  FileText,
  FileX,
  Files,
  FloppyDisk,
  Folder,
  FolderMinus,
  FolderOpen,
  FolderPlus,
  GearSix,
  Globe,
  HandCoins,
  HardHat,
  House,
  IdentificationCard,
  Image,
  Info,
  Key,
  Lightbulb,
  ListChecks,
  ListNumbers,
  Lock,
  MagnifyingGlass,
  MapPin,
  MapTrifold,
  PencilSimple,
  Path,
  Phone,
  Plus,
  Question,
  Quotes,
  Receipt,
  Scales,
  Scroll,
  SealCheck,
  ShieldCheck,
  SignOut,
  Signpost,
  SquaresFour,
  Stamp,
  Target,
  TrendUp,
  Trash,
  UploadSimple,
  User,
  Users,
  Warning,
  XCircle,
  type Icon as PhosphorIcon,
  type IconWeight,
} from '@phosphor-icons/react';
import type { IconComponent, IconProps } from './types';

/**
 * Banque d'icônes Monumia — adossée à Phosphor (https://phosphoricons.com),
 * plus les icônes propres à la marque (`./monumia.tsx` : monument à rosace
 * quadrilobe, tracés fait-main du fondateur).
 *
 * Le site n'importe QUE depuis ce fichier, sous des noms métier
 * (`IconNotification`, `IconAide`…). Un concept = une icône :
 * l'aide financière est TOUJOURS `IconAide`, le conseil `IconConseil`,
 * l'organisme qui verse `IconInstitution`… Pour changer un glyphe partout :
 * re-pointer une seule ligne ici, sans toucher au reste du code.
 */

export type { IconComponent, IconProps } from './types';
export {
  IconMonument,
  IconProjet,
  IconClocheMonumia,
  IconEcrouMonumia,
  IconTelechargementMonumia,
} from './monumia';

/** Graisse Phosphor appliquée à toute la banque. Options : thin/light/regular/bold/fill/duotone. */
const WEIGHT: IconWeight = 'duotone';

/** Enveloppe une icône Phosphor : graisse imposée par défaut, surchargeable via `weight`.
 * `defaultWeight` permet d'imposer une autre graisse à une icône précise (ex. le
 * duotone salit les glyphes « pleins » comme le téléchargement → bold). */
function icon(PhIcon: PhosphorIcon, defaultWeight: IconWeight = WEIGHT): IconComponent {
  function IconWrapper({ size = 20, weight = defaultWeight, ...props }: IconProps) {
    return <PhIcon weight={weight} size={size} {...props} />;
  }
  return IconWrapper;
}

/* Navigation / cœur — IconMonument (façade à rosace quadrilobe) vient de ./monumia */
export const IconDashboard = icon(SquaresFour);
export const IconDocuments = icon(Files);
export const IconDossier = icon(Folder);
export const IconNotification = icon(Bell);
export const IconReglages = icon(GearSix);
export const IconTelecharger = icon(DownloadSimple, 'bold');
export const IconAccount = icon(User);
export const IconCompte = IconAccount;
export const IconHelp = icon(Question);
export const IconAgenda = icon(CalendarDots);
export const IconDeconnexion = icon(SignOut);

/* Documents */
export const IconDocument = icon(FileText);
export const IconDocumentValide = icon(SealCheck);
export const IconDocumentAlerte = icon(FileX);
export const IconArchive = icon(Archive);
export const IconDevis = icon(Receipt);
export const IconPlan = icon(Blueprint);
export const IconCadastre = icon(MapTrifold);
export const IconCourrier = icon(EnvelopeOpen);
export const IconDossierOuvert = icon(FolderOpen);
export const IconAjouterDossier = icon(FolderPlus);
export const IconRetirerDossier = icon(FolderMinus);
export const IconDepot = icon(UploadSimple);
export const IconModele = icon(Stamp);

/* Aides / finances — l'aide financière a UNE icône : la main aux pièces */
export const IconAide = icon(HandCoins);
export const IconSubvention = icon(Coins);
export const IconTendance = icon(TrendUp);
export const IconInstitution = icon(Bank);
/** Guidage / être accompagné sur le chemin (panneau indicateur). */
export const IconAccompagnement = icon(Signpost);
/** Astuce, bon conseil (ampoule) — distinct de l'accompagnement. */
export const IconConseil = icon(Lightbulb);
/** Étapes d'une démarche (liste numérotée). */
export const IconEtapes = icon(ListNumbers);

/* Patrimoine / protection */
/** Fiche descriptive du monument (carte d'identité) — distincte d'IconMonument (le projet). */
export const IconFiche = icon(IdentificationCard);
export const IconProtection = icon(ShieldCheck);
export const IconDiagnostic = icon(Compass);
export const IconLocalisation = icon(MapPin);
export const IconSuivi = icon(Path);

/* Temps */
export const IconCalendrier = icon(CalendarBlank);
export const IconEcheance = icon(CalendarCheck);
export const IconTemps = icon(Clock);

/* BTP / artisans */
export const IconChantier = icon(HardHat);
export const IconProspect = icon(Target);
export const IconContact = icon(Envelope);
export const IconTelephone = icon(Phone);
export const IconEquipe = icon(Users);
export const IconDiscussion = icon(ChatsCircle);

/* Statuts */
export const IconSucces = icon(CheckCircle);
export const IconAttention = icon(Warning);
export const IconErreur = icon(XCircle);
export const IconInfo = icon(Info);
export const IconVerrou = icon(Lock);
export const IconPublic = icon(Globe);

/* Actions */
export const IconRecherche = icon(MagnifyingGlass);
export const IconModifier = icon(PencilSimple);
export const IconSupprimer = icon(Trash);
export const IconVoir = icon(Eye);
export const IconRafraichir = icon(ArrowsClockwise, 'bold');
export const IconAjouter = icon(Plus, 'bold');
export const IconLienExterne = icon(ArrowSquareOut);

/* Divers */
export const IconRegle = icon(Scales);
export const IconLivre = icon(BookOpen);
export const IconCle = icon(Key);
export const IconEnregistrer = icon(FloppyDisk);
export const IconMaison = icon(House);
export const IconImage = icon(Image);
export const IconListe = icon(ListChecks);
export const IconCitation = icon(Quotes);
export const IconParchemin = icon(Scroll);
