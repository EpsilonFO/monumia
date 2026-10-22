import { useEffect, useMemo, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { ACCEPT_ATTR, MAX_FILE_SIZE_MB, validateFile } from '@/constants/file-types';
import { TYPES_DOSSIERS, dossierLabel } from '@/lib/document-type-meta';
import { formatFichier, tailleFichier } from '@/lib/document-fichier';
import { estImage, nomDepuisFichier } from '@/lib/documents-espace';
import { toast } from 'sonner';
import type { Document, DocumentType } from '@/types';
import '@/components/document/documents.css';

interface AttachDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Monument de rattachement (fiche du bien) : pré-filtre la liste et marque
   *  les dépôts. Ignoré si `projetId` est fourni. */
  monumentId?: string;
  /** Projet de travaux de rattachement. Quand il est là, il PRIME : la pièce
   *  déposée appartient au chantier, pas au monument — c'est ce qui la garde
   *  hors de vue de qui n'est pas sur ce chantier. */
  projetId?: string;
  /** Nom proposé pour un nouveau fichier (le libellé de la pièce du dossier).
   *  Il sert aussi de sous-titre : « Pour la pièce … ». */
  defaultName?: string;
  /** Pièce du référentiel que le nouveau fichier incarne : il la porte, et les
   *  autres dossiers pourront le reprendre. */
  pieceId?: string;
  /** Dossier présélectionné pour un nouveau fichier. */
  typeParDefaut?: DocumentType | null;
  /** Called with the chosen document (either existing or freshly uploaded). */
  onAttach: (document: Document) => Promise<void> | void;
  /** Called only after a FRESH upload (pas la sélection d'un doc existant) —
   *  pour ouvrir le popup « Gérer l'accès » sur la pièce déposée. */
  onUploaded?: (document: Document) => void;
  /** Version courte de la page d'un dossier (« Choisir dans mes documents ») :
   *  la seule liste de ses documents, sans dépôt dans la fenêtre. Le lien du
   *  pied appelle `onImporter`, qui ouvre le dépôt habituel. */
  choixSeul?: boolean;
  onImporter?: () => void;
}

/**
 * « Joindre un document » : choisir parmi ceux qu'on voit déjà (Mes documents),
 * ou importer un nouveau fichier. Même habillage que la fenêtre d'ajout
 * (`UploadDocumentDialog`, `.dmodal`) ; le métier est celui d'avant.
 */
export function AttachDocumentDialog({
  open,
  onOpenChange,
  monumentId,
  projetId,
  defaultName,
  pieceId,
  typeParDefaut,
  onAttach,
  onUploaded,
  choixSeul = false,
  onImporter,
}: AttachDocumentDialogProps) {
  const { t } = useTranslation(['dossier', 'common']);
  const user = useAuthStore((s) => s.user);
  const { documents, loading, fetchDocuments, uploadDocument } = useDocumentStore();

  const [search, setSearch] = useState('');
  // Par défaut on montre TOUS les documents de l'utilisateur (pas seulement ceux
  // déjà sur ce monument) : on peut ainsi rattacher un doc de « Mes documents ».
  const [scope, setScope] = useState<'monument' | 'all'>('all');
  const [attachingId, setAttachingId] = useState<string | null>(null);

  // Nouveau fichier
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [nom, setNom] = useState('');
  const [type, setType] = useState<DocumentType | ''>('');
  const [description, setDescription] = useState('');
  const [survol, setSurvol] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (open) {
      fetchDocuments();
      setSearch('');
      setScope('all');
      setFile(null);
      setNom(defaultName ?? '');
      setType(typeParDefaut ?? '');
      setDescription('');
      setSurvol(false);
    }
    // Lus à l'ouverture seulement : une mise à jour du store pendant la saisie
    // ne doit pas écraser ce qui est en cours.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const filtered = useMemo(() => {
    let docs = documents;
    if (scope === 'monument') {
      // « Ce périmètre uniquement » : le chantier s'il y en a un, sinon le bien.
      if (projetId) docs = docs.filter((d) => d.projetIds.includes(projetId));
      else if (monumentId) docs = docs.filter((d) => d.monumentIds.includes(monumentId));
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      docs = docs.filter(
        (d) =>
          d.nom.toLowerCase().includes(q) ||
          d.nomFichier.toLowerCase().includes(q) ||
          d.tags.some((tag) => tag.toLowerCase().includes(q)),
      );
    }
    return docs;
  }, [documents, scope, monumentId, projetId, search]);

  const occupe = uploading || !!attachingId;

  const handleSelectExisting = async (doc: Document) => {
    setAttachingId(doc.id);
    try {
      await onAttach(doc);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('AttachDocumentDialog.erreurSelection'));
    } finally {
      setAttachingId(null);
    }
  };

  const acceptFile = (candidate: File) => {
    const err = validateFile(candidate);
    if (err) {
      toast.error(err);
      return;
    }
    setFile(candidate);
    if (!nom.trim()) setNom(nomDepuisFichier(candidate.name));
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

  const handleUpload = async () => {
    if (!file || !nom.trim() || !type || !user) return;
    setUploading(true);
    try {
      const doc = await uploadDocument(
        {
          file,
          nom: nom.trim(),
          type,
          // Le projet prime : déposer une pièce depuis un chantier ne doit pas
          // la rattacher au monument, où toute son équipe la verrait.
          monumentIds: projetId ? undefined : monumentId ? [monumentId] : undefined,
          projetIds: projetId ? [projetId] : undefined,
          description: description.trim() || undefined,
          tags: [],
          pieceId,
        },
        user.id,
      );
      await onAttach(doc);
      onUploaded?.(doc);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('AttachDocumentDialog.erreurImport'));
    } finally {
      setUploading(false);
    }
  };

  // Ce qui manque pour importer, dans l'ordre des champs (dossier, puis nom).
  const manque = !type && !nom.trim()
    ? t('AttachDocumentDialog.manqueDossierEtNom')
    : !type
      ? t('AttachDocumentDialog.manqueDossier')
      : !nom.trim()
        ? t('AttachDocumentDialog.manqueNom')
        : null;
  const format = file ? formatFichier(file.name) : '';

  if (choixSeul) {
    return (
      <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o && !occupe) onOpenChange(false); }}>
        <DialogPrimitive.Portal>
          <div className="ec">
            <DialogPrimitive.Overlay className="dov">
              <DialogPrimitive.Content className="dmodal pdos-choix" aria-describedby={undefined}>
                <div className="m-h">
                  <div>
                    <DialogPrimitive.Title asChild><h2>{t('AttachDocumentDialog.choisirTitre')}</h2></DialogPrimitive.Title>
                    {defaultName && <p className="m-sub">{defaultName}</p>}
                  </div>
                  <DialogPrimitive.Close asChild>
                    <button className="x" type="button" aria-label={t('common:actions.fermer')} disabled={occupe}>
                      <Picto nom="croix" />
                    </button>
                  </DialogPrimitive.Close>
                </div>

                {documents.length > 5 && (
                  <label className="jsearch">
                    <span className="sr">{t('AttachDocumentDialog.rechercher')}</span>
                    <Picto nom="loupe" />
                    <input
                      type="search"
                      placeholder={t('AttachDocumentDialog.rechercher')}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                )}
                <div className="docs">
                  {loading && documents.length === 0 ? (
                    <p className="jvide">{t('AttachDocumentDialog.chargement')}</p>
                  ) : filtered.length === 0 ? (
                    <p className="jvide">
                      {search.trim() ? t('AttachDocumentDialog.aucunTrouve') : t('AttachDocumentDialog.aucunDocument')}
                    </p>
                  ) : (
                    filtered.map((doc) => {
                      const fmt = formatFichier(doc.nomFichier);
                      return (
                        <button
                          key={doc.id}
                          type="button"
                          className="doc"
                          disabled={occupe}
                          onClick={() => handleSelectExisting(doc)}
                        >
                          <span className={`ext${estImage(fmt, doc.mimeType) ? ' img' : ''}`}>{fmt}</span>
                          <span className="jnom">
                            <b>{doc.nom}</b>
                            <small>
                              {attachingId === doc.id ? t('AttachDocumentDialog.ajout') : `${dossierLabel(doc.type)} · ${tailleFichier(doc.tailleFichier)}`}
                            </small>
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
                {onImporter && (
                  <div className="m-f">
                    <Trans
                      t={t}
                      i18nKey="AttachDocumentDialog.absent"
                      components={{
                        bouton: (
                          <button
                            className="rm"
                            type="button"
                            disabled={occupe}
                            onClick={() => { onOpenChange(false); onImporter(); }}
                          />
                        ),
                      }}
                    />
                  </div>
                )}
              </DialogPrimitive.Content>
            </DialogPrimitive.Overlay>
          </div>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    );
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o && !occupe) onOpenChange(false); }}>
      <DialogPrimitive.Portal>
        <div className="ec">
          <DialogPrimitive.Overlay className="dov">
            <DialogPrimitive.Content className="dmodal" aria-describedby={undefined}>
              <div className="m-h">
                <div>
                  <DialogPrimitive.Title asChild><h2>{t('AttachDocumentDialog.joindreTitre')}</h2></DialogPrimitive.Title>
                  <p className="m-sub">
                    {defaultName
                      ? t('AttachDocumentDialog.sousTitrePiece', { piece: defaultName })
                      : t('AttachDocumentDialog.sousTitre')}
                  </p>
                </div>
                <DialogPrimitive.Close asChild>
                  <button className="x" type="button" aria-label={t('common:actions.fermer')} disabled={occupe}>
                    <Picto nom="croix" />
                  </button>
                </DialogPrimitive.Close>
              </div>

              <div className="fld">
                <span className="lb">{t('AttachDocumentDialog.vosDocuments')}</span>
                <label className="jsearch">
                  <span className="sr">{t('AttachDocumentDialog.rechercher')}</span>
                  <Picto nom="loupe" />
                  <input
                    type="search"
                    placeholder={t('AttachDocumentDialog.rechercher')}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                {(projetId || monumentId) && (
                  <div className="tps jscope">
                    <button type="button" className="tp" aria-pressed={scope === 'all'} onClick={() => setScope('all')}>
                      {t('AttachDocumentDialog.tousMesDocuments')}
                    </button>
                    <button type="button" className="tp" aria-pressed={scope === 'monument'} onClick={() => setScope('monument')}>
                      {projetId ? t('AttachDocumentDialog.ceProjet') : t('AttachDocumentDialog.ceMonument')}
                    </button>
                  </div>
                )}
                <div className="jlist">
                  {loading ? (
                    <p className="jvide">{t('AttachDocumentDialog.chargement')}</p>
                  ) : filtered.length === 0 ? (
                    <p className="jvide">
                      {search.trim() ? t('AttachDocumentDialog.aucunTrouve') : t('AttachDocumentDialog.aucunDocumentImporter')}
                    </p>
                  ) : (
                    filtered.map((doc) => {
                      const fmt = formatFichier(doc.nomFichier);
                      return (
                        <button
                          key={doc.id}
                          type="button"
                          className="jrow"
                          disabled={occupe}
                          onClick={() => handleSelectExisting(doc)}
                        >
                          <span className={`ext${estImage(fmt, doc.mimeType) ? ' img' : ''}`}>{fmt}</span>
                          <span className="jnom">
                            <b>{doc.nom}</b>
                            <small>{dossierLabel(doc.type)} · {tailleFichier(doc.tailleFichier)}</small>
                          </span>
                          <span className="jgo">{attachingId === doc.id ? t('AttachDocumentDialog.ajout') : t('AttachDocumentDialog.choisir')}</span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

              <div className="fld">
                <span className="lb">{t('AttachDocumentDialog.nouveauFichier')}</span>
                <input ref={fileInputRef} type="file" accept={ACCEPT_ATTR} hidden onChange={handleFileChange} />
                {file ? (
                  <>
                    <div className="fchip">
                      <span className={`ext${estImage(format, file.type) ? ' img' : ''}`}>{format}</span>
                      <div>
                        <b>{file.name}</b>
                        <small>{tailleFichier(file.size)}</small>
                      </div>
                      <button type="button" onClick={() => fileInputRef.current?.click()} disabled={occupe}>{t('AttachDocumentDialog.changer')}</button>
                    </div>
                    <div className="fld">
                      <span className="lb">{t('AttachDocumentDialog.quelDossier')}</span>
                      <div className="tps">
                        {TYPES_DOSSIERS.map((td) => (
                          <button key={td} type="button" className="tp" aria-pressed={type === td} onClick={() => setType(td)}>
                            {dossierLabel(td)}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="fld">
                      <label htmlFor="joindre-nom">{t('AttachDocumentDialog.nomDocument')}</label>
                      <input
                        id="joindre-nom"
                        className="txt"
                        placeholder={t('AttachDocumentDialog.nomPlaceholder')}
                        autoComplete="off"
                        value={nom}
                        onChange={(e) => setNom(e.target.value)}
                      />
                    </div>
                    <div className="fld">
                      <details className="note">
                        <summary><Picto nom="plus" />{t('AttachDocumentDialog.ajouterNote')}</summary>
                        <textarea
                          className="area"
                          aria-label={t('AttachDocumentDialog.note')}
                          placeholder={t('AttachDocumentDialog.notePlaceholder')}
                          value={description}
                          onChange={(e) => setDescription(e.target.value)}
                        />
                      </details>
                    </div>
                  </>
                ) : (
                  <div
                    className={`dz jdz${survol ? ' over' : ''}`}
                    onDragEnter={(e) => { e.preventDefault(); setSurvol(true); }}
                    onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
                    onDragLeave={(e) => { e.preventDefault(); setSurvol(false); }}
                    onDrop={handleDrop}
                  >
                    <p>{t('AttachDocumentDialog.glisser')}</p>
                    <small>{t('AttachDocumentDialog.formats', { taille: MAX_FILE_SIZE_MB })}</small>
                    <button className="btn b-line b-sm" type="button" onClick={() => fileInputRef.current?.click()}>
                      {t('AttachDocumentDialog.choisirOrdinateur')}
                    </button>
                  </div>
                )}
              </div>

              <div className="m-f">
                <span className="hint">
                  {uploading ? t('AttachDocumentDialog.importEnCours') : file && manque ? manque : ''}
                </span>
                <button className="ghost" type="button" onClick={() => onOpenChange(false)} disabled={occupe}>
                  {file ? t('common:actions.annuler') : t('common:actions.fermer')}
                </button>
                {file && (
                  <button
                    className="btn b-orange"
                    type="button"
                    disabled={!!manque || occupe}
                    onClick={handleUpload}
                  >
                    <Picto nom="envoyer" />{t('AttachDocumentDialog.importerEtJoindre')}
                  </button>
                )}
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Overlay>
        </div>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
