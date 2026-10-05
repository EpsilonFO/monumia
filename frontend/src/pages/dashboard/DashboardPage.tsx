import { useEffect, useMemo } from 'react';
import { Link } from 'react-router';
import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { AFaireMaintenantCarte } from '@/components/dashboard/AFaireMaintenantCarte';
import { CarteMonument } from '@/components/dashboard/CarteMonument';
import { DocumentsTableau } from '@/components/dashboard/DocumentsTableau';
import { BoutonNouvelleRecherche, CarteNouveauProjet } from '@/components/dashboard/NouvelleRecherche';
import { useNouvelleRecherche } from '@/components/dashboard/useNouvelleRecherche';
import { Picto } from '@/components/shared/ecrans/Picto';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useProjectsData } from '@/hooks/useProjectsData';
import { ROUTES } from '@/constants/routes';
import { aFaireMaintenant, type AFaire } from '@/lib/a-faire-maintenant';
import { mergeProjectDeadlines, computeMonumentStats, projectStage } from '@/lib/project-stats';
import type { MonumentStats } from '@/lib/project-stats';
import { documentDuMonument } from '@/lib/pieces-a-deposer';
import type { ProjectDigest, Projet } from '@/types';
import '@/components/dashboard/nouvelle-recherche.css';
import './tableau-de-bord.css';

/** La phrase sous le bonjour : ce que dit la date la plus proche. Sans date,
 *  la carte « Tout est à jour » le dit déjà : pas de phrase. */
function phraseDuJour(a: AFaire): string {
  const quand = format(parseISO(a.echeance.date), 'd MMMM', { locale: fr });
  if (a.echeance.joursRestants < 0) return `Une échéance est dépassée : ${a.titre}, prévue le ${quand}.`;
  if (a.nature === 'dossier') return `Une échéance approche : ${a.detail}, le ${quand}.`;
  return `Une date approche : ${a.titre} ferme le ${quand}.`;
}

/**
 * Tableau de bord, dessiné comme la maquette `monumia-tableau-de-bord.html` :
 * le bonjour et ses deux boutons, la chose à faire maintenant (la date la plus
 * proche), chaque monument avec ses projets puis la carte « nouveau projet »,
 * et enfin l'espace documents.
 */
export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const projets = useProjetStore((s) => s.projets);
  const digestsByProjet = useAideStore((s) => s.digestsByProjet);
  const suivis = useSuiviStore((s) => s.suivis);
  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const recherche = useNouvelleRecherche();

  // Charge monuments, dossiers, digests d'aides et suivis en un seul appel :
  // tout arrive ensemble, donc les squelettes couvrent aussi le nombre d'aides
  // et l'avancement sans que les cartes « sautent ».
  const { loading } = useProjectsData();
  // Les documents comptent sur les cartes et dans l'espace documents ; le store
  // partage la requête si les deux la lancent ensemble.
  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user],
  );

  // Cartes « Vos monuments » : les vôtres + ceux partagés avec vous (le store
  // ne contient que des monuments accessibles). « À faire maintenant » reste
  // sur `userMonuments`.
  const displayMonuments = monuments;

  const diagMap = useMemo<Record<string, ProjectDigest | null>>(() => {
    const out: Record<string, ProjectDigest | null> = {};
    for (const p of projets) out[p.id] = digestsByProjet[p.id] ?? null;
    return out;
  }, [projets, digestsByProjet]);

  const userDossiers = useMemo(
    () => (user ? dossiers.filter((d) => d.userId === user.id) : []),
    [dossiers, user],
  );

  // Toutes les échéances, de la plus proche à la plus lointaine. Un dossier en
  // retard passe en tête : c'est ce qu'il faut faire en premier.
  const aFaire = useMemo(() => {
    const monumentIds = new Set(userMonuments.map((m) => m.id));
    const echeances = projets
      .filter((p) => monumentIds.has(p.monumentId))
      .flatMap((p) => mergeProjectDeadlines(diagMap[p.id] ?? null, userDossiers.filter((d) => d.projetId === p.id)))
      .sort((a, b) => a.joursRestants - b.joursRestants);
    return aFaireMaintenant(echeances, diagMap, userDossiers, userMonuments);
  }, [userMonuments, projets, diagMap, userDossiers]);

  const statsByMonument = useMemo<Record<string, MonumentStats>>(() => {
    const out: Record<string, MonumentStats> = {};
    for (const m of displayMonuments) out[m.id] = computeMonumentStats(m, projets, diagMap, dossiers);
    return out;
  }, [displayMonuments, projets, diagMap, dossiers]);

  // L'étape de chaque projet, affichée en points sur sa ligne.
  const etapeDe = (p: Projet) =>
    projectStage(
      diagMap[p.id] ?? null,
      dossiers.filter((d) => d.projetId === p.id),
      suivis.filter((s) => s.projetId === p.id),
    );

  // « 1 document prêt pour vos dossiers » : ceux du monument et de ses projets
  // (la liste vient de `GET /documents`, chargée par l'espace documents).
  const documentsParMonument = useMemo<Record<string, number>>(() => {
    const out: Record<string, number> = {};
    for (const m of displayMonuments) {
      const ids = projets.filter((p) => p.monumentId === m.id).map((p) => p.id);
      out[m.id] = documents.filter((d) => documentDuMonument(d, m.id, ids)).length;
    }
    return out;
  }, [displayMonuments, projets, documents]);

  if (!user) return null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Bonjour' : hour < 18 ? 'Bon après-midi' : 'Bonsoir';
  const jour = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="ec tdb">
      <div className="hello">
        <div>
          <span className="eyebrow">{jour.charAt(0).toUpperCase() + jour.slice(1)}</span>
          <h1>
            {greeting}, <span>{user.prenom}</span>
          </h1>
          {!loading && aFaire && <p>{phraseDuJour(aFaire)}</p>}
        </div>
        <div className="hello-acts">
          <Link className="btn b-line b-lg" to={ROUTES.MONUMENT_NEW}>
            <Picto nom="plus" />
            {userMonuments.length === 0 ? 'Créer un monument' : 'Nouveau monument'}
          </Link>
          <BoutonNouvelleRecherche recherche={recherche} nbMonuments={displayMonuments.length}>
            Nouvelle recherche d'aides
          </BoutonNouvelleRecherche>
        </div>
      </div>

      {loading ? (
        <div className="now" aria-hidden="true">
          <div className="now-in">
            <span className="sk" style={{ width: 91, height: 100.5, borderRadius: 16 }} />
            <div style={{ display: 'grid', gap: 11 }}>
              <span className="sk" style={{ width: 218.5, height: 13 }} />
              <span className="sk" style={{ width: '70%', height: 24 }} />
              <span className="sk" style={{ width: '55%', height: 16 }} />
            </div>
            <span className="sk" style={{ width: 209.5, height: 48, borderRadius: 999 }} />
          </div>
        </div>
      ) : (
        <AFaireMaintenantCarte aFaire={aFaire} />
      )}

      <section className="sec" aria-labelledby="monT">
        <div className="sec-h">
          <div>
            <span className="eyebrow">Vos monuments</span>
            <h2 id="monT">Où en sont vos projets</h2>
          </div>
        </div>
        {loading ? (
          <div className="cmons" aria-hidden="true">
            {[0, 1].map((i) => (
              <div key={i} className="cmon">
                <div className="cmon-h" style={{ height: 103.5 }} />
                <div className="cmon-b">
                  <span className="sk" style={{ width: '60%', height: 20.5 }} />
                  <span className="sk" style={{ width: '100%', height: 56 }} />
                  <span className="sk" style={{ width: '40%', height: 16 }} />
                </div>
              </div>
            ))}
          </div>
        ) : displayMonuments.length === 0 ? (
          <p className="vide">
            Aucun monument pour l'instant. Commencez par la fiche de votre monument : Monumia en déduit les aides
            auxquelles il peut prétendre.
          </p>
        ) : (
          <div className="cmons">
            {displayMonuments.map((m) => (
              <CarteMonument
                key={m.id}
                monument={m}
                projets={projets.filter((p) => p.monumentId === m.id)}
                stats={statsByMonument[m.id]}
                etapeDe={etapeDe}
                nbDocuments={documentsParMonument[m.id] ?? 0}
              />
            ))}
            <CarteNouveauProjet recherche={recherche} nbMonuments={displayMonuments.length} />
          </div>
        )}
      </section>

      {!loading && displayMonuments.length > 0 && (
        <DocumentsTableau monuments={displayMonuments} projets={projets} />
      )}
      {recherche.dialogue}
    </div>
  );
}
