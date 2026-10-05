import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Picto } from '@/components/shared/ecrans/Picto';
import { PictoDossierPlein } from '@/components/document/PictosDocuments';
import { UploadDocumentDialog } from '@/components/document/UploadDocumentDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { ACCEPT_ATTR } from '@/constants/file-types';
import { ROUTES } from '@/constants/routes';
import { TYPES_DOSSIERS, dossierLabel } from '@/lib/document-type-meta';
import { formatFichier, tailleFichier } from '@/lib/document-fichier';
import { compterParType, documentsRecents, estImage, tailleTotale } from '@/lib/documents-espace';
import { documentDuMonument } from '@/lib/pieces-a-deposer';
import { monumentNomCourt } from '@/lib/projet-titre';
import type { Document, DocumentType, Monument, Projet, ProjectRole } from '@/types';

/** Les dossiers que la maquette montre toujours, même vides : les pièces qu'on demande le plus. */
const DOSSIERS_TOUJOURS: DocumentType[] = ['photo', 'devis', 'arrete', 'attestation'];
const NB_DERNIERS = 3;

const RANG: Record<ProjectRole, number> = { member: 1, co_owner: 2, owner: 3 };
function meilleurRole(roles: (ProjectRole | null | undefined)[]): ProjectRole | null {
  return roles.reduce<ProjectRole | null>((m, r) => (r && (!m || RANG[r] > RANG[m]) ? r : m), null);
}

const plur = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;
/** « 17 sept. 2026 » ; rien pour une date illisible plutôt qu'une page qui casse. */
function dateCourte(iso: string): string | null {
  const d = parseISO(iso);
  return Number.isNaN(d.getTime()) ? null : format(d, 'd MMM yyyy', { locale: fr });
}
const glisseDesFichiers = (e: DragEvent) => !!e.dataTransfer && [...e.dataTransfer.types].includes('Files');

/**
 * « Vos documents » du tableau de bord (maquette `monumia-tableau-de-bord.html`,
 * `.dc`) : les dossiers par type et leur compte, les derniers ajouts, une zone
 * de dépôt. Un seul monument : ses documents et ceux de ses projets ; plusieurs :
 * tous ceux que `GET /documents` rend, déjà filtrés par le serveur
 * (`best_document_role`), rien n'est masqué ici qui aurait été reçu.
 *
 * Le dépôt est celui de « Mes documents » : le fichier choisi ou lâché ouvre
 * `UploadDocumentDialog` (dossier, nom, monuments), puis « Gérer l'accès ».
 * Glisser un fichier n'importe où sur la page pose le voile `.gdrop`, sauf
 * derrière le paywall (`inert`) et quand une fenêtre est déjà ouverte.
 */
export function DocumentsTableau({ monuments, projets }: { monuments: Monument[]; projets: Projet[] }) {
  const documents = useDocumentStore((s) => s.documents);
  const loading = useDocumentStore((s) => s.loading);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const userId = useAuthStore((s) => s.user?.id);

  const [depot, setDepot] = useState<File[] | null>(null);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [nouveaux, setNouveaux] = useState<Set<string>>(new Set());
  const [glisse, setGlisse] = useState(false);
  const racine = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  useEffect(() => {
    if (nouveaux.size === 0) return;
    const t = setTimeout(() => setNouveaux(new Set()), 1600);
    return () => clearTimeout(t);
  }, [nouveaux]);

  const seul = monuments.length === 1 ? monuments[0] : null;
  const docs = useMemo(() => {
    if (!seul) return documents;
    const ids = projets.filter((p) => p.monumentId === seul.id).map((p) => p.id);
    return documents.filter((d) => documentDuMonument(d, seul.id, ids));
  }, [documents, projets, seul]);

  const comptes = compterParType(docs);
  const dossiers = TYPES_DOSSIERS.filter((t) => DOSSIERS_TOUJOURS.includes(t) || comptes[t]);
  const derniers = documentsRecents(docs, NB_DERNIERS);
  const lien = seul ? `${ROUTES.DOCUMENTS}?monument=${encodeURIComponent(seul.id)}` : ROUTES.DOCUMENTS;
  const titre = seul ? `Les documents ${monumentNomCourt(seul.nom, true) ?? 'de ce monument'}` : 'Les documents de vos monuments';

  // Rattachement du dépôt, comme sur « Mes documents » : au monument quand on
  // est de son équipe, sinon à ses chantiers ouverts. Plusieurs monuments : la
  // fenêtre d'ajout laisse cocher lesquels.
  const membre = !!seul && (!!seul.myRole || seul.userId === userId || !!seul.depuisLeCache);
  const depotMonuments = seul && membre ? [seul.id] : [];
  const depotProjets = seul && !membre
    ? projets.filter((p) => p.monumentId === seul.id && !p.clotureAt).map((p) => p.id)
    : [];

  const fenetreOuverte = !!depot || !!accessDoc || !!previewDoc;

  // Le voile plein écran : un fichier glissé depuis l'ordinateur, où que soit
  // le pointeur. Le compteur de profondeur évite le clignotement d'un enfant à l'autre.
  useEffect(() => {
    if (fenetreOuverte) return;
    let profondeur = 0;
    const bloque = () => !racine.current || !!racine.current.closest('[inert]');
    const fin = () => { profondeur = 0; setGlisse(false); };
    const entree = (e: DragEvent) => {
      if (!glisseDesFichiers(e) || bloque()) return;
      e.preventDefault();
      profondeur += 1;
      setGlisse(true);
    };
    const survol = (e: DragEvent) => { if (glisseDesFichiers(e) && !bloque()) e.preventDefault(); };
    const sortie = () => { profondeur = Math.max(0, profondeur - 1); if (profondeur === 0) fin(); };
    const lacher = (e: DragEvent) => {
      if (!glisseDesFichiers(e) || bloque()) return;
      e.preventDefault();
      fin();
      const fichiers = [...(e.dataTransfer?.files ?? [])];
      if (fichiers.length) setDepot(fichiers);
    };
    window.addEventListener('dragenter', entree);
    window.addEventListener('dragover', survol);
    window.addEventListener('dragleave', sortie);
    window.addEventListener('drop', lacher);
    return () => {
      window.removeEventListener('dragenter', entree);
      window.removeEventListener('dragover', survol);
      window.removeEventListener('dragleave', sortie);
      window.removeEventListener('drop', lacher);
      setGlisse(false);
    };
  }, [fenetreOuverte]);

  const choisir = () => {
    const input = inputRef.current;
    if (!input) return;
    input.value = '';
    input.click();
  };

  const roleSur = (d: Document): ProjectRole | null => meilleurRole([
    ...d.monumentIds.map((id) => {
      const m = monuments.find((x) => x.id === id);
      return m?.myRole ?? (m && m.userId === userId ? 'owner' : null);
    }),
    ...d.projetIds.map((id) => projets.find((p) => p.id === id)?.myRole),
  ]);

  const apresDepot = (deposes: Document[]) => {
    setNouveaux(new Set(deposes.map((d) => d.id)));
    // Comme « Mes documents » : le document part avec un défaut sûr (chef et
    // adjoints), « Gérer l'accès » s'ouvre pour que l'auteur choisisse.
    if (deposes.length === 1 && deposes[0].monumentIds.length > 0) setAccessDoc(deposes[0]);
  };

  return (
    <section className="sec" aria-labelledby="docT" ref={racine}>
      <div className="sec-h">
        <div>
          <span className="eyebrow">Vos documents</span>
          <h2 id="docT">{titre}</h2>
          <p>Une pièce déposée une fois sert à tous vos dossiers.</p>
        </div>
        <Link className="btn b-blue" to={lien}>
          Ouvrir mes documents
          <Picto nom="fleche" />
        </Link>
      </div>
      <div className="dc">
        <div>
          <div className="folds">
            {dossiers.map((t) => (
              <Link key={t} className="fo" to={lien}>
                <PictoDossierPlein className="i" />
                {dossierLabel(t)} <em>{comptes[t] ?? 0}</em>
              </Link>
            ))}
          </div>
          <div className="dc-h"><b>Derniers ajouts</b></div>
          {loading && docs.length === 0 ? (
            <div className="rec" aria-hidden="true">
              <span className="sk" style={{ height: 52, borderRadius: 12 }} />
            </div>
          ) : derniers.length === 0 ? (
            <p className="rec-vide">Aucun document pour l'instant.</p>
          ) : (
            <ul className="rec">
              {derniers.map((d) => {
                const ext = formatFichier(d.nomFichier);
                const quand = dateCourte(d.dateUpload);
                return (
                  <li key={d.id} className={nouveaux.has(d.id) ? 'new' : undefined}>
                    <button type="button" onClick={() => setPreviewDoc(d)}>
                      <span className={estImage(ext, d.mimeType) ? 'ext img' : 'ext'}>{ext}</span>
                      <span>
                        <b>{d.nom}</b>
                        <small>{quand ? `${dossierLabel(d.type)} · ${quand}` : dossierLabel(d.type)}</small>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div className={glisse ? 'dc-drop over' : 'dc-drop'}>
          <span className="up" aria-hidden="true"><Picto nom="envoyer" /></span>
          <b>Glissez un fichier ici</b>
          <p>Devis, photos, arrêté de protection : vous choisirez ensuite son dossier.</p>
          <button className="btn b-blue b-sm" type="button" onClick={choisir}>Choisir un fichier</button>
        </div>
        <div className="dc-f">
          <span>{plur(docs.length, 'document')} · {tailleFichier(tailleTotale(docs))}</span>
          <span>Vos documents restent privés.</span>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple
        className="sr"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const fichiers = [...(e.target.files ?? [])];
          if (fichiers.length) setDepot(fichiers);
        }}
      />
      {glisse && (
        <div className="gdrop" aria-hidden="true">
          <div>
            <b>Déposez votre fichier</b>
            <p>Il sera rangé dans Mes documents.</p>
          </div>
        </div>
      )}

      <UploadDocumentDialog
        open={!!depot}
        onOpenChange={(o) => { if (!o) setDepot(null); }}
        onUploaded={apresDepot}
        fichiers={depot ?? undefined}
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
      />
    </section>
  );
}
