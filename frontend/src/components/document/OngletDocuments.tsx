import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Picto } from '@/components/shared/ecrans/Picto';
import { LigneDocument } from '@/components/document/LigneDocument';
import { PiecesADeposer } from '@/components/document/PiecesADeposer';
import { UploadDocumentDialog, type PieceAPreremplir } from '@/components/document/UploadDocumentDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { usePiecesADeposer } from '@/hooks/usePiecesADeposer';
import { actionsDocument, type IciDocument } from '@/lib/actions-document';
import { nbAidesParPiece } from '@/lib/pieces-a-deposer';
import { projetTitre } from '@/lib/projet-titre';
import { documentService } from '@/services/document.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import type { Document, ProjectRole } from '@/types';
import './documents.css';

export interface OngletDocumentsProps {
  /** Le monument ou le projet dont c'est l'onglet. */
  ici: IciDocument;
  /** Le monument parent (le monument lui-même, côté monument). */
  monumentId: string;
  /** La liste de l'onglet, chargée par la page (`documentService.getAll`). */
  documents: Document[];
  /** Relire cette liste après un dépôt, un rattachement, un retrait… */
  onChange: () => void;
  /** Le rôle qui gouverne l'onglet : `Monument.myRole` ou `Projet.myRole`. */
  role: ProjectRole | null;
  auteurs?: Record<string, string>;
  dossierNames?: Record<string, string>;
  /** Une phrase sous « Vos documents ». */
  intro?: string;
  /** Le texte du bloc vide. */
  vide: string;
}

/**
 * L'onglet Documents d'un monument ou d'un projet, au dessin de Mes documents :
 * « À déposer pour vos aides », puis la liste, avec le même menu ⋮.
 *
 * Deux règles viennent du périmètre et nulle part ailleurs :
 *  - côté PROJET, un document déposé pend au chantier et à lui seul (pas de
 *    choix de monument dans la fenêtre d'ajout) : le déposer ici ne doit pas
 *    l'exposer à l'équipe du bien au-delà de ce qu'elle voit déjà ;
 *  - côté MONUMENT, il pend au monument, coché par défaut.
 */
export function OngletDocuments({
  ici, monumentId, documents, onChange, role, auteurs = {}, dossierNames = {}, intro, vide,
}: OngletDocumentsProps) {
  const userId = useAuthStore((s) => s.user?.id);
  const projets = useProjetStore((s) => s.projets);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const trashDocument = useDocumentStore((s) => s.trashDocument);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [piece, setPiece] = useState<PieceAPreremplir | null>(null);
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [attachOpen, setAttachOpen] = useState(false);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [nouveauId, setNouveauId] = useState<string | null>(null);

  // Le store « mes documents » sert à savoir quelles pièces sont déjà là : la
  // liste de l'onglet ne voit que son périmètre (celle d'un monument n'a pas
  // les pièces de ses projets).
  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  useEffect(() => {
    if (!nouveauId) return;
    const t = setTimeout(() => setNouveauId(null), 1600);
    return () => clearTimeout(t);
  }, [nouveauId]);

  const coteProjet = ici.type === 'projet';
  const projetIds = coteProjet ? [ici.id] : undefined;
  const { pieces } = usePiecesADeposer(monumentId, projetIds, documents);
  const aidesParPiece = useMemo(() => nbAidesParPiece(pieces), [pieces]);
  const projetsById = useMemo(() => new Map(projets.map((p) => [p.id, p])), [projets]);

  const relire = () => {
    onChange();
    fetchDocuments();
  };

  const ouvrirAjout = (p: PieceAPreremplir | null) => {
    setPiece(p);
    setEditDoc(null);
    setUploadOpen(true);
  };

  const corbeille = async (d: Document) => {
    if (!confirm(`Mettre "${d.nom}" à la corbeille ?`)) return;
    try { await trashDocument(d.id); onChange(); toast.success('Document mis à la corbeille'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const retirer = async (d: Document, lieu: IciDocument) => {
    try {
      if (lieu.type === 'projet') await documentService.removeFromProjet(d.id, lieu.id);
      else await documentService.removeFromProject(d.id, lieu.id);
      relire();
      toast.success(lieu.type === 'projet' ? 'Document retiré du projet' : 'Document retiré du monument');
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };

  // Joindre un document EXISTANT (AttachDocumentDialog) : on le rattache au
  // périmètre de l'onglet s'il n'y pend pas déjà. Relancer l'erreur : la
  // fenêtre s'en sert pour rester ouverte.
  const joindre = async (doc: Document) => {
    try {
      if (coteProjet && !doc.projetIds.includes(ici.id)) {
        await documentService.addToProjects(doc.id, [], [ici.id]);
      } else if (!coteProjet && !doc.monumentIds.includes(ici.id)) {
        await documentService.addToProjects(doc.id, [ici.id]);
      }
      relire();
      toast.success(coteProjet ? 'Document ajouté au projet' : 'Document ajouté au monument');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur lors de l'ajout");
      throw err;
    }
  };

  const apresDepot = (doc: Document) => {
    setNouveauId(doc.id);
    onChange();
    // Créé avec un défaut sûr (chef + adjoints) : « Gérer l'accès » s'ouvre
    // aussitôt pour que l'auteur choisisse qui peut le voir.
    if (doc.monumentIds.length > 0 || doc.projetIds.length > 0) setAccessDoc(doc);
  };

  const rattachementsDe = (d: Document): string[] => {
    const pills = coteProjet
      ? []
      : d.projetIds
        .map((pid) => projetsById.get(pid))
        .filter((p) => p?.monumentId === monumentId)
        .map((p) => projetTitre(p!));
    const dossiers = d.dossiersUtilises.map((id) => dossierNames[id]).filter(Boolean);
    if (dossiers.length === 1) pills.push(dossiers[0]);
    else if (d.dossiersUtilises.length > 0) {
      const n = d.dossiersUtilises.length;
      pills.push(`Utilisé dans ${n} dossier${n > 1 ? 's' : ''}`);
    }
    return pills;
  };

  return (
    <div className="odoc">
      <PiecesADeposer
        monumentId={monumentId}
        projetIds={projetIds}
        documents={documents}
        lectureSeule={!role}
        onDeposer={(p) => ouvrirAjout({ pieceId: p.pieceId, nom: p.nom, typeDocument: p.typeDocument, nbAides: p.nbAides })}
      />

      <section className="odoc-sec" aria-label="Vos documents">
        <div className="sec-h">
          <div>
            <h2>Vos documents</h2>
            {intro && <p>{intro}</p>}
          </div>
          <div className="odoc-acts">
            <button className="btn b-line" type="button" onClick={() => setAttachOpen(true)}>
              Joindre un document existant
            </button>
            <button className="btn b-orange" type="button" onClick={() => ouvrirAjout(null)}>
              <Picto nom="envoyer" />Ajouter un document
            </button>
          </div>
        </div>

        <div className="odoc-liste">
          {documents.length === 0 ? (
            <p className="ldocs-vide">{vide}</p>
          ) : documents.map((d) => (
            <LigneDocument
              key={d.id}
              document={d}
              onVoir={() => setPreviewDoc(d)}
              actions={actionsDocument(d, { userId, role, ici }, {
                modifier: (doc) => { setPiece(null); setEditDoc(doc); setUploadOpen(true); },
                rattacher: setAddToProjectDoc,
                gererAcces: setAccessDoc,
                corbeille,
                retirer,
              })}
              nbAides={d.pieceId ? aidesParPiece[d.pieceId] : undefined}
              rattachements={rattachementsDe(d)}
              auteur={d.userId !== userId ? auteurs[d.userId] : undefined}
              nouveau={d.id === nouveauId}
            />
          ))}
        </div>
      </section>

      <UploadDocumentDialog
        open={uploadOpen}
        onOpenChange={(o) => { setUploadOpen(o); if (!o) { setPiece(null); setEditDoc(null); } }}
        onUploaded={apresDepot}
        onModifie={onChange}
        piece={piece}
        document={editDoc}
        monumentIdsParDefaut={coteProjet ? [] : [ici.id]}
        projetIds={coteProjet ? [ici.id] : []}
        choixMonuments={!coteProjet}
      />
      <AttachDocumentDialog
        open={attachOpen}
        onOpenChange={setAttachOpen}
        monumentId={coteProjet ? undefined : ici.id}
        projetId={coteProjet ? ici.id : undefined}
        onAttach={joindre}
        onUploaded={(doc) => setAccessDoc(doc)}
      />
      {accessDoc && (
        <ManageDocumentAccessDialog
          document={accessDoc}
          myRole={role}
          open={!!accessDoc}
          onOpenChange={(open) => { if (!open) setAccessDoc(null); }}
          onSaved={onChange}
        />
      )}
      <DocumentPreviewDialog
        document={previewDoc}
        open={!!previewDoc}
        onOpenChange={(open) => { if (!open) setPreviewDoc(null); }}
        onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }}
      />
      <AddToProjectDialog
        document={addToProjectDoc}
        open={!!addToProjectDoc}
        onOpenChange={(open) => { if (!open) { setAddToProjectDoc(null); relire(); } }}
      />
    </div>
  );
}
