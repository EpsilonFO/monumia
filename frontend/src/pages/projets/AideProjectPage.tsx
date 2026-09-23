import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { getDisponibilite, getEligibilityStatus } from '@/components/aide/eligibility-status';
import { FicheAvantDepot } from '@/components/aide/fiche/FicheAvantDepot';
import { FicheBarre, type ActionBarre } from '@/components/aide/fiche/FicheBarre';
import { FicheConseils, FicheEtapes } from '@/components/aide/fiche/FicheConseils';
import { FicheBandeauGuichet, FicheEnBref } from '@/components/aide/fiche/FicheEnBref';
import { FicheEligibilite } from '@/components/aide/fiche/FicheEligibilite';
import { FicheEssentiel } from '@/components/aide/fiche/FicheEssentiel';
import { FichePieces } from '@/components/aide/fiche/FichePieces';
import { FicheReglement, type FicheReglementHandle } from '@/components/aide/fiche/FicheReglement';
import { useApparition } from '@/components/aide/fiche/useFiche';
import '@/components/aide/fiche/fiche-aide.css';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAideStore } from '@/stores/useAideStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { projectPermissions } from '@/lib/project-permissions';
import { isAccessLostError } from '@/lib/api-error';
import {
  useOffre, useOffreMonument, useOffreChargee, useOffreMonumentConnue,
} from '@/hooks/useOffre';
import { libelleMonuments } from '@/lib/offres';
import {
  CLASSE_GUICHET,
  chapeauAide,
  etapesAide,
  financeurAide,
  guichet as guichetDe,
  libelleType,
  piecesAide,
  reglementDe,
  titreAide,
} from '@/lib/fiche-aide';
import { idProjetYbug } from '@/lib/ybug';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { projetTitre } from '@/lib/projet-titre';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Aide, AideMatchResult } from '@/types';

/**
 * Fiche d'une aide, vue depuis un PROJET de travaux : c'est le projet qui donne
 * le contexte d'éligibilité (ses travaux, ses réponses) et qui recevra le
 * dossier. Le monument parent n'intervient que pour les droits et le paywall.
 *
 * La mise en page est la maquette du designer (monumia-fiches) : en-tête,
 * « L'essentiel » en colonne, puis En bref, éligibilité, conseils, étapes,
 * pièces et règlement complet. Les textes viennent de la fiche rédigée de l'aide
 * (`aide.fiche`) quand elle existe, des champs bruts sinon (cf. lib/fiche-aide).
 */
export function AideProjectPage() {
  const { projetId, aideId } = useParams();
  const navigate = useNavigate();

  const projet = useProjetStore((s) => s.projets.find((p) => p.id === projetId));
  const upsertProjet = useProjetStore((s) => s.upsertProjet);
  const repondreFait = useProjetStore((s) => s.repondreFait);
  const monumentId = projet?.monumentId;
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const upsertMonument = useMonumentStore((s) => s.upsertMonument);

  const diagnosticsByProjet = useAideStore((s) => s.diagnosticsByProjet);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  const dossiers = useDossierStore((s) => s.dossiers);
  const dossierLoaded = useDossierStore((s) => s.loaded);
  const setDossiers = useDossierStore((s) => s.setDossiers);

  const [charge, setCharge] = useState<{ id: string; aide: Aide } | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [opening, setOpening] = useState(false);
  const [envoiReponse, setEnvoiReponse] = useState(false);

  const projetFetchedRef = useRef(false);
  const titreRef = useRef<HTMLHeadingElement>(null);
  const reglementRef = useRef<FicheReglementHandle>(null);
  const apparition = useApparition<HTMLElement>();

  const diagnostic = projetId ? diagnosticsByProjet[projetId] ?? null : null;
  const matchResult: AideMatchResult | null = useMemo(() => {
    if (!diagnostic || !aideId) return null;
    return diagnostic.aidesEligibles.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesAtteignables?.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesPotentiellementEligibles.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesNonEligibles.find((m) => m.aide.id === aideId)
      ?? null;
  }, [diagnostic, aideId]);

  // L'onglet « Aides » et l'ouverture d'un dossier sont réservés au chef de projet
  // et à son adjoint. Le rôle se lit sur le PROJET : un collaborateur invité sur
  // le seul chantier n'en a aucun sur le monument. Un collaborateur qui
  // atteindrait cette page (lien direct) est renvoyé vers le projet.
  // Un projet relu du cache local n'a pas de rôle (cf. `projetPourLeCache`) :
  // inconnu n'est pas nul, et on ne renvoie personne avant la réponse du serveur.
  const canAccessAides = projet && !projet.depuisLeCache
    ? projectPermissions(projet.myRole ?? null).canAccessAides
    : true;

  // Le détail d'une aide est gratuit — sauf tant que son guichet n'est pas
  // ouvert : savoir à l'avance quelle aide va ouvrir est ce que l'offre Veille
  // vend. L'offre lue est celle qui gouverne le BIEN, comme sur la page du
  // projet, pour que l'équipe d'un client abonné voie la même chose que lui.
  const offre = useOffreMonument(monumentId);
  const offreCompte = useOffre();
  const offreChargee = useOffreChargee();
  // L'offre qui décide est celle du MONUMENT : un monument relu du cache local
  // ne la porte pas, et rediriger sur l'offre gratuite par défaut enverrait un
  // abonné aux tarifs à chaque rechargement.
  const offreMonumentConnue = useOffreMonumentConnue(monumentId);
  const locked =
    !offre.aidesBientot && !!matchResult && getDisponibilite(matchResult) === 'bientot';

  // Relu aussi quand il vient du cache local : c'est la réponse du serveur qui
  // porte le rôle, donc l'accès à cette fiche et le droit d'y répondre.
  const projetARelire = !projet || !!projet.depuisLeCache;
  useEffect(() => {
    if (!projetARelire || !projetId || projetFetchedRef.current) return;
    projetFetchedRef.current = true;
    projetService.getById(projetId).then(upsertProjet).catch((err) => {
      const enStore = useProjetStore.getState().projets.some((p) => p.id === projetId);
      if (!enStore || isAccessLostError(err)) setNotFound(true);
    });
  }, [projetARelire, projetId, upsertProjet]);

  // Relu aussi quand il vient du cache local, qui ne garde pas son offre : la
  // redirection des aides à venir attendrait sinon `GET /dashboard`. Une panne
  // passagère ne dit « introuvable » que s'il n'y a rien à montrer.
  const monumentARelire = !monument || !!monument.depuisLeCache;
  useEffect(() => {
    if (!monumentId || !monumentARelire) return;
    monumentService.getById(monumentId).then(upsertMonument).catch((err) => {
      const enStore = useMonumentStore.getState().monuments.some((m) => m.id === monumentId);
      if (!enStore || isAccessLostError(err)) setNotFound(true);
    });
  }, [monumentId, monumentARelire, upsertMonument]);

  useEffect(() => {
    if (projet && !canAccessAides && projetId) {
      navigate(ROUTES.PROJET_DETAIL(projetId), { replace: true });
    }
  }, [projet, canAccessAides, projetId, navigate]);

  useEffect(() => {
    // On attend la réponse du serveur : rediriger sur l'état initial (offre
    // gratuite par prudence) éjecterait un abonné à chaque rechargement.
    if (!offreChargee || !offreMonumentConnue || !locked || !monumentId) return;
    navigate(ROUTES.TARIFS(monumentId), { replace: true });
  }, [offreChargee, offreMonumentConnue, locked, monumentId, navigate]);

  // Le diagnostic complet porte les critères remplis / à débloquer affichés ici.
  // On l'obtient sur place quand il manque : le dashboard ne charge plus qu'un
  // digest par projet, donc arriver par une échéance ne le fournit plus.
  //
  // Même effet que sur la page du projet, et SANS garde `|| diagnostic` :
  // répondre depuis cette fiche change `projet.questionnaire`, et un diagnostic
  // déjà en store laisserait le verdict figé sur les réponses d'avant. Le
  // moteur est pur et coûte deux millisecondes : une relance à l'arrivée ne se
  // voit pas.
  const questionnaireKey = projet ? JSON.stringify(projet.questionnaire ?? {}) : '';
  useEffect(() => {
    if (!projetId || !questionnaireKey) return;
    let cancelled = false;
    aideService
      .runProjectDiagnostic(projetId, JSON.parse(questionnaireKey))
      .then((result) => { if (!cancelled) setDiagnostic(projetId, result); })
      .catch(console.error);
    return () => { cancelled = true; };
  }, [projetId, questionnaireKey, setDiagnostic]);

  // La fiche complète se demande toujours au serveur : le diagnostic n'emporte
  // de chaque aide que sa `carte`, ni la fiche rédigée ni le règlement cité. Si
  // la demande échoue, l'aide telle que le diagnostic la rapporte suffit à
  // afficher une page, en moins riche ; sans elle, l'aide est introuvable.
  //
  // L'aide chargée garde son id : passer à l'aide suivante ne montre pas la
  // précédente le temps de la requête.
  useEffect(() => {
    if (!aideId) return;
    let cancelled = false;
    aideService.getById(aideId).then((a) => { if (!cancelled) setCharge({ id: aideId, aide: a }); }).catch(() => {
      if (cancelled) return;
      const diag = projetId ? useAideStore.getState().diagnosticsByProjet[projetId] : undefined;
      const repli = diag && [
        ...diag.aidesEligibles,
        ...(diag.aidesAtteignables ?? []),
        ...diag.aidesPotentiellementEligibles,
        ...diag.aidesNonEligibles,
      ].find((m) => m.aide.id === aideId && !m.resume);
      if (repli) setCharge({ id: aideId, aide: repli.aide });
      else setNotFound(true);
    });
    return () => { cancelled = true; };
  }, [aideId, projetId]);
  const aide = charge && charge.id === aideId ? charge.aide : null;

  useEffect(() => {
    dossierService.fetchAll().then(setDossiers).catch(console.error);
  }, [setDossiers]);

  /**
   * Répondre depuis la fiche. Le droit est `canEditProject` (= co_owner),
   * miroir de ce qu'exige `update_projet` : proposer un formulaire qu'un 403
   * refuserait serait pire que de ne rien proposer. Aucune relance manuelle du
   * diagnostic — le questionnaire mis à jour suffit à déclencher l'effet.
   */
  const peutRepondre = !!projet && projectPermissions(projet.myRole ?? null).canEditProject;
  const handleRepondre = useMemo(
    () =>
      peutRepondre && projetId
        ? async (factKey: string, value: string | string[] | undefined) => {
            setEnvoiReponse(true);
            try {
              await repondreFait(projetId, factKey, value);
            } catch (err) {
              toast.error(
                err instanceof Error ? err.message : "Votre réponse n'a pas pu être enregistrée",
              );
            } finally {
              setEnvoiReponse(false);
            }
          }
        : undefined,
    [peutRepondre, projetId, repondreFait],
  );

  const existingDossier = useMemo(
    () => dossiers.find((d) => d.projetId === projetId && d.aideId === aideId) ?? null,
    [dossiers, projetId, aideId],
  );

  const handleOpenOrView = async () => {
    if (!projetId || !aideId || !projet) return;
    setOpening(true);
    try {
      // Garde anti-doublon : le backend ne dédoublonne pas sur (projet, aide).
      // Si le store n'est pas encore hydraté, on rafraîchit avant de décider.
      let target = existingDossier;
      if (!target && !dossierLoaded) {
        const all = await dossierService.fetchAll().catch(() => []);
        target = all.find((d) => d.projetId === projetId && d.aideId === aideId) ?? null;
      }
      if (target) {
        navigate(ROUTES.PROJET_DOSSIER(projetId, target.id));
        return;
      }
      // Les travaux du dossier sont ceux du PROJET : c'est son cadrage qui dit
      // sur quoi porte la candidature.
      const created = await dossierService.create(projetId, aideId, projet.travauxEnvisages ?? []);
      navigate(ROUTES.PROJET_DOSSIER(projetId, created.id));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du dossier');
    } finally {
      setOpening(false);
    }
  };

  // Les voisines de l'aide, dans l'ordre du diagnostic, pour « Aide précédente /
  // suivante ». Une aide à venir hors offre n'y figure pas : elle mènerait aux
  // tarifs, pas à une fiche.
  const voisines = useMemo(() => {
    if (!diagnostic || !aideId) return { avant: null, apres: null };
    const liste = [
      ...diagnostic.aidesEligibles,
      ...(diagnostic.aidesAtteignables ?? []),
      ...diagnostic.aidesPotentiellementEligibles,
    ].filter((m) => offre.aidesBientot || getDisponibilite(m) !== 'bientot');
    const i = liste.findIndex((m) => m.aide.id === aideId);
    if (i < 0) return { avant: null, apres: null };
    return { avant: liste[i - 1]?.aide.id ?? null, apres: liste[i + 1]?.aide.id ?? null };
  }, [diagnostic, aideId, offre.aidesBientot]);

  if (notFound) {
    return (
      <div className="space-y-4">
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Aide introuvable</h1>
        <Link to={projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour au projet
        </Link>
      </div>
    );
  }

  // `locked` fait partie du garde : sans lui, la fiche complète s'afficherait le
  // temps d'un rendu avant que la redirection de l'effet ne prenne effet. Le
  // serveur refuse de toute façon GET /aides/{id} sur une aide à venir hors
  // offre — ceci évite seulement l'à-coup visuel.
  if (!aide || !projet || !monument || !canAccessAides || locked) {
    return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} /></div>;
  }

  const g = guichetDe(aide);
  const titre = titreAide(aide);
  const reglement = reglementDe(aide);
  const tousLesPoints = [...reglement.demarches, ...reglement.rubriques.flatMap((r) => r.points)];
  const numeros = new Map(tousLesPoints.map((p) => [p.id, p.n]));
  const titres = new Map(tousLesPoints.map((p) => [p.id, p.titre]));
  const resumes = new Map((aide.reglement ?? []).map((c) => [c.text, aide.fiche?.points[c.id]?.resume || c.text]));
  const pieces = piecesAide(aide, existingDossier);
  const statut = matchResult ? getEligibilityStatus(matchResult) : null;
  // Une aide écartée n'a rien à préparer : le bloc se tait.
  const avecDemarches = reglement.demarches.length > 0 && statut !== 'non-eligible';
  const plansDemarche = new Map(
    (matchResult?.llmEvaluation?.evaluations ?? []).flatMap((e) =>
      e.conditionId && e.demarche ? [[e.conditionId, e.demarche] as const] : [],
    ),
  );
  const lienProjet = ROUTES.PROJET_DETAIL(projet.id);
  const sources = [
    ...(aide.urlOfficielle ? [{ libelle: 'Page officielle', url: aide.urlOfficielle, ico: 'externe' as const }] : []),
    ...(aide.formulaireUrl ? [{ libelle: 'Formulaire', url: aide.formulaireUrl, ico: 'formulaire' as const }] : []),
  ];

  const action: ActionBarre = existingDossier
    ? { libelle: 'Voir le dossier', onClick: handleOpenOrView }
    : statut === 'eligible'
      ? pieces.length ? { libelle: 'Réunir les pièces', ancre: 'pieces' } : { libelle: 'Commencer mon dossier', onClick: handleOpenOrView }
      : statut === 'non-eligible'
        ? { libelle: 'Autres aides', vers: lienProjet }
        : matchResult
          ? { libelle: 'Vérifier mon éligibilité', ancre: 'eligibilite' }
          : { libelle: 'Lire le règlement', ancre: 'reglement' };
  const signaler = idProjetYbug() ? () => window.Ybug?.open?.() : undefined;

  return (
    <div className="fa">
      <FicheBarre
        titre={titre}
        sousTitre={g.libelle}
        etape={statut === 'eligible' ? (existingDossier ? 'depot' : 'pieces') : 'elig'}
        action={action}
        repere={titreRef}
      />
      <div className="page">
        <div className="head">
          <p className="crumbs">
            <Link to={ROUTES.MONUMENTS}>{libelleMonuments(offreCompte)}</Link><span>/</span>
            <Link to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`}>{monument.nom}</Link><span>/</span>
            <Link to={lienProjet}>{projetTitre(projet)}</Link><span>/</span>
            {titre}
          </p>
          <section className="top">
            <p className="tags">
              <b className="tag-fin">{financeurAide(aide)}</b>
              <span className="tag-type">{libelleType(aide)}</span>
              <span className={`status ${CLASSE_GUICHET[g.etat]}`}><i />{g.libelle}</span>
            </p>
            <h1 ref={titreRef}>{titre}</h1>
            <p className="lede">{chapeauAide(aide)}</p>
          </section>
        </div>

        <aside className="side" aria-labelledby="ess-t">
          <FicheEssentiel aide={aide} guichet={g} onSignaler={signaler} />
        </aside>

        <div className="body">
          <FicheBandeauGuichet guichet={g} />
          <FicheEnBref aide={aide} />
          {matchResult && (
            <FicheEligibilite
              key={aide.id}
              match={matchResult}
              questions={diagnostic?.qcmQuestions ?? []}
              answers={projet.questionnaire ?? {}}
              onRepondre={handleRepondre}
              envoiEnCours={envoiReponse}
              titres={titres}
              resumes={resumes}
              dossierOuvert={!!existingDossier}
              ouverture={opening}
              onDossier={handleOpenOrView}
              lienAutres={lienProjet}
              nbDemarches={avecDemarches ? reglement.demarches.length : 0}
            />
          )}
          {avecDemarches && (
            <FicheAvantDepot
              demarches={reglement.demarches}
              plans={plansDemarche}
              onOuvrirPoint={(id) => reglementRef.current?.ouvrirPoint(id)}
            />
          )}
          <FicheConseils
            conseils={aide.fiche?.conseils ?? []}
            numeroDe={(id) => numeros.get(id)}
            onOuvrirPoint={(id) => reglementRef.current?.ouvrirPoint(id)}
          />
          {etapesAide(aide).length > 0 && (
            <section className="block reveal" ref={apparition}>
              <FicheEtapes etapes={etapesAide(aide)} />
            </section>
          )}
          {pieces.length > 0 && (
            <section className="block reveal" id="pieces" ref={apparition}>
              <FichePieces pieces={pieces} onAjouter={handleOpenOrView} ouverture={opening} />
            </section>
          )}
          <FicheReglement key={aide.id} reglement={reglement} sources={sources} ref={reglementRef} />
          <nav className="pager" aria-label="Autres aides">
            {voisines.avant
              ? <Link to={ROUTES.PROJET_AIDE(projet.id, voisines.avant)}>← Aide précédente</Link>
              : <span className="vide">← Aide précédente</span>}
            <Link to={lienProjet}>Toutes les aides</Link>
            {voisines.apres
              ? <Link to={ROUTES.PROJET_AIDE(projet.id, voisines.apres)}>Aide suivante →</Link>
              : <span className="vide">Aide suivante →</span>}
          </nav>
        </div>
      </div>
    </div>
  );
}
