import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Picto } from '@/components/shared/ecrans/Picto';
import {
  BarreSection, BarreSelection, FichiersDocuments, OutilsDocuments, VideDocuments, VoileDepot,
  type GesteSelection,
} from '@/components/document/EspaceDocuments';
import { useDepotGlisse } from '@/components/document/useDepotGlisse';
import type { DocumentAfficheProps } from '@/components/document/LigneDocument';
import { PiecesADeposer } from '@/components/document/PiecesADeposer';
import { UploadDocumentDialog, type PieceAPreremplir } from '@/components/document/UploadDocumentDialog';
import { ChangerDossierDialog } from '@/components/document/ChangerDossierDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { usePiecesADeposer } from '@/hooks/usePiecesADeposer';
import { actionsDocument, repartirSelection, type IciDocument } from '@/lib/actions-document';
import { downloadDocument } from '@/lib/document-download';
import { rechercherDocuments, trierDocuments, type TriDocuments, type VueDocuments } from '@/lib/documents-espace';
import { nbAidesParPiece } from '@/lib/pieces-a-deposer';
import { projetTitre } from '@/lib/projet-titre';
import { documentService } from '@/services/document.service';
import { ACCEPT_ATTR } from '@/constants/file-types';
import { useAuthStore } from '@/stores/useAuthStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import type { Document, DocumentType, ProjectRole } from '@/types';
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
  /** Une phrase sous l'intertitre « Documents ». */
  intro?: string;
  /** Le texte du bloc vide. */
  vide: string;
}

/** Même clé que Mes documents : on garde l'affichage choisi d'un écran à l'autre. */
const CLE_VUE = 'monumia.documents.vue';
function vueMemorisee(): VueDocuments {
  try { return window.localStorage.getItem(CLE_VUE) === 'liste' ? 'liste' : 'grille'; } catch { return 'grille'; }
}

const plur = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;

interface Depot {
  fichiers: File[];
  piece: PieceAPreremplir | null;
  type: DocumentType | null;
}

/**
 * L'onglet Documents d'un monument ou d'un projet, avec les briques de Mes
 * documents : pièces demandées, recherche, grille ou liste, sélection, dépôt
 * par glisser, et le même menu ⋮.
 *
 * Deux règles viennent du périmètre et nulle part ailleurs :
 *  - côté PROJET, un document déposé pend au chantier et à lui seul (pas de
 *    choix de monument dans la fenêtre d'ajout) : le déposer ici ne doit pas
 *    l'exposer à l'équipe du bien au-delà de ce qu'elle voit déjà ;
 *  - côté MONUMENT, il pend au monument, coché par défaut. La liste y montre
 *    aussi les pièces de ses projets (le serveur les ajoute), avec la pastille
 *    du chantier. « Retirer de ce monument » ne leur est pas proposé
 *    (`droitsDocument`) : elles ne pendent qu'au projet.
 */
export function OngletDocuments({
  ici, monumentId, documents, onChange, role, auteurs = {}, dossierNames = {}, intro, vide,
}: OngletDocumentsProps) {
  const userId = useAuthStore((s) => s.user?.id);
  const projets = useProjetStore((s) => s.projets);
  const monumentNom = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId)?.nom);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const trashDocument = useDocumentStore((s) => s.trashDocument);

  const [recherche, setRecherche] = useState('');
  const [tri, setTri] = useState<TriDocuments>('date');
  const [vue, setVueEtat] = useState<VueDocuments>(vueMemorisee);
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const [depot, setDepot] = useState<Depot | null>(null);
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [attachOpen, setAttachOpen] = useState(false);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [aDeplacer, setADeplacer] = useState<Document[]>([]);
  const [nouveaux, setNouveaux] = useState<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);
  const pieceEnAttente = useRef<PieceAPreremplir | null>(null);

  // Le store « mes documents » sert à savoir quelles pièces sont déjà là : la
  // liste de l'onglet ne voit que son périmètre (celle d'un projet n'a pas les
  // pièces du monument, ni une pièce `porteur` déposée ailleurs).
  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  useEffect(() => {
    if (nouveaux.size === 0) return;
    const t = setTimeout(() => setNouveaux(new Set()), 1600);
    return () => clearTimeout(t);
  }, [nouveaux]);

  const setVue = (v: VueDocuments) => {
    setVueEtat(v);
    try { window.localStorage.setItem(CLE_VUE, v); } catch { /* navigation privée */ }
  };

  const coteProjet = ici.type === 'projet';
  const projetIds = coteProjet ? [ici.id] : undefined;
  const { pieces } = usePiecesADeposer(monumentId, projetIds, documents);
  const aidesParPiece = useMemo(() => nbAidesParPiece(pieces), [pieces]);
  const projetsById = useMemo(() => new Map(projets.map((p) => [p.id, p])), [projets]);

  const relire = () => {
    onChange();
    fetchDocuments();
  };

  /** Le sélecteur de fichiers d'abord, puis la fenêtre d'ajout (maquette). */
  const choisirFichiers = (piece: PieceAPreremplir | null) => {
    pieceEnAttente.current = piece;
    const input = inputRef.current;
    if (!input) return;
    input.multiple = !piece;
    input.value = '';
    input.click();
  };
  const ouvrirDepot = (d: Depot) => { setEditDoc(null); setDepot(d); };
  const depotGlisse = useDepotGlisse((fichiers) => ouvrirDepot({ fichiers, piece: null, type: null }));

  const erreur = (e: unknown) => toast.error(e instanceof Error ? e.message : 'Erreur');

  const corbeille = async (d: Document) => {
    if (!confirm(`Mettre « ${d.nom} » à la corbeille ?`)) return;
    try { await trashDocument(d.id); onChange(); toast.success(`« ${d.nom} » est dans la corbeille.`); } catch (e) { erreur(e); }
  };
  const retirerSansRelire = async (d: Document, lieu: IciDocument) => {
    if (lieu.type === 'projet') await documentService.removeFromProjet(d.id, lieu.id);
    else await documentService.removeFromProject(d.id, lieu.id);
  };
  const retirer = async (d: Document, lieu: IciDocument) => {
    try {
      await retirerSansRelire(d, lieu);
      relire();
      toast.success(lieu.type === 'projet' ? 'Document retiré du projet' : 'Document retiré du monument');
    } catch (e) { erreur(e); }
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

  const apresDepot = (docs: Document[]) => {
    setNouveaux(new Set(docs.map((d) => d.id)));
    onChange();
    // Créé avec un défaut sûr (chef + adjoints) : « Gérer l'accès » s'ouvre
    // aussitôt pour que l'auteur choisisse qui peut le voir.
    const doc = docs[0];
    if (docs.length === 1 && (doc.monumentIds.length > 0 || doc.projetIds.length > 0)) setAccessDoc(doc);
  };

  const rattachementsDe = (d: Document): string[] => {
    const pills = coteProjet
      ? []
      : d.projetIds
        .map((pid) => projetsById.get(pid))
        .filter((p) => p?.monumentId === monumentId)
        .map((p) => projetTitre(p!, monumentNom));
    const dossiers = d.dossiersUtilises.map((id) => dossierNames[id]).filter(Boolean);
    if (dossiers.length === 1) pills.push(dossiers[0]);
    else if (d.dossiersUtilises.length > 0) {
      const n = d.dossiersUtilises.length;
      pills.push(`Utilisé dans ${n} dossier${n > 1 ? 's' : ''}`);
    }
    return pills;
  };

  const basculer = (id: string) => setSelection((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  const liste = trierDocuments(rechercherDocuments(documents, recherche), tri);

  const proprietes = (d: Document): DocumentAfficheProps => ({
    document: d,
    onVoir: () => setPreviewDoc(d),
    actions: actionsDocument(d, { userId, role, ici }, {
      modifier: (doc) => { setDepot(null); setEditDoc(doc); },
      deplacer: (doc) => setADeplacer([doc]),
      rattacher: setAddToProjectDoc,
      gererAcces: setAccessDoc,
      corbeille,
      retirer,
    }),
    nbAides: d.pieceId ? aidesParPiece[d.pieceId] : undefined,
    rattachements: rattachementsDe(d),
    auteur: d.userId !== userId ? auteurs[d.userId] : undefined,
    nouveau: nouveaux.has(d.id),
    selectionne: selection.has(d.id),
    onSelection: () => basculer(d.id),
  });

  // ---- Sélection ----
  const selectionnes = documents.filter((d) => selection.has(d.id));
  const repartition = repartirSelection(selectionnes, { userId, roleDe: () => role, ici });
  const supprimerSelection = async () => {
    const { aJeter, aRetirer, sansRetrait } = repartition;
    const phrases = [
      aJeter.length ? `${plur(aJeter.length, 'document')} à la corbeille` : '',
      aRetirer.length ? `${plur(aRetirer.length, 'document')} retiré${aRetirer.length > 1 ? 's' : ''} de ${ici.nom}` : '',
    ].filter(Boolean);
    const reste = sansRetrait.length
      ? `\n${plur(sansRetrait.length, 'autre document')} ne ${sansRetrait.length > 1 ? 'peuvent' : 'peut'} pas être supprimé${sansRetrait.length > 1 ? 's' : ''} par vous : ${sansRetrait.length > 1 ? 'ils restent' : 'il reste'} en place.`
      : '';
    if (!confirm(`Supprimer la sélection : ${phrases.join(', ')} ?${reste}`)) return;
    let ok = 0;
    for (const d of aJeter) { try { await trashDocument(d.id); ok += 1; } catch (e) { erreur(e); } }
    for (const d of aRetirer) { try { await retirerSansRelire(d, ici); ok += 1; } catch (e) { erreur(e); } }
    setSelection(new Set());
    relire();
    if (ok) toast.success(`${plur(ok, 'document')} supprimé${ok > 1 ? 's' : ''} de cet espace.`);
  };
  const gestesSelection: GesteSelection[] = [
    {
      label: 'Télécharger',
      picto: 'telecharger',
      onClick: async () => {
        for (const d of selectionnes) {
          try { await downloadDocument(d); } catch (e) { toast.error(`${d.nom} : ${e instanceof Error ? e.message : 'téléchargement impossible'}`); }
        }
      },
    },
    ...(repartition.modifiables.length ? [{ label: 'Déplacer', picto: 'deplacer' as const, onClick: () => setADeplacer(repartition.modifiables) }] : []),
    ...(repartition.aJeter.length + repartition.aRetirer.length
      ? [{ label: 'Supprimer', picto: 'corbeille' as const, onClick: supprimerSelection }]
      : []),
  ];

  return (
    <div className="desp odoc" {...depotGlisse.gestionnaires}>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        className="sr"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const fichiers = [...(e.target.files ?? [])];
          const piece = pieceEnAttente.current;
          if (fichiers.length) ouvrirDepot({ fichiers, piece, type: piece?.typeDocument ?? null });
        }}
      />

      <PiecesADeposer
        monumentId={monumentId}
        projetIds={projetIds}
        documents={documents}
        lectureSeule={!role}
        onDeposer={(p) => choisirFichiers({ pieceId: p.pieceId, nom: p.nom, typeDocument: p.typeDocument, nbAides: p.nbAides })}
      />

      <OutilsDocuments recherche={recherche} onRecherche={setRecherche} vue={vue} onVue={setVue}>
        <div className="odoc-acts">
          <button className="btn b-line" type="button" onClick={() => setAttachOpen(true)}>
            Joindre un document existant
          </button>
          <button className="btn b-orange" type="button" onClick={() => choisirFichiers(null)}>
            <Picto nom="envoyer" />Ajouter un document
          </button>
        </div>
      </OutilsDocuments>

      <BarreSection titre={recherche.trim() ? 'Résultats' : 'Documents'} tri={tri} onTri={setTri} />
      {intro && <p className="odoc-intro">{intro}</p>}

      {liste.length === 0 ? (
        recherche.trim()
          ? <VideDocuments titre="Aucun document trouvé" texte="Essayez un autre mot." />
          : <VideDocuments titre="Aucun document" texte={vide} />
      ) : (
        <FichiersDocuments documents={liste} vue={vue} proprietes={proprietes} />
      )}
      <BarreSelection nombre={selectionnes.length} gestes={gestesSelection} onVider={() => setSelection(new Set())} />
      <VoileDepot actif={depotGlisse.actif} />

      <UploadDocumentDialog
        open={!!depot || !!editDoc}
        onOpenChange={(o) => { if (!o) { setDepot(null); setEditDoc(null); } }}
        onUploaded={apresDepot}
        onModifie={onChange}
        fichiers={depot?.fichiers}
        typeParDefaut={depot?.type}
        piece={depot?.piece}
        document={editDoc}
        monumentIdsParDefaut={coteProjet ? [] : [ici.id]}
        projetIds={coteProjet ? [ici.id] : []}
        choixMonuments={!coteProjet}
      />
      <ChangerDossierDialog
        documents={aDeplacer}
        onOpenChange={(o) => { if (!o) setADeplacer([]); }}
        onDeplace={() => { setSelection(new Set()); onChange(); }}
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
