import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { IconDossierOuvert, IconAjouterDossier } from '@/components/icons';
import { AideDetails } from '@/components/aide/AideDetails';
import { AideHero } from '@/components/aide/AideHero';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAideStore } from '@/stores/useAideStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { projectPermissions } from '@/lib/project-permissions';
import { useAidesAccess } from '@/hooks/useAidesAccess';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Aide, AideMatchResult } from '@/types';

export function AideProjectPage() {
  const { projetId, aideId } = useParams();
  const navigate = useNavigate();

  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === projetId));
  const addMonument = useMonumentStore((s) => s.addMonument);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  const dossiers = useDossierStore((s) => s.dossiers);
  const dossierLoaded = useDossierStore((s) => s.loaded);
  const setDossiers = useDossierStore((s) => s.setDossiers);

  const [aide, setAide] = useState<Aide | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [opening, setOpening] = useState(false);

  const monumentFetchedRef = useRef(false);

  const diagnostic = projetId ? diagnosticsByMonument[projetId] ?? null : null;
  const matchResult: AideMatchResult | null = useMemo(() => {
    if (!diagnostic || !aideId) return null;
    return diagnostic.aidesEligibles.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesAtteignables?.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesPotentiellementEligibles.find((m) => m.aide.id === aideId)
      ?? diagnostic.aidesNonEligibles.find((m) => m.aide.id === aideId)
      ?? null;
  }, [diagnostic, aideId]);

  // L'onglet « Aides » et l'ouverture d'un dossier sont réservés au chef de projet
  // et à son adjoint. Un collaborateur qui atteindrait cette page (lien direct) est
  // renvoyé vers le projet.
  const canAccessAides = monument ? projectPermissions(monument.myRole ?? null).canAccessAides : true;

  // Paywall : la fiche complète d'une aide est précisément ce que l'offre
  // « Dossier » vend. Sur un projet non débloqué, l'URL directe mène aux tarifs.
  const { locked, loading: accessLoading } = useAidesAccess(projetId);

  useEffect(() => {
    if (monument || !projetId || monumentFetchedRef.current) return;
    monumentFetchedRef.current = true;
    monumentService.getById(projetId).then(addMonument).catch(() => setNotFound(true));
  }, [monument, projetId, addMonument]);

  useEffect(() => {
    if (monument && !canAccessAides && projetId) {
      navigate(ROUTES.PROJET_DETAIL(projetId), { replace: true });
    }
  }, [monument, canAccessAides, projetId, navigate]);

  useEffect(() => {
    // On attend la réponse du serveur : rediriger sur l'état initial
    // (verrouillé par défaut) éjecterait un abonné à chaque rechargement.
    if (accessLoading || !locked || !projetId) return;
    navigate(ROUTES.TARIFS(projetId), { replace: true });
  }, [accessLoading, locked, projetId, navigate]);

  // Le diagnostic complet porte les critères remplis / à débloquer affichés ici.
  // On l'obtient sur place quand il manque : le dashboard ne charge plus qu'un
  // digest par projet, donc arriver par une échéance ne le fournit plus.
  const questionnaireKey = monument?.questionnaire ? JSON.stringify(monument.questionnaire) : '';
  useEffect(() => {
    if (!projetId || diagnostic) return;
    let cancelled = false;
    aideService
      .runProjectDiagnostic(projetId, questionnaireKey ? JSON.parse(questionnaireKey) : {})
      .then((result) => { if (!cancelled) setDiagnostic(projetId, result); })
      .catch(console.error);
    return () => { cancelled = true; };
  }, [projetId, diagnostic, questionnaireKey, setDiagnostic]);

  useEffect(() => {
    if (!aideId) return;
    const fromDiagnostic = matchResult?.aide;
    if (fromDiagnostic) { setAide(fromDiagnostic); return; }
    aideService.getById(aideId).then(setAide).catch(() => setNotFound(true));
  }, [aideId, matchResult]);

  useEffect(() => {
    dossierService.fetchAll().then(setDossiers).catch(console.error);
  }, [setDossiers]);

  const existingDossier = useMemo(
    () => dossiers.find((d) => d.monumentId === projetId && d.aideId === aideId) ?? null,
    [dossiers, projetId, aideId],
  );

  const handleOpenOrView = async () => {
    if (!projetId || !aideId || !monument) return;
    setOpening(true);
    try {
      // Garde anti-doublon : le backend ne dédoublonne pas sur (monument, aide).
      // Si le store n'est pas encore hydraté, on rafraîchit avant de décider.
      let target = existingDossier;
      if (!target && !dossierLoaded) {
        const all = await dossierService.fetchAll().catch(() => []);
        target = all.find((d) => d.monumentId === projetId && d.aideId === aideId) ?? null;
      }
      if (target) {
        navigate(ROUTES.PROJET_DOSSIER(projetId, target.id));
        return;
      }
      const created = await dossierService.create(projetId, aideId, monument.travauxEnvisages ?? []);
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
        <Link to={projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.PROJETS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour au projet
        </Link>
      </div>
    );
  }

  // `locked` fait partie du garde : sans lui, la fiche complète s'afficherait le
  // temps d'un rendu avant que la redirection de l'effet ne prenne effet.
  if (!aide || !monument || !canAccessAides || locked) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} /></div>;

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
      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Link to={ROUTES.PROJETS} className="hover:opacity-70 transition-opacity">Projets</Link>
        <span>/</span>
        <Link to={ROUTES.PROJET_DETAIL(monument.id)} className="hover:opacity-70 transition-opacity">{monument.nom}</Link>
        <span>/</span>
        <span className="truncate" style={{ color: C.ink }}>{aide.nomCourt}</span>
      </div>

      <AideHero aide={aide} matchResult={matchResult} cta={cta} />

      <AideDetails aide={aide} matchResult={matchResult} monumentName={monument.nom} showHeader={false} />
    </div>
  );
}
