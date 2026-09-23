import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { IconDossierOuvert, IconAjouterDossier } from '@/components/icons';
import { AideDetails } from '@/components/aide/AideDetails';
import { AideHero } from '@/components/aide/AideHero';
import { getDisponibilite } from '@/components/aide/eligibility-status';
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

  const [aide, setAide] = useState<Aide | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [opening, setOpening] = useState(false);
  const [envoiReponse, setEnvoiReponse] = useState(false);

  const projetFetchedRef = useRef(false);

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

  // L'aide telle que le diagnostic la rapporte — sauf quand il n'en rapporte
  // qu'un RÉSUMÉ : une non éligible que la liste n'affiche pas arrive sans ses
  // pièces ni sa démarche (cf. `resumer_non_eligibles` côté serveur), et la
  // fiche complète se demande alors à part.
  useEffect(() => {
    if (!aideId) return;
    const fromDiagnostic = matchResult && !matchResult.resume ? matchResult.aide : null;
    if (fromDiagnostic) { setAide(fromDiagnostic); return; }
    aideService.getById(aideId).then(setAide).catch(() => setNotFound(true));
  }, [aideId, matchResult]);

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

  const cta = (
    <button
      onClick={handleOpenOrView}
      disabled={opening}
      className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-[13px] font-semibold text-white transition-all duration-200 hover:shadow-md disabled:opacity-60"
      style={{ background: existingDossier ? C.blue : C.orange }}
    >
      {opening ? <Loader2 className="h-4 w-4 animate-spin" /> : existingDossier ? <IconDossierOuvert className="h-4 w-4" /> : <IconAjouterDossier className="h-4 w-4" />}
      {existingDossier ? 'Voir le dossier' : 'Ouvrir un dossier'}
    </button>
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 overflow-hidden text-[13px] text-muted-foreground">
        <Link to={ROUTES.MONUMENTS} className="shrink-0 hover:opacity-70 transition-opacity">{libelleMonuments(offreCompte)}</Link>
        <span>/</span>
        <Link to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`} className="truncate hover:opacity-70 transition-opacity">{monument.nom}</Link>
        <span>/</span>
        <Link to={ROUTES.PROJET_DETAIL(projet.id)} className="truncate hover:opacity-70 transition-opacity">{projetTitre(projet)}</Link>
        <span>/</span>
        <span className="truncate" style={{ color: C.ink }}>{aide.nomCourt}</span>
      </div>

      <AideHero aide={aide} matchResult={matchResult} cta={cta} />

      <AideDetails
        aide={aide}
        matchResult={matchResult}
        monumentName={monument.nom}
        showHeader={false}
        questions={diagnostic?.qcmQuestions}
        answers={projet.questionnaire ?? {}}
        onRepondre={handleRepondre}
        envoiEnCours={envoiReponse}
      />
    </div>
  );
}
