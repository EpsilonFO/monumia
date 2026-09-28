import { useEffect, useRef, useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { FAMILLES_TYPES, typeLabel } from '@/lib/document-type-meta';
import { projetTitre } from '@/lib/projet-titre';
import { ACCEPT_ATTR, MAX_FILE_SIZE_MB, validateFile } from '@/constants/file-types';
import { formatFichier, tailleFichier } from '@/lib/document-fichier';
import { toast } from 'sonner';
import type { Document, DocumentType } from '@/types';
import './documents.css';

/** La pièce du référentiel qu'on dépose depuis « À déposer pour vos aides ». */
export interface PieceAPreremplir {
  pieceId: string;
  nom: string;
  typeDocument: DocumentType;
  nbAides?: number;
}

interface UploadDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Appelé avec le document fraîchement déposé (pas en mode édition). */
  onUploaded?: (doc: Document) => void;
  /** « Déposer : {pièce} » : type et nom pré-remplis, et le document créé
   *  porte le `pieceId` (c'est lui qui le fait reprendre dans les dossiers). */
  piece?: PieceAPreremplir | null;
  /** Monuments cochés à l'ouverture (le monument affiché par la page). */
  monumentIdsParDefaut?: string[];
  /** Projets auxquels le document sera rattaché, sans choix possible ici
   *  (l'onglet Documents d'un projet, ou un monument où l'on n'est membre que
   *  d'un chantier). */
  projetIds?: string[];
  /** Mode édition : pas de fichier ni de rattachement, seulement le type, le
   *  nom et la note d'un document existant. */
  document?: Document | null;
  /** Appelé après l'enregistrement du mode édition. */
  onModifie?: (doc: Document) => void;
  /** Faux : pas de pilules de monuments (l'onglet d'un projet, où la pièce
   *  appartient au chantier et à lui seul). */
  choixMonuments?: boolean;
}

/** « le fichier, le type et le nom » */
function enumerer(mots: string[]): string {
  return mots.length > 1 ? `${mots.slice(0, -1).join(', ')} et ${mots[mots.length - 1]}` : mots[0] ?? '';
}

/**
 * La fenêtre « Ajouter un document » de la maquette (`.ov` / `.modal`) :
 * 1. le fichier, 2. son type en pilules par famille, 3. son nom, une note
 * repliable, puis le rattachement aux monuments (que la maquette ne montre
 * pas, mais que l'application a toujours eu). Le métier est celui d'avant :
 * validations de `constants/file-types`, dépôt par `useDocumentStore`.
 */
export function UploadDocumentDialog({
  open, onOpenChange, onUploaded, piece, monumentIdsParDefaut, projetIds = [], document: edite, onModifie,
  choixMonuments = true,
}: UploadDocumentDialogProps) {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const projets = useProjetStore((s) => s.projets);
  const uploadDocument = useDocumentStore((s) => s.uploadDocument);
  const updateDocument = useDocumentStore((s) => s.updateDocument);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [nom, setNom] = useState('');
  const [type, setType] = useState<DocumentType | ''>('');
  const [monumentIds, setMonumentIds] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [survol, setSurvol] = useState(false);
  const [loading, setLoading] = useState(false);

  // Un monument où l'on a un rôle d'équipe : c'est ce que la route de dépôt
  // exige (`require_project_access`, membre suffit). Un membre d'un seul
  // chantier n'en a pas, et passe par `projetIds`.
  const mesMonuments = user && choixMonuments ? monuments.filter((m) => m.myRole || m.userId === user.id) : [];
  const projetsFixes = projets.filter((p) => projetIds.includes(p.id));

  // Les valeurs d'ouverture ne se lisent qu'à l'ouverture : une mise à jour
  // du store pendant la saisie ne doit pas écraser ce qui est en cours.
  useEffect(() => {
    if (!open) return;
    setFile(null);
    setSurvol(false);
    setNom(edite?.nom ?? piece?.nom ?? '');
    setType(edite?.type ?? piece?.typeDocument ?? '');
    setDescription(edite?.description ?? '');
    setMonumentIds(monumentIdsParDefaut ?? []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const acceptFile = (candidate: File) => {
    const err = validateFile(candidate);
    if (err) {
      toast.error(err);
      return;
    }
    setFile(candidate);
    if (!nom.trim()) {
      setNom(candidate.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) acceptFile(selected);
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setSurvol(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) acceptFile(dropped);
  };

  const choisirFichier = () => fileInputRef.current?.click();

  const manque: string[] = [];
  if (!edite && !file) manque.push('le fichier');
  if (!type) manque.push('le type');
  if (!nom.trim()) manque.push('le nom');

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
      toast.success(`Rangé dans ${typeLabel(type)}.`);
      onOpenChange(false);
      onModifie?.(edite);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    } finally {
      setLoading(false);
    }
  };

  const importer = async () => {
    if (!file || !nom.trim() || !type || !user) return;
    setLoading(true);
    try {
      const doc = await uploadDocument(
        {
          file,
          nom: nom.trim(),
          type,
          monumentIds: monumentIds.length > 0 ? monumentIds : undefined,
          projetIds: projetIds.length > 0 ? projetIds : undefined,
          description: description.trim() || undefined,
          tags: [],
          pieceId: piece?.pieceId,
        },
        user.id,
      );
      toast.success(
        piece?.nbAides
          ? `Rangé dans ${typeLabel(type)}. Il servira à ${piece.nbAides} aide${piece.nbAides > 1 ? 's' : ''}.`
          : `Rangé dans ${typeLabel(type)}.`,
      );
      setLoading(false);
      onOpenChange(false);
      // L'appelant décide de la suite : ouvrir « Gérer l'accès » (le document
      // est créé avec un défaut sûr, chef + adjoints), suivre le document…
      onUploaded?.(doc);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur lors de l'import");
      setLoading(false);
    }
  };

  const titre = edite ? 'Modifier le document' : piece ? `Déposer : ${piece.nom}` : 'Ajouter un document';
  const sousTitre = edite
    ? 'Son type, son nom et sa note.'
    : piece
      ? "Le type et le nom sont déjà remplis. Il ne reste qu'à choisir le fichier."
      : 'Trois informations, et il sera rangé au bon endroit.';

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <DialogPrimitive.Portal>
        <div className="ec">
          <DialogPrimitive.Overlay className="dov">
            <DialogPrimitive.Content className="dmodal">
              <div className="m-h">
                <div>
                  <DialogPrimitive.Title asChild><h2>{titre}</h2></DialogPrimitive.Title>
                  <DialogPrimitive.Description asChild><p>{sousTitre}</p></DialogPrimitive.Description>
                </div>
                <DialogPrimitive.Close asChild>
                  <button className="x" type="button" aria-label="Fermer" disabled={loading}>
                    <Picto nom="croix" />
                  </button>
                </DialogPrimitive.Close>
              </div>

              {!edite && (
                <div className="fld">
                  <span className="lb">1. Le fichier</span>
                  <input ref={fileInputRef} type="file" accept={ACCEPT_ATTR} hidden onChange={handleFileChange} />
                  {file ? (
                    <div className="file">
                      <span className="dft">{formatFichier(file.name)}</span>
                      <div>
                        <b>{file.name}</b>
                        <small>{tailleFichier(file.size)}</small>
                      </div>
                      <button type="button" onClick={choisirFichier}>Changer</button>
                    </div>
                  ) : (
                    <div
                      className={`dz${survol ? ' over' : ''}`}
                      onDragEnter={(e) => { e.preventDefault(); setSurvol(true); }}
                      onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
                      onDragLeave={(e) => { e.preventDefault(); setSurvol(false); }}
                      onDrop={handleDrop}
                    >
                      <p>Glissez le fichier ici</p>
                      <small>PDF, photo, Word, Excel ou CSV, jusqu'à {MAX_FILE_SIZE_MB} Mo</small>
                      <button className="btn b-blue b-sm" type="button" onClick={choisirFichier}>
                        Choisir sur l'ordinateur
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="fld">
                <span className="lb">{edite ? '1' : '2'}. Qu'est-ce que c'est ?</span>
                <div className="tg">
                  {FAMILLES_TYPES.map((f) => (
                    <div key={f.nom}>
                      <div className="fl">{f.nom}</div>
                      <div className="tps">
                        {f.types.map((t) => (
                          <button
                            key={t}
                            type="button"
                            className="tp"
                            aria-pressed={type === t}
                            onClick={() => setType(t)}
                          >
                            {typeLabel(t)}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="fld">
                <label htmlFor="doc-nom">{edite ? '2' : '3'}. Son nom</label>
                <input
                  id="doc-nom"
                  className="txt"
                  placeholder="Ex. : Devis restauration toiture"
                  autoComplete="off"
                  value={nom}
                  onChange={(e) => setNom(e.target.value)}
                />
              </div>

              {!edite && (mesMonuments.length > 0 || projetsFixes.length > 0) && (
                <div className="fld">
                  <span className="lb">Rattaché à{mesMonuments.length > 0 && <small>facultatif</small>}</span>
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
                      Il sera {monumentIds.length > 0 ? 'aussi ' : ''}rattaché{' '}
                      {projetsFixes.length > 1 ? 'aux projets' : 'au projet'}{' '}
                      {enumerer(projetsFixes.map(projetTitre))}.
                    </p>
                  )}
                  {monumentIds.length === 0 && projetsFixes.length === 0 && (
                    <p className="mp-note">Sans monument, il reste un document personnel.</p>
                  )}
                </div>
              )}

              <div className="fld">
                <details className="note" open={!!edite?.description}>
                  <summary><Picto nom="plus" />{edite ? 'La note' : 'Ajouter une note'}</summary>
                  <textarea
                    className="area"
                    aria-label="Note"
                    placeholder="Ex. : devis de l'entreprise Martin, reçu le 12 septembre"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </details>
              </div>

              <div className="m-f">
                <span className="hint">
                  {loading
                    ? edite ? 'Enregistrement…' : 'Import en cours…'
                    : manque.length ? `Il manque ${enumerer(manque)}.` : 'Tout est prêt.'}
                </span>
                <button className="ghost" type="button" onClick={handleClose} disabled={loading}>Annuler</button>
                <button
                  className="btn b-orange"
                  type="button"
                  disabled={manque.length > 0 || loading}
                  onClick={edite ? enregistrer : importer}
                >
                  {edite ? 'Enregistrer' : <><Picto nom="envoyer" />Importer</>}
                </button>
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Overlay>
        </div>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
