import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { CarteMonument } from '@/components/dashboard/CarteMonument';
import { BoutonNouvelleRecherche, CarteNouveauProjet } from '@/components/dashboard/NouvelleRecherche';
import { useNouvelleRecherche } from '@/components/dashboard/useNouvelleRecherche';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ProjectListSkeleton } from '@/components/skeletons';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { computeMonumentStats, projectStage } from '@/lib/project-stats';
import { documentDuMonument } from '@/lib/pieces-a-deposer';
import { useProjectsData } from '@/hooks/useProjectsData';
import { useOffre } from '@/hooks/useOffre';
import { libelleMonuments, sousLePlafond } from '@/lib/offres';
import { PaywallDialog } from '@/components/shared/Paywall';
import { useAuthStore } from '@/stores/useAuthStore';
import { ROUTES } from '@/constants/routes';
import type { Projet } from '@/types';
import '@/components/dashboard/nouvelle-recherche.css';
import './liste-monuments.css';

type MonumentSortKey = 'recent' | 'oldest' | 'name' | 'modified';

/**
 * « Mes monuments » : maquette `monumia-mes-monuments.html`. Un monument par
 * ligne, chacun avec ses projets et trois boutons (documents, nouvelle
 * recherche, projets), puis le bandeau « nouveau projet », centré (demande de
 * Félix, la maquette met le bouton à droite).
 */
export function MonumentsListPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const projets = useProjetStore((s) => s.projets);
  const dossiers = useDossierStore((s) => s.dossiers);
  const digestsByProjet = useAideStore((s) => s.digestsByProjet);
  const suivis = useSuiviStore((s) => s.suivis);
  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const recherche = useNouvelleRecherche();

  // Charge monuments, projets, dossiers, diagnostics et suivis ; `loading` ne
  // retombe qu'une fois TOUT arrivé, pour que le squelette couvre aussi le
  // nombre d'aides (sinon les cartes s'affichent vides puis sautent).
  const { loading } = useProjectsData();
  // Le compteur « Documents » de chaque carte : la liste de `GET /documents`,
  // déjà filtrée par le serveur.
  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const [paywallMonument, setPaywallMonument] = useState(false);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<MonumentSortKey>('recent');

  const visibleMonuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = q
      ? monuments.filter(
          (m) =>
            m.nom.toLowerCase().includes(q) ||
            (m.commune?.toLowerCase().includes(q) ?? false)
        )
      : monuments;

    const sorted = [...filtered];
    switch (sortKey) {
      case 'recent':
        sorted.sort(
          (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
        break;
      case 'oldest':
        sorted.sort(
          (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        );
        break;
      case 'name':
        sorted.sort((a, b) => a.nom.localeCompare(b.nom, 'fr', { sensitivity: 'base' }));
        break;
      case 'modified':
        sorted.sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
        break;
    }
    return sorted;
  }, [monuments, search, sortKey]);

  // Plafond de l'offre : le bouton de création laisse place à la porte de
  // sortie quand le compte a déjà son quota de monuments. Le comptage porte sur
  // les monuments POSSÉDÉS — un bien partagé par quelqu'un d'autre ne consomme
  // rien, exactement comme côté serveur (services/quotas.py).
  const offre = useOffre();
  const mesMonuments = user ? monuments.filter((m) => m.userId === user.id).length : 0;
  const peutCreer = sousLePlafond(offre.monumentsMax, mesMonuments);

  // Le bouton garde son libellé et son geste, et c'est le paywall qui se pose
  // devant quand le plafond est atteint : refermer la modale laisse
  // l'utilisateur sur sa liste, ce qu'une redirection vers les tarifs ne
  // permet pas. `Link` quand l'action est ouverte, `button` sinon — un lien
  // qui n'emmène nulle part mentirait au survol comme au clic milieu.
  const newMonumentButton = (className: string) => peutCreer ? (
    <Link className={className} to={ROUTES.MONUMENT_NEW}>
      <Picto nom="plus" />
      Nouveau monument
    </Link>
  ) : (
    <button className={className} type="button" onClick={() => setPaywallMonument(true)}>
      <Picto nom="plus" />
      Nouveau monument
    </button>
  );

  // L'étape de chaque projet, affichée en points sur sa ligne.
  const etapeDe = (p: Projet) =>
    projectStage(
      digestsByProjet[p.id] ?? null,
      dossiers.filter((d) => d.projetId === p.id),
      suivis.filter((x) => x.projetId === p.id),
    );

  const documentsDe = (monumentId: string) => {
    const ids = projets.filter((p) => p.monumentId === monumentId).map((p) => p.id);
    return documents.filter((d) => documentDuMonument(d, monumentId, ids)).length;
  };
  const peutChercher = new Set(recherche.candidats.map((m) => m.id));

  return (
    <div className="ec mlist">
      <div className="hello">
        <div>
          <h1>{libelleMonuments(offre)}</h1>
          <p>Chaque monument, ses projets de travaux et les aides qui vont avec.</p>
        </div>
        <div className="hello-acts">
          {newMonumentButton('btn b-line b-lg')}
          <BoutonNouvelleRecherche recherche={recherche} nbMonuments={monuments.length}>
            Nouvelle recherche d'aides
          </BoutonNouvelleRecherche>
        </div>
      </div>

      {loading ? (
        <div style={{ marginTop: 26 }}>
          <ProjectListSkeleton />
        </div>
      ) : monuments.length === 0 ? (
        <div className="vide" style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: 24 }}>Aucun monument pour le moment</h2>
          <p style={{ margin: '9px auto 20.5px', maxWidth: '52ch' }}>
            Décrivez votre monument, puis lancez autant de projets de travaux que nécessaire pour identifier les
            aides mobilisables.
          </p>
          {newMonumentButton('btn b-orange')}
        </div>
      ) : (
        <>
          {/* Recherche et tri : utiles seulement quand la liste devient longue.
              La plupart des comptes ont 1-2 monuments — on leur épargne ce bruit. */}
          {monuments.length > 3 && (
            <div className="tools">
              <label className="search">
                <span className="sr">Rechercher un monument</span>
                <Picto nom="loupe" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Rechercher un monument"
                />
              </label>
              <div className="sel">
                <label className="sr" htmlFor="tri-monuments">
                  Trier les monuments
                </label>
                <select
                  id="tri-monuments"
                  value={sortKey}
                  onChange={(e) => setSortKey(e.target.value as MonumentSortKey)}
                >
                  <option value="recent">Créés récemment</option>
                  <option value="oldest">Plus anciens</option>
                  <option value="modified">Récemment modifiés</option>
                  <option value="name">Nom (A → Z)</option>
                </select>
              </div>
            </div>
          )}

          {visibleMonuments.length === 0 ? (
            <p className="vide">Aucun monument ne correspond à votre recherche.</p>
          ) : (
            <div className="cmons">
              {visibleMonuments.map((monument) => (
                <CarteMonument
                  key={monument.id}
                  monument={monument}
                  projets={projets.filter((p) => p.monumentId === monument.id)}
                  stats={computeMonumentStats(monument, projets, digestsByProjet, dossiers)}
                  etapeDe={etapeDe}
                  nbDocuments={documentsDe(monument.id)}
                  variante="liste"
                  onNouvelleRecherche={peutChercher.has(monument.id) ? () => recherche.lancer(monument.id) : undefined}
                />
              ))}
            </div>
          )}
          <CarteNouveauProjet recherche={recherche} nbMonuments={monuments.length} bande />
        </>
      )}

      <PaywallDialog
        open={paywallMonument}
        onOpenChange={setPaywallMonument}
        offre="Multi-monuments"
        titre="Gérez tout votre parc au même endroit"
        description="L'offre gratuite couvre un monument. Multi-monuments les rend illimités et ouvre le tableau de bord, qui réunit leurs chantiers et leurs échéances."
      />
      {recherche.dialogue}
    </div>
  );
}
