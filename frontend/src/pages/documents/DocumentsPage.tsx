import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { toast } from 'sonner';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Picto } from '@/components/shared/ecrans/Picto';
import { PictoDoc, type NomPictoDoc } from '@/components/document/PictosDocuments';
import {
  BarreSection, BarreSelection, DossiersDocuments, FichiersDocuments, FichiersSquelette, OutilsDocuments,
  VideDocuments, VoileDepot, type GesteSelection,
} from '@/components/document/EspaceDocuments';
import { useDepotGlisse } from '@/components/document/useDepotGlisse';
import type { DocumentAfficheProps } from '@/components/document/LigneDocument';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { UploadDocumentDialog, type PieceAPreremplir } from '@/components/document/UploadDocumentDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { ChangerDossierDialog } from '@/components/document/ChangerDossierDialog';
import { usePiecesADeposer } from '@/hooks/usePiecesADeposer';
import { useProjectsData } from '@/hooks/useProjectsData';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { actionsDocument, repartirSelection, type ActionDocument } from '@/lib/actions-document';
import { dossierLabel } from '@/lib/document-type-meta';
import { tailleFichier } from '@/lib/document-fichier';
import { downloadDocument } from '@/lib/document-download';
import {
  compterParType, documentsRecents, rechercherDocuments, tailleTotale, trierDocuments,
  type TriDocuments, type VueDocuments,
} from '@/lib/documents-espace';
import { documentDuMonument, nbAidesParPiece } from '@/lib/pieces-a-deposer';
import { projetTitre } from '@/lib/projet-titre';
import { ACCEPT_ATTR } from '@/constants/file-types';
import { ROUTES } from '@/constants/routes';
import type { Document, DocumentType, ProjectRole } from '@/types';
import { CommentFonctionne } from '@/components/document/CommentFonctionne';
import '@/components/document/documents.css';

/** Les deux entrées du sélecteur de lieu qui ne sont pas un monument. */
const SANS = 'sans';
const PARTAGES = 'partages';

type Section = 'tous' | 'recents' | 'corbeille';

const RANG: Record<ProjectRole, number> = { member: 1, co_owner: 2, owner: 3 };
function meilleurRole(roles: (ProjectRole | null | undefined)[]): ProjectRole | null {
  return roles.reduce<ProjectRole | null>((m, r) => (r && (!m || RANG[r] > RANG[m]) ? r : m), null);
}

const plur = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;

/** Grille ou liste : une commodité du navigateur, jamais une donnée. */
const CLE_VUE = 'monumia.documents.vue';
function vueMemorisee(): VueDocuments {
  try { return window.localStorage.getItem(CLE_VUE) === 'liste' ? 'liste' : 'grille'; } catch { return 'grille'; }
}

interface Lieu {
  id: string;
  nom: string;
  docs: Document[];
}

/** Ce que la fenêtre d'ajout reçoit à l'ouverture. */
interface Depot {
  fichiers: File[];
  type: DocumentType | null;
  piece: PieceAPreremplir | null;
}

/**
 * Mes documents : maquette `monumia-documents.html`, un espace de fichiers.
 * À gauche « Nouveau » et les rubriques (tous, récents, pièces demandées,
 * corbeille) ; à droite la recherche, le fil (« Tous les documents › Devis »),
 * le lieu, les dossiers (un par type) et les fichiers en grille ou en liste.
 *
 * La page montre UN lieu à la fois (`?monument=`) : un monument, les documents
 * sans monument, ou ceux qu'un monument invisible partage avec vous. La liste
 * vient telle quelle de `GET /documents`, déjà filtrée par le serveur
 * (`best_document_role`) : rien n'est masqué ici qui aurait été reçu.
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

  const [section, setSection] = useState<Section>('tous');
  const [dossier, setDossier] = useState<DocumentType | null>(null);
  const [recherche, setRecherche] = useState('');
  const [tri, setTri] = useState<TriDocuments>('date');
  const [vue, setVueEtat] = useState<VueDocuments>(vueMemorisee);
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const [depot, setDepot] = useState<Depot | null>(null);
  const [editDoc, setEditDoc] = useState<Document | null>(null);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [aDeplacer, setADeplacer] = useState<Document[]>([]);
  const [nouveaux, setNouveaux] = useState<Set<string>>(new Set());

  const inputRef = useRef<HTMLInputElement>(null);
  const enAttente = useRef<Omit<Depot, 'fichiers'>>({ type: null, piece: null });

  useEffect(() => {
    fetchDocuments();
    fetchTrashed();
  }, [fetchDocuments, fetchTrashed]);

  useEffect(() => {
    if (nouveaux.size === 0) return;
    const t = setTimeout(() => setNouveaux(new Set()), 1600);
    return () => clearTimeout(t);
  }, [nouveaux]);

  const setVue = (v: VueDocuments) => {
    setVueEtat(v);
    try { window.localStorage.setItem(CLE_VUE, v); } catch { /* navigation privée */ }
  };

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

  // ---- Les lieux ----
  const lieux: Lieu[] = useMemo(() => {
    const parMonument: Lieu[] = monuments.map((m) => ({
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
  const actif = lieux.find((o) => o.id === demande) ?? lieux[0] ?? null;
  const monumentActif = actif ? monumentsById.get(actif.id) ?? null : null;

  const choisirLieu = (id: string) => {
    setDossier(null);
    setSelection(new Set());
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('monument', id);
      return next;
    }, { replace: true });
  };

  // ---- Pièces demandées par les aides (pastille « Sert à N aides ») ----
  const { pieces } = usePiecesADeposer(monumentActif?.id ?? null);
  const aidesParPiece = useMemo(() => nbAidesParPiece(pieces), [pieces]);
  const rubrique = section;

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

  /** « Nouveau », « Importer un fichier », « Déposer » : le sélecteur de fichiers d'abord. */
  const choisirFichiers = (opts: Omit<Depot, 'fichiers'>) => {
    enAttente.current = opts;
    const input = inputRef.current;
    if (!input) return;
    input.multiple = !opts.piece;
    input.value = '';
    input.click();
  };
  const ouvrirDepot = (d: Depot) => { setEditDoc(null); setDepot(d); };

  const depotGlisse = useDepotGlisse(
    rubrique === 'corbeille' ? null : (fichiers, cible) => ouvrirDepot({ fichiers, type: cible ?? dossier, piece: null }),
  );

  // ---- Ce qui s'affiche ----
  const base = actif?.docs ?? [];
  const trouves = rechercherDocuments(rubrique === 'corbeille' ? trashedDocuments : base, recherche);
  const liste = rubrique === 'recents'
    ? trierDocuments(documentsRecents(trouves), tri)
    : trierDocuments(rubrique === 'tous' && dossier ? trouves.filter((d) => d.type === dossier) : trouves, tri);
  const comptes = compterParType(base);
  const montrerDossiers = rubrique === 'tous' && !dossier && !recherche.trim();

  // ---- Rôles et gestes ----
  const roleSur = (d: Document): ProjectRole | null => meilleurRole([
    ...d.monumentIds.map((id) => monumentsById.get(id)?.myRole),
    ...d.projetIds.map((id) => projetsById.get(id)?.myRole),
  ]);
  const ici = monumentActif ? { type: 'monument' as const, id: monumentActif.id, nom: monumentActif.nom } : null;

  const erreur = (e: unknown) => toast.error(e instanceof Error ? e.message : 'Erreur');

  const handleTrash = async (d: Document) => {
    if (!confirm(`Mettre « ${d.nom} » à la corbeille ?`)) return;
    try { await trashDocument(d.id); toast.success(`« ${d.nom} » est dans la corbeille.`); } catch (e) { erreur(e); }
  };
  const handleRemoveFromMonument = async (d: Document, monumentId: string) => {
    try { await removeFromProject(d.id, monumentId); toast.success('Document retiré du monument'); } catch (e) { erreur(e); }
  };
  const handleRestore = async (d: Document) => {
    try { await restoreDocument(d.id); toast.success('Document restauré'); } catch (e) { erreur(e); }
  };
  const handleDeletePermanent = async (d: Document) => {
    if (!confirm(`Supprimer définitivement « ${d.nom} » ? Cette action est irréversible.`)) return;
    try { await deleteDocument(d.id); toast.success('Document supprimé définitivement'); } catch (e) { erreur(e); }
  };

  const actionsPour = (d: Document): ActionDocument[] => (rubrique === 'corbeille'
    ? [
      { cle: 'restaurer', label: 'Restaurer', onClick: () => handleRestore(d) },
      { cle: 'supprimer', label: 'Supprimer définitivement', onClick: () => handleDeletePermanent(d), destructive: true },
    ]
    : actionsDocument(d, { userId, role: roleSur(d), ici }, {
      modifier: (doc) => { setDepot(null); setEditDoc(doc); },
      deplacer: (doc) => setADeplacer([doc]),
      rattacher: setAddToProjectDoc,
      gererAcces: setAccessDoc,
      corbeille: handleTrash,
      retirer: (doc, lieu) => handleRemoveFromMonument(doc, lieu.id),
    }));

  const rattachementsDe = (d: Document): string[] => (monumentActif
    ? d.projetIds
      .map((pid) => projetsById.get(pid))
      .filter((p) => p?.monumentId === monumentActif.id)
      .map((p) => projetTitre(p!, monumentActif.nom))
    : []);

  const basculer = (id: string) => setSelection((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  const proprietes = (d: Document): DocumentAfficheProps => ({
    document: d,
    onVoir: () => setPreviewDoc(d),
    actions: actionsPour(d),
    variant: rubrique === 'corbeille' ? 'trash' : 'normal',
    nbAides: d.pieceId ? aidesParPiece[d.pieceId] : undefined,
    rattachements: rattachementsDe(d),
    auteur: d.userId !== userId ? uploaderNames[d.userId] : undefined,
    nouveau: nouveaux.has(d.id),
    selectionne: selection.has(d.id),
    onSelection: rubrique === 'corbeille' ? undefined : () => basculer(d.id),
  });

  // ---- Sélection ----
  const selectionnes = base.filter((d) => selection.has(d.id));
  const repartition = repartirSelection(selectionnes, { userId, roleDe: roleSur, ici });

  const telechargerSelection = async () => {
    for (const d of selectionnes) {
      try { await downloadDocument(d); } catch (e) { toast.error(`${d.nom} : ${e instanceof Error ? e.message : 'téléchargement impossible'}`); }
    }
  };
  const supprimerSelection = async () => {
    const { aJeter, aRetirer, sansRetrait } = repartition;
    const phrases = [
      aJeter.length ? `${plur(aJeter.length, 'document')} à la corbeille` : '',
      aRetirer.length && ici ? `${plur(aRetirer.length, 'document')} retiré${aRetirer.length > 1 ? 's' : ''} de ${ici.nom}` : '',
    ].filter(Boolean);
    const reste = sansRetrait.length
      ? `\n${plur(sansRetrait.length, 'autre document')} ne ${sansRetrait.length > 1 ? 'peuvent' : 'peut'} pas être supprimé${sansRetrait.length > 1 ? 's' : ''} par vous : ${sansRetrait.length > 1 ? 'ils restent' : 'il reste'} en place.`
      : '';
    if (!confirm(`Supprimer la sélection : ${phrases.join(', ')} ?${reste}`)) return;
    let ok = 0;
    for (const d of aJeter) { try { await trashDocument(d.id); ok += 1; } catch (e) { erreur(e); } }
    for (const d of aRetirer) { try { if (ici) { await removeFromProject(d.id, ici.id); ok += 1; } } catch (e) { erreur(e); } }
    setSelection(new Set());
    if (ok) toast.success(`${plur(ok, 'document')} supprimé${ok > 1 ? 's' : ''} de cet espace.`);
  };

  const gestesSelection: GesteSelection[] = [
    { label: 'Télécharger', picto: 'telecharger', onClick: telechargerSelection },
    ...(repartition.modifiables.length ? [{ label: 'Déplacer', picto: 'deplacer' as const, onClick: () => setADeplacer(repartition.modifiables) }] : []),
    ...(repartition.aJeter.length + repartition.aRetirer.length
      ? [{ label: 'Supprimer', picto: 'corbeille' as const, onClick: supprimerSelection }]
      : []),
  ];

  // ---- Après un dépôt ----
  const apresDepot = (docs: Document[]) => {
    const doc = docs[0];
    if (!doc) return;
    setNouveaux(new Set(docs.map((d) => d.id)));
    // Rangé ailleurs que sous le lieu affiché : on suit le document.
    const ou = monumentsDuDocument(doc);
    if (ou.length > 0 && actif && !ou.includes(actif.id)) choisirLieu(ou[0]);
    else if (ou.length === 0 && doc.monumentIds.length === 0 && doc.projetIds.length === 0 && actif?.id !== SANS) choisirLieu(SANS);
    // Comme la maquette : on ouvre le dossier où il vient d'être rangé.
    setSection('tous');
    setRecherche('');
    setDossier(docs.every((d) => d.type === doc.type) ? doc.type : null);
    // Le document est créé avec un défaut sûr (chef + adjoints) : « Gérer
    // l'accès » s'ouvre aussitôt pour que l'auteur choisisse qui peut le voir.
    if (docs.length === 1 && doc.monumentIds.length > 0) setAccessDoc(doc);
  };

  const ouvrirRubrique = (s: Section) => {
    setSection(s);
    setDossier(null);
    setSelection(new Set());
  };

  // ---- Fil ----
  const fil: { label: string; onClick?: () => void }[] = rubrique === 'recents'
    ? [{ label: 'Récents' }]
    : rubrique === 'corbeille'
      ? [{ label: 'Corbeille' }]
      : dossier
        ? [{ label: 'Tous les documents', onClick: () => { setDossier(null); setSelection(new Set()); } }, { label: dossierLabel(dossier) }]
        : [{ label: 'Tous les documents' }];

  const rubriques: { id: Section; picto: NomPictoDoc; label: string; badge?: number }[] = [
    { id: 'tous', picto: 'tous', label: 'Tous les documents' },
    { id: 'recents', picto: 'recents', label: 'Récents' },
    { id: 'corbeille', picto: 'corbeille', label: 'Corbeille' },
  ];

  const importer = (
    <button className="btn b-blue" type="button" onClick={() => choisirFichiers({ type: dossier, piece: null })}>
      <Picto nom="envoyer" />Importer un fichier
    </button>
  );
  const vide = recherche.trim()
    ? <VideDocuments titre="Aucun document trouvé" texte="Essayez un autre mot." />
    : rubrique === 'corbeille'
      ? <VideDocuments titre="La corbeille est vide" texte="Un document mis à la corbeille y reste tant que vous ne le supprimez pas définitivement." />
      : (
        <VideDocuments
          titre={dossier ? 'Ce dossier est vide' : 'Aucun document'}
          texte="Glissez un fichier sur cette page, ou choisissez-le sur votre ordinateur."
          action={importer}
        />
      );

  return (
    <div className="ec docs-page">
      <h1 className="sr">Mes documents</h1>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        className="sr"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const fichiers = [...(e.target.files ?? [])];
          if (fichiers.length) ouvrirDepot({ fichiers, ...enAttente.current });
        }}
      />

      <div className="drive">
        <aside className="side" aria-label="Navigation des documents">
          <button className="nouveau" type="button" onClick={() => choisirFichiers({ type: dossier, piece: null })}>
            <Picto nom="plus" />Nouveau
          </button>
          <nav className="dnav">
            {rubriques.map((r) => (
              <button key={r.id} type="button" aria-current={rubrique === r.id} onClick={() => ouvrirRubrique(r.id)}>
                <PictoDoc nom={r.picto} />{r.label}{r.badge ? <em>{r.badge}</em> : null}
              </button>
            ))}
          </nav>
          {actif && (
            <div className="store">
              <b>{plur(base.length, 'document')}</b>
              <small>{tailleFichier(tailleTotale(base))}</small>
            </div>
          )}
          <p className="priv">
            <Picto nom="cadenas" />
            <span>Vos fichiers restent privés. Monumia ne les transmet à aucun financeur, et vous choisissez qui, dans votre équipe, peut les voir.</span>
          </p>
        </aside>

        <section className="desp main" aria-label="Vos documents" {...depotGlisse.gestionnaires}>
          <OutilsDocuments
            recherche={recherche}
            onRecherche={(q) => {
              setRecherche(q);
              if (rubrique === 'corbeille') ouvrirRubrique('tous');
            }}
            vue={vue}
            onVue={setVue}
          />
          <CommentFonctionne />

          <div className="crumbs">
            {fil.map((f, i) => (
              <span key={f.label} className="crumb">
                {i > 0 && <PictoDoc nom="suivant" className="sep" />}
                {f.onClick ? <button type="button" onClick={f.onClick}>{f.label}</button> : <span aria-current="page">{f.label}</span>}
              </span>
            ))}
          </div>
          {actif && rubrique !== 'corbeille' && (
            lieux.length > 1 ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" className="lieu" aria-label={`Lieu : ${actif.nom}. Changer de lieu`}>
                    {actif.nom}<Picto nom="chevron" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="ec dmenu">
                  {lieux.map((l) => (
                    <DropdownMenuItem key={l.id} onClick={() => choisirLieu(l.id)} className={l.id === actif.id ? 'on' : undefined}>
                      <span className="nomlieu">{l.nom}</span><em>{l.docs.length}</em>
                    </DropdownMenuItem>
                  ))}
                  {monumentActif && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem asChild>
                        <Link to={ROUTES.MONUMENT_DETAIL(monumentActif.id)}>Voir la fiche du monument</Link>
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : monumentActif ? (
              <Link className="lieu" to={ROUTES.MONUMENT_DETAIL(monumentActif.id)}>{monumentActif.nom}</Link>
            ) : (
              <span className="lieu">{actif.nom}</span>
            )
          )}

          {montrerDossiers && (
            <>
              <BarreSection titre="Dossiers" />
              <DossiersDocuments
                comptes={comptes}
                onOuvrir={(t) => { setDossier(t); setSelection(new Set()); }}
                survole={depotGlisse.survole}
              />
            </>
          )}
          <BarreSection
            titre={rubrique === 'corbeille' ? 'Dans la corbeille' : recherche.trim() && !dossier ? 'Résultats' : 'Documents'}
            tri={tri}
            onTri={setTri}
          />
          {loading ? <FichiersSquelette /> : liste.length === 0 ? vide : (
            <FichiersDocuments documents={liste} vue={vue} proprietes={proprietes} />
          )}
          <BarreSelection nombre={selectionnes.length} gestes={gestesSelection} onVider={() => setSelection(new Set())} />

          <VoileDepot actif={depotGlisse.actif && !depotGlisse.surDossiers} dossier={dossier} />
        </section>
      </div>

      <UploadDocumentDialog
        open={!!depot || !!editDoc}
        onOpenChange={(o) => { if (!o) { setDepot(null); setEditDoc(null); } }}
        onUploaded={apresDepot}
        fichiers={depot?.fichiers}
        typeParDefaut={depot?.type}
        piece={depot?.piece}
        document={editDoc}
        monumentIdsParDefaut={depotMonuments}
        projetIds={depotProjets}
      />
      <ChangerDossierDialog
        documents={aDeplacer}
        onOpenChange={(o) => { if (!o) setADeplacer([]); }}
        onDeplace={() => setSelection(new Set())}
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
