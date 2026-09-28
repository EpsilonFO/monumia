import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Picto } from '@/components/shared/ecrans/Picto';
import { LigneDocument } from '@/components/document/LigneDocument';
import { actionsDocument, type ActionDocument } from '@/lib/actions-document';
import { PiecesADeposer } from '@/components/document/PiecesADeposer';
import { usePiecesADeposer } from '@/hooks/usePiecesADeposer';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { UploadDocumentDialog, type PieceAPreremplir } from '@/components/document/UploadDocumentDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useProjectsData } from '@/hooks/useProjectsData';
import { DocumentsListSkeleton } from '@/components/skeletons';
import { FAMILLES_TYPES, typeLabel } from '@/lib/document-type-meta';
import { documentDuMonument, nbAidesParPiece } from '@/lib/pieces-a-deposer';
import { projetTitre } from '@/lib/projet-titre';
import { ROUTES } from '@/constants/routes';
import type { Document, DocumentType, ProjectRole } from '@/types';
import { toast } from 'sonner';
import '@/components/document/documents.css';

/** Les deux entrées du sélecteur qui ne sont pas un monument. */
const SANS = 'sans';
const PARTAGES = 'partages';

const RANG: Record<ProjectRole, number> = { member: 1, co_owner: 2, owner: 3 };
function meilleurRole(roles: (ProjectRole | null | undefined)[]): ProjectRole | null {
  return roles.reduce<ProjectRole | null>((m, r) => (r && (!m || RANG[r] > RANG[m]) ? r : m), null);
}

interface Onglet {
  id: string;
  nom: string;
  docs: Document[];
}

/**
 * Mes documents : maquette `monumia-documents.html` (yaml paul). La page
 * montre UN monument à la fois (`?monument=`) ; quand il y a plus d'un endroit
 * où ranger (plusieurs monuments, des documents sans monument, des documents
 * partagés par un monument qu'on ne voit pas), un sélecteur en pilules le
 * choisit.
 */
export function DocumentsPage() {
  // Les digests des projets (pièces demandées par leurs aides) et les projets
  // eux-mêmes viennent de `GET /dashboard`.
  useProjectsData();
  const {
    documents, trashedDocuments, loading,
    fetchDocuments, fetchTrashed, trashDocument, restoreDocument, removeFromProject, deleteDocument,
  } = useDocumentStore();
  const monuments = useMonumentStore((s) => s.monuments);
  const projets = useProjetStore((s) => s.projets);
  const userId = useAuthStore((s) => s.user?.id);
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<DocumentType | ''>('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pieceADeposer, setPieceADeposer] = useState<PieceAPreremplir | null>(null);
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [trashOpen, setTrashOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [nouveauId, setNouveauId] = useState<string | null>(null);

  useEffect(() => {
    fetchDocuments();
    fetchTrashed();
  }, [fetchDocuments, fetchTrashed]);

  useEffect(() => {
    if (!nouveauId) return;
    const t = setTimeout(() => setNouveauId(null), 1600);
    return () => clearTimeout(t);
  }, [nouveauId]);

  // ---- Résolution des noms et des rôles ----
  const monumentsById = useMemo(() => new Map(monuments.map((m) => [m.id, m])), [monuments]);
  const projetsById = useMemo(() => new Map(projets.map((p) => [p.id, p])), [projets]);
  const projetsParMonument = useMemo(() => {
    const m = new Map<string, string[]>();
    projets.forEach((p) => m.set(p.monumentId, [...(m.get(p.monumentId) ?? []), p.id]));
    return m;
  }, [projets]);
  const uploaderNames = useMemo(() => {
    const m: Record<string, string> = {};
    monuments.forEach((mo) => (mo.members ?? []).forEach((p) => { m[p.userId] = `${p.prenom} ${p.nom}`.trim(); }));
    return m;
  }, [monuments]);

  /** Les monuments connus auxquels un document pend, directement ou par un de leurs projets. */
  const monumentsDuDocument = useMemo(() => (d: Document): string[] => {
    const ids = new Set(d.monumentIds.filter((id) => monumentsById.has(id)));
    d.projetIds.forEach((pid) => {
      const mid = projetsById.get(pid)?.monumentId;
      if (mid && monumentsById.has(mid)) ids.add(mid);
    });
    return [...ids];
  }, [monumentsById, projetsById]);

  // ---- Les entrées du sélecteur ----
  const onglets: Onglet[] = useMemo(() => {
    const parMonument: Onglet[] = monuments.map((m) => ({
      id: m.id,
      nom: m.nom,
      docs: documents.filter((d) => documentDuMonument(d, m.id, projetsParMonument.get(m.id) ?? [])),
    }));
    const sans = documents.filter((d) => d.monumentIds.length === 0 && d.projetIds.length === 0);
    // Filet de sécurité : un document que le serveur nous rend (donc visible)
    // mais dont aucun monument n'est connu du store ne doit jamais disparaître.
    const partages = documents.filter(
      (d) => (d.monumentIds.length > 0 || d.projetIds.length > 0) && monumentsDuDocument(d).length === 0,
    );
    return [
      ...parMonument,
      ...(sans.length > 0 ? [{ id: SANS, nom: 'Sans monument', docs: sans }] : []),
      ...(partages.length > 0 ? [{ id: PARTAGES, nom: 'Partagés avec vous', docs: partages }] : []),
    ];
  }, [monuments, documents, projetsParMonument, monumentsDuDocument]);

  const demande = params.get('monument');
  const actif = onglets.find((o) => o.id === demande) ?? onglets[0] ?? null;
  const monumentActif = actif ? monumentsById.get(actif.id) ?? null : null;

  const choisir = (id: string) => {
    setFilterType('');
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('monument', id);
      return next;
    }, { replace: true });
  };

  // ---- Pièces à déposer (pour la pastille « Sert à N aides ») ----
  const { pieces } = usePiecesADeposer(monumentActif?.id ?? null);
  const aidesParPiece = useMemo(() => nbAidesParPiece(pieces), [pieces]);

  // ---- Rattachement d'un nouveau dépôt ----
  // Sur un monument dont on est de l'équipe, le document pend au monument. Un
  // membre d'un seul chantier n'y a pas droit (la route refuse) : il le range
  // dans ses projets ouverts. Un monument relu du cache n'a pas encore son rôle.
  const membreDuMonument = !!monumentActif
    && (!!monumentActif.myRole || monumentActif.userId === userId || !!monumentActif.depuisLeCache);
  const depotMonuments = monumentActif && membreDuMonument ? [monumentActif.id] : [];
  const depotProjets = monumentActif && !membreDuMonument
    ? projets.filter((p) => p.monumentId === monumentActif.id && !p.clotureAt).map((p) => p.id)
    : [];

  const ouvrirAjout = (piece: PieceAPreremplir | null) => {
    setPieceADeposer(piece);
    setEditDoc(null);
    setUploadOpen(true);
  };

  // ---- Filtrage (recherche + type) ----
  const q = search.trim().toLowerCase();
  const visibles = (actif?.docs ?? []).filter((d) => {
    if (filterType && d.type !== filterType) return false;
    if (!q) return true;
    return d.nom.toLowerCase().includes(q)
      || d.nomFichier.toLowerCase().includes(q)
      || d.tags.some((t) => t.toLowerCase().includes(q));
  });

  // ---- Actions ----
  const roleSur = (d: Document): ProjectRole | null => meilleurRole([
    ...d.monumentIds.map((id) => monumentsById.get(id)?.myRole),
    ...d.projetIds.map((id) => projetsById.get(id)?.myRole),
  ]);

  const handleTrash = async (d: Document) => {
    if (!confirm(`Mettre "${d.nom}" à la corbeille ?`)) return;
    try { await trashDocument(d.id); toast.success('Document mis à la corbeille'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const handleRemoveFromMonument = async (d: Document, monumentId: string) => {
    try { await removeFromProject(d.id, monumentId); toast.success('Document retiré du monument'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const handleRestore = async (d: Document) => {
    try { await restoreDocument(d.id); toast.success('Document restauré'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };
  const handleDeletePermanent = async (d: Document) => {
    if (!confirm(`Supprimer définitivement "${d.nom}" ? Cette action est irréversible.`)) return;
    try { await deleteDocument(d.id); toast.success('Document supprimé définitivement'); }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Erreur'); }
  };

  const actionsPour = (d: Document): ActionDocument[] => actionsDocument(
    d,
    { userId, role: roleSur(d), ici: monumentActif ? { type: 'monument', id: monumentActif.id, nom: monumentActif.nom } : null },
    {
      modifier: (doc) => { setPieceADeposer(null); setEditDoc(doc); setUploadOpen(true); },
      rattacher: setAddToProjectDoc,
      gererAcces: setAccessDoc,
      corbeille: handleTrash,
      retirer: (doc, ici) => handleRemoveFromMonument(doc, ici.id),
    },
  );

  const rattachementsDe = (d: Document): string[] => (monumentActif
    ? d.projetIds
      .map((pid) => projetsById.get(pid))
      .filter((p) => p?.monumentId === monumentActif.id)
      .map((p) => projetTitre(p!))
    : []);

  const apresDepot = (doc: Document) => {
    setNouveauId(doc.id);
    // Rangé ailleurs que sous le monument affiché : on suit le document.
    const ici = actif?.id;
    const ou = monumentsDuDocument(doc);
    if (ou.length > 0 && ici && !ou.includes(ici)) choisir(ou[0]);
    else if (ou.length === 0 && doc.monumentIds.length === 0 && doc.projetIds.length === 0 && ici !== SANS) choisir(SANS);
    // Le document est créé avec un défaut sûr (chef + adjoints) : « Gérer
    // l'accès » s'ouvre aussitôt pour que l'auteur choisisse qui peut le voir.
    if (doc.monumentIds.length > 0) setAccessDoc(doc);
  };

  const filtreActif = q !== '' || filterType !== '';
  const videMessage = filtreActif
    ? 'Aucun document ne correspond.'
    : monumentActif
      ? 'Aucun document pour ce monument pour l\'instant.'
      : 'Aucun document pour l\'instant.';

  return (
    <div className="ec docs-page">
      <div className="d-top">
        <div>
          {monumentActif && (
            <Link className="d-lieu" to={ROUTES.MONUMENT_DETAIL(monumentActif.id)}>{monumentActif.nom}</Link>
          )}
          <h1>Mes documents</h1>
          <p>Une pièce déposée une fois sert à tous les dossiers qui la demandent.</p>
        </div>
        <button className="btn b-orange" type="button" onClick={() => ouvrirAjout(null)}>
          <Picto nom="envoyer" />Ajouter un document
        </button>
      </div>

      {onglets.length > 1 && (
        <div className="d-mons" role="group" aria-label="Choisir un monument">
          {onglets.map((o) => (
            <button key={o.id} type="button" aria-pressed={o.id === actif?.id} onClick={() => choisir(o.id)}>
              {o.nom}<em>{o.docs.length}</em>
            </button>
          ))}
        </div>
      )}

      {monumentActif && (
        <div className="d-sec">
          <PiecesADeposer
            monumentId={monumentActif.id}
            onDeposer={(p) => ouvrirAjout({ pieceId: p.pieceId, nom: p.nom, typeDocument: p.typeDocument, nbAides: p.nbAides })}
          />
        </div>
      )}

      <section className="d-sec" aria-labelledby="docs-titre">
        <div className="sec-h"><div><h2 id="docs-titre">Vos documents</h2></div></div>
        <div className="d-tools">
          <label className="d-search">
            <span className="sr">Rechercher un document</span>
            <Picto nom="loupe" />
            <input type="search" placeholder="Rechercher un document" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className="d-sel">
            <label className="sr" htmlFor="docs-type">Type de document</label>
            <select id="docs-type" value={filterType} onChange={(e) => setFilterType(e.target.value as DocumentType | '')}>
              <option value="">Tous les types</option>
              {FAMILLES_TYPES.map((f) => (
                <optgroup key={f.nom} label={f.nom}>
                  {f.types.map((t) => <option key={t} value={t}>{typeLabel(t)}</option>)}
                </optgroup>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="d-docs"><DocumentsListSkeleton /></div>
        ) : (
          <div className="d-docs">
            {visibles.length === 0 ? (
              <p className="ldocs-vide">{videMessage}</p>
            ) : visibles.map((d) => (
              <LigneDocument
                key={d.id}
                document={d}
                onVoir={() => setPreviewDoc(d)}
                actions={actionsPour(d)}
                nbAides={d.pieceId ? aidesParPiece[d.pieceId] : undefined}
                rattachements={rattachementsDe(d)}
                auteur={d.userId !== userId ? uploaderNames[d.userId] : undefined}
                nouveau={d.id === nouveauId}
              />
            ))}
          </div>
        )}

        {trashedDocuments.length > 0 && (
          <div className="d-trash">
            <button className="lnk" type="button" aria-expanded={trashOpen} onClick={() => setTrashOpen((o) => !o)}>
              {trashOpen ? 'Masquer' : 'Voir'} les documents supprimés ({trashedDocuments.length})
            </button>
            {trashOpen && (
              <div className="d-docs">
                {trashedDocuments.map((d) => (
                  <LigneDocument
                    key={d.id}
                    document={d}
                    variant="trash"
                    onVoir={() => setPreviewDoc(d)}
                    actions={[
                      { label: 'Restaurer', onClick: () => handleRestore(d) },
                      { label: 'Supprimer définitivement', onClick: () => handleDeletePermanent(d), destructive: true },
                    ]}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <p className="d-priv">
        <Picto nom="cadenas" />
        <span>
          Vos documents restent privés. Monumia ne les transmet à aucun financeur, et vous choisissez qui, dans
          votre équipe, peut les voir.
        </span>
      </p>


      <UploadDocumentDialog
        open={uploadOpen}
        onOpenChange={(o) => { setUploadOpen(o); if (!o) { setPieceADeposer(null); setEditDoc(null); } }}
        onUploaded={apresDepot}
        piece={pieceADeposer}
        document={editDoc}
        monumentIdsParDefaut={depotMonuments}
        projetIds={depotProjets}
      />
      {accessDoc && (
        <ManageDocumentAccessDialog
          document={accessDoc}
          myRole={roleSur(accessDoc)}
          open={!!accessDoc}
          onOpenChange={(open) => { if (!open) setAccessDoc(null); }}
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
        onOpenChange={(open) => { if (!open) setAddToProjectDoc(null); }}
      />
    </div>
  );
}
