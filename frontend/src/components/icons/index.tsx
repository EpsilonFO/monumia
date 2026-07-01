import type { ComponentType, SVGProps } from 'react';
import {
  Archive,
  ArrowSquareOut,
  ArrowsClockwise,
  Bank,
  Bell,
  BookOpen,
  CalendarBlank,
  CalendarCheck,
  CheckCircle,
  Clock,
  Coins,
  Compass,
  DownloadSimple,
  Envelope,
  Eye,
  FileText,
  FileX,
  Files,
  FloppyDisk,
  Folder,
  FolderMinus,
  FolderOpen,
  FolderPlus,
  Gauge,
  GearSix,
  Globe,
  HandCoins,
  HardHat,
  House,
  Image,
  Info,
  Key,
  Layout,
  Lightbulb,
  ListChecks,
  Lock,
  MagnifyingGlass,
  MapPin,
  Notebook,
  PencilSimple,
  Plus,
  Question,
  Quotes,
  Receipt,
  Scales,
  Scroll,
  SealCheck,
  ShieldCheck,
  SignOut,
  SquaresFour,
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

/**
 * Banque d'icônes Monumia — adossée à Phosphor (https://phosphoricons.com).
 *
 * Le site n'importe QUE depuis ce fichier, sous des noms métier
 * (`IconNotification`, `IconAide`…). Pour changer de style d'icônes partout :
 * ajuster `WEIGHT` (graisse) ci-dessous, ou re-pointer un `Icon*` vers une autre
 * icône Phosphor — sur une seule ligne, sans toucher au reste du code.
 */

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'strokeWidth'> & {
  size?: number;
  strokeWidth?: number;
};

export type IconComponent = ComponentType<IconProps>;

/** Graisse Phosphor appliquée à toute la banque. Options : thin/light/regular/bold/fill/duotone. */
const WEIGHT: IconWeight = 'bold';

/** Enveloppe une icône Phosphor : graisse imposée + taille par défaut cohérente (surchargée par size/className). */
function icon(PhIcon: PhosphorIcon): IconComponent {
  function IconWrapper({ size = 20, ...props }: IconProps) {
    return <PhIcon weight={WEIGHT} size={size} {...props} />;
  }
  return IconWrapper;
}

/* Navigation / cœur */
export const IconDashboard = icon(SquaresFour);
export const IconMonument = icon(Bank);
export const IconDocuments = icon(Files);
export const IconDossier = icon(Folder);
export const IconNotification = icon(Bell);
export const IconReglages = icon(GearSix);
export const IconTelecharger = icon(DownloadSimple);
export const IconAccount = icon(User);
export const IconCompte = IconAccount;
export const IconHelp = icon(Question);
export const IconAgenda = icon(Notebook);
export const IconDeconnexion = icon(SignOut);

/* Documents */
export const IconDocument = icon(FileText);
export const IconDocumentValide = icon(SealCheck);
export const IconDocumentAlerte = icon(FileX);
export const IconArchive = icon(Archive);
export const IconDevis = icon(Receipt);
export const IconDossierOuvert = icon(FolderOpen);
export const IconAjouterDossier = icon(FolderPlus);
export const IconRetirerDossier = icon(FolderMinus);
export const IconDepot = icon(UploadSimple);
export const IconModele = icon(Layout);

/* Aides / finances */
export const IconAide = icon(HandCoins);
export const IconSubvention = icon(Coins);
export const IconTendance = icon(TrendUp);
export const IconAccompagnement = icon(Lightbulb);

/* Patrimoine / protection */
export const IconProtection = icon(ShieldCheck);
export const IconDiagnostic = icon(Compass);
export const IconLocalisation = icon(MapPin);
export const IconSuivi = icon(Gauge);

/* Temps */
export const IconCalendrier = icon(CalendarBlank);
export const IconEcheance = icon(CalendarCheck);
export const IconTemps = icon(Clock);

/* BTP / artisans */
export const IconChantier = icon(HardHat);
export const IconProspect = icon(Target);
export const IconContact = icon(Envelope);
export const IconEquipe = icon(Users);

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
export const IconRafraichir = icon(ArrowsClockwise);
export const IconAjouter = icon(Plus);
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
