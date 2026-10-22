import { useEffect, useRef, useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { TYPES_DOSSIERS, dossierLabel } from '@/lib/document-type-meta';
import { estImage, nomDepuisFichier } from '@/lib/documents-espace';
import { projetTitre } from '@/lib/projet-titre';
import { ACCEPT_ATTR, MAX_FILE_SIZE_MB, validateFile } from '@/constants/file-types';
import { formatFichier, tailleFichier } from '@/lib/document-fichier';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { localeIntl } from '@/i18n/format';
import type { Document, DocumentType } from '@/types';
import './documents.css';

/** La pièce qu'on dépose : une pièce du référentiel (« Pièces demandées »), ou
 *  une pièce d'un dossier, qui n'a pas toujours de `pieceId` ni de dossier
 *  connu (l'utilisateur le choisit alors). */
export interface PieceAPreremplir {
  pieceId?: string;
  nom: string;
  typeDocument?: DocumentType;
  nbAides?: number;
}

interface UploadDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Appelé avec les documents fraîchement déposés (pas en mode édition). */
  onUploaded?: (docs: Document[]) => void;
  /** « Déposer : {pièce} » : dossier et nom pré-remplis, et le document créé
   *  porte le `pieceId` (c'est lui qui le fait reprendre dans les dossiers). */
  piece?: PieceAPreremplir | null;
  /** Les fichiers déjà choisis (bouton « Nouveau », glisser-déposer). */
  fichiers?: File[];
  /** Le dossier ouvert au moment du dépôt : il est présélectionné. */
  typeParDefaut?: DocumentType | null;
  /** Monuments cochés à l'ouverture (le monument affiché par la page). */
  monumentIdsParDefaut?: string[];
  /** Projets auxquels le document sera rattaché, sans choix possible ici
   *  (l'onglet Documents d'un projet, ou un monument où l'on n'est membre que
   *  d'un chantier). */
  projetIds?: string[];
  /** Mode édition : pas de fichier ni de rattachement, seulement le dossier, le
   *  nom et la note d'un document existant. */
  document?: Document | null;
  /** Appelé après l'enregistrement du mode édition. */
  onModifie?: (doc: Document) => void;
  /** Faux : pas de pilules de monuments (l'onglet d'un projet, où la pièce
   *  appartient au chantier et à lui seul). */
  choixMonuments?: boolean;
}

/** « le fichier, le dossier et le nom » ; en anglais « the file, the folder and the name ». */
function enumerer(mots: string[]): string {
  return new Intl.ListFormat(localeIntl(), { style: 'long', type: 'conjunction' }).format(mots);
}

/**
 * La fenêtre d'ajout de la maquette `monumia-documents.html` (`.ov` /
 * `.modal`) : le fichier choisi, « Dans quel dossier le ranger ? », le nom.
 * Plusieurs fichiers d'un coup : chacun garde le nom de son fichier. Deux
 * rubriques que la maquette ne montre pas et que l'application a toujours
 * eues : le rattachement aux monuments et la note. Le métier est celui
 * d'avant : validations de `constants/file-types`, dépôt par `useDocumentStore`.
 */
export function UploadDocumentDialog({
  open, onOpenChange, onUploaded, piece, fichiers: fichiersInitiaux, typeParDefaut, monumentIdsParDefaut,
  projetIds = [], document: edite, onModifie, choixMonuments = true,
}: UploadDocumentDialogProps) {
  const { t } = useTranslation(['documents', 'common']);
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const projets = useProjetStore((s) => s.projets);
  const uploadDocument = useDocumentStore((s) => s.uploadDocument);
  const updateDocument = useDocumentStore((s) => s.updateDocument);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [nom, setNom] = useState('');
  const [type, setType] = useState<DocumentType | ''>('');
  const [monumentIds, setMonumentIds] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [survol, setSurvol] = useState(false);
  const [loading, setLoading] = useState(false);

  // Une pièce demandée, c'est UN fichier : son nom est celui de la pièce.
  const plusieursPermis = !piece && !edite;
  const plusieurs = files.length > 1;

  // Un monument où l'on a un rôle d'équipe : c'est ce que la route de dépôt
  // exige (`require_project_access`, membre suffit). Un membre d'un seul
  // chantier n'en a pas, et passe par `projetIds`.
  const mesMonuments = user && choixMonuments ? monuments.filter((m) => m.myRole || m.userId === user.id) : [];
  const projetsFixes = projets.filter((p) => projetIds.includes(p.id));
  const nomMonument = (monumentId: string) => monuments.find((m) => m.id === monumentId)?.nom;

  const garder = (candidats: File[]): File[] => {
    const bons = candidats.filter((f) => {
      const err = validateFile(f);
      if (err) toast.error(t('commun.erreurDocument', { nom: f.name, message: err }));
      return !err;
    });
    return plusieursPermis ? bons : bons.slice(0, 1);
  };

  // Les valeurs d'ouverture ne se lisent qu'à l'ouverture : une mise à jour
  // du store pendant la saisie ne doit pas écraser ce qui est en cours.
  useEffect(() => {
    if (!open) return;
    const depart = garder(fichiersInitiaux ?? []);
    setFiles(depart);
    setSurvol(false);
    setNom(edite?.nom ?? piece?.nom ?? (depart.length === 1 ? nomDepuisFichier(depart[0].name) : ''));
    setType(edite?.type ?? piece?.typeDocument ?? typeParDefaut ?? '');
    setDescription(edite?.description ?? '');
    setMonumentIds(monumentIdsParDefaut ?? []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const accepter = (candidats: File[]) => {
    const bons = garder(candidats);
    if (bons.length === 0) return;
    setFiles(bons);
    if (bons.length === 1 && !nom.trim()) setNom(nomDepuisFichier(bons[0].name));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    accepter([...(e.target.files ?? [])]);
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setSurvol(false);
    accepter([...e.dataTransfer.files]);
  };

  const choisirFichier = () => fileInputRef.current?.click();

  const manque: string[] = [];
  if (!edite && files.length === 0) manque.push(t('UploadDocumentDialog.manqueFichier'));
  if (!type) manque.push(t('UploadDocumentDialog.manqueDossier'));
  if (!plusieurs && !nom.trim()) manque.push(t('UploadDocumentDialog.manqueNom'));

  const handleClose = () => {
    if (loading) return;
    onOpenChange(false);
  };

  const enregistrer = async () => {
    if (!edite || !type) return;
    setLoading(true);
    try {
      await updateDocument(edite.id, {
        nom: nom.trim(),
        type,
        // Une note vidée s'efface : la chaîne vide passe, `undefined` non.
        description: description.trim(),
      });
      toast.success(t('commun.rangeDansDossier', { dossier: dossierLabel(type) }));
      onOpenChange(false);
      onModifie?.(edite);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('UploadDocumentDialog.erreurEnregistrement'));
    } finally {
      setLoading(false);
    }
  };

  const importer = async () => {
    if (files.length === 0 || !type || !user || (!plusieurs && !nom.trim())) return;
    setLoading(true);
    const deposes: Document[] = [];
    // Un par un : le store insère chaque document en tête de liste, et une
    // erreur sur l'un n'empêche pas les autres.
    for (const file of files) {
      try {
        deposes.push(await uploadDocument(
          {
            file,
            nom: plusieurs ? nomDepuisFichier(file.name) || file.name : nom.trim(),
            type,
            monumentIds: monumentIds.length > 0 ? monumentIds : undefined,
            projetIds: projetIds.length > 0 ? projetIds : undefined,
            description: description.trim() || undefined,
            tags: [],
            pieceId: piece?.pieceId,
          },
          user.id,
        ));
      } catch (err: unknown) {
        toast.error(t('commun.erreurDocument', {
          nom: file.name,
          message: err instanceof Error ? err.message : t('UploadDocumentDialog.erreurImport'),
        }));
      }
    }
    setLoading(false);
    if (deposes.length === 0) return;
    const dossier = dossierLabel(type);
    if (files.length > 1) {
      toast.success(deposes.length === files.length
        ? t('commun.rangesDansDossier', { nombre: deposes.length, dossier })
        : t('UploadDocumentDialog.rangesPartiel', { nombre: deposes.length, total: files.length, dossier }));
    } else {
      toast.success(piece?.nbAides
        ? t('UploadDocumentDialog.rangeServira', { dossier, count: piece.nbAides })
        : t('commun.rangeDansDossier', { dossier }));
    }
    onOpenChange(false);
    // L'appelant décide de la suite : ouvrir « Gérer l'accès » (le document
    // est créé avec un défaut sûr, chef + adjoints), suivre le document…
    onUploaded?.(deposes);
  };

  const titre = edite
    ? t('UploadDocumentDialog.titreModifier')
    : piece
      ? t('UploadDocumentDialog.titreDeposer', { piece: piece.nom })
      : plusieurs
        ? t('UploadDocumentDialog.titrePlusieurs', { nombre: files.length })
        : t('UploadDocumentDialog.titreAjouter');
  const poids = files.reduce((s, f) => s + f.size, 0);
  const format = files[0] ? formatFichier(files[0].name) : '';

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <DialogPrimitive.Portal>
        <div className="ec">
          <DialogPrimitive.Overlay className="dov">
            <DialogPrimitive.Content className="dmodal" aria-describedby={undefined}>
              <div className="m-h">
                <DialogPrimitive.Title asChild><h2>{titre}</h2></DialogPrimitive.Title>
                <DialogPrimitive.Close asChild>
                  <button className="x" type="button" aria-label={t('common:actions.fermer')} disabled={loading}>
                    <Picto nom="croix" />
                  </button>
                </DialogPrimitive.Close>
              </div>

              {!edite && (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPT_ATTR}
                    multiple={plusieursPermis}
                    hidden
                    onChange={handleFileChange}
                  />
                  {files.length > 0 ? (
                    <div className="fchip">
                      <span className={`ext${estImage(format, files[0].type) ? ' img' : ''}`}>{format}</span>
                      <div>
                        <b>{files.map((f) => f.name).join(', ')}</b>
                        <small>{tailleFichier(poids)}</small>
                      </div>
                      <button type="button" onClick={choisirFichier} disabled={loading}>{t('UploadDocumentDialog.changer')}</button>
                    </div>
                  ) : (
                    <div
                      className={`dz${survol ? ' over' : ''}`}
                      onDragEnter={(e) => { e.preventDefault(); setSurvol(true); }}
                      onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
                      onDragLeave={(e) => { e.preventDefault(); setSurvol(false); }}
                      onDrop={handleDrop}
                    >
                      <p>{plusieursPermis ? t('UploadDocumentDialog.glissezFichiers') : t('UploadDocumentDialog.glissezFichier')}</p>
                      <small>{t('UploadDocumentDialog.formatsAcceptes', { taille: MAX_FILE_SIZE_MB })}</small>
                      <button className="btn b-blue b-sm" type="button" onClick={choisirFichier}>
                        {t('UploadDocumentDialog.choisirOrdinateur')}
                      </button>
                    </div>
                  )}
                </>
              )}

              <div className="fld">
                <span className="lb">{t('commun.questionDossier')}</span>
                <div className="tps">
                  {TYPES_DOSSIERS.map((tp) => (
                    <button key={tp} type="button" className="tp" aria-pressed={type === tp} onClick={() => setType(tp)}>
                      {dossierLabel(tp)}
                    </button>
                  ))}
                </div>
              </div>

              {!plusieurs && (
                <div className="fld">
                  <label htmlFor="doc-nom">{t('UploadDocumentDialog.nomDocument')}</label>
                  <input
                    id="doc-nom"
                    className="txt"
                    placeholder={t('UploadDocumentDialog.nomPlaceholder')}
                    autoComplete="off"
                    value={nom}
                    onChange={(e) => setNom(e.target.value)}
                  />
                </div>
              )}

              {!edite && (mesMonuments.length > 0 || projetsFixes.length > 0) && (
                <div className="fld">
                  <span className="lb">
                    {t('UploadDocumentDialog.rattacheA')}
                    {mesMonuments.length > 0 && <small>{t('UploadDocumentDialog.facultatif')}</small>}
                  </span>
                  {mesMonuments.length > 0 && (
                    <div className="mp">
                      {mesMonuments.map((m) => {
                        const coche = monumentIds.includes(m.id);
                        return (
                          <button
                            key={m.id}
                            type="button"
                            className="tp"
                            aria-pressed={coche}
                            onClick={() =>
                              setMonumentIds((prev) => (coche ? prev.filter((id) => id !== m.id) : [...prev, m.id]))
                            }
                          >
                            <Picto nom="coche" />{m.nom}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {projetsFixes.length > 0 && (
                    <p className="mp-note">
                      {t(
                        plusieurs
                          ? monumentIds.length > 0 ? 'UploadDocumentDialog.notePlusieursAussi' : 'UploadDocumentDialog.notePlusieurs'
                          : monumentIds.length > 0 ? 'UploadDocumentDialog.noteUnAussi' : 'UploadDocumentDialog.noteUn',
                        {
                          count: projetsFixes.length,
                          projets: enumerer(projetsFixes.map((p) => projetTitre(p, nomMonument(p.monumentId)))),
                        },
                      )}
                    </p>
                  )}
                  {monumentIds.length === 0 && projetsFixes.length === 0 && (
                    <p className="mp-note">
                      {plusieurs ? t('UploadDocumentDialog.sansMonumentPlusieurs') : t('UploadDocumentDialog.sansMonumentUn')}
                    </p>
                  )}
                </div>
              )}

              <div className="fld">
                <details className="note" open={!!edite?.description}>
                  <summary><Picto nom="plus" />{edite ? t('UploadDocumentDialog.laNote') : t('UploadDocumentDialog.ajouterNote')}</summary>
                  <textarea
                    className="area"
                    aria-label={t('UploadDocumentDialog.note')}
                    placeholder={t('UploadDocumentDialog.notePlaceholder')}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </details>
              </div>

              <div className="m-f">
                <span className="hint">
                  {loading
                    ? edite ? t('common:etats.enregistrement') : t('UploadDocumentDialog.importEnCours')
                    : manque.length ? t('UploadDocumentDialog.ilManque', { liste: enumerer(manque) }) : ''}
                </span>
                <button className="ghost" type="button" onClick={handleClose} disabled={loading}>{t('common:actions.annuler')}</button>
                <button
                  className="btn b-orange"
                  type="button"
                  disabled={manque.length > 0 || loading}
                  onClick={edite ? enregistrer : importer}
                >
                  {edite ? t('common:actions.enregistrer') : <><Picto nom="envoyer" />{t('UploadDocumentDialog.importer')}</>}
                </button>
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Overlay>
        </div>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
