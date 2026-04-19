import { useEffect, useMemo, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router';

/** Decode HTML entities (&#039; &amp; etc.) that may be present in aide text fields. */
const decodeHtml = (text: string | null | undefined): string => {
  if (!text) return '';
  const el = document.createElement('textarea');
  el.innerHTML = text;
  return el.value;
};
import {
  ChevronLeft, ExternalLink, Clock, Building2, FileText,
  CheckCircle2, XCircle, HelpCircle, ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { PageHeader } from '@/components/shared/PageHeader';
import { Disclaimer } from '@/components/shared/Disclaimer';
import { useAideStore, selectLastDiagnostic } from '@/stores/useAideStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useSegmentLabel } from '@/hooks/useSegment';
import { useAidesAccess } from '@/hooks/useAidesAccess';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { ROUTES } from '@/constants/routes';
import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import type { Aide, AideMatchResult } from '@/types';

export function AideDetailPage() {
  const { locked } = useAidesAccess();
  if (locked) {
    return <Navigate to="/tarifs" replace />;
  }
  const { aideId } = useParams();
  const navigate = useNavigate();
  const storeAide = useAideStore((s) => s.aides.find((a) => a.id === aideId));
  const user = useAuthStore((s) => s.user);
  const lastDiagnostic = useAideStore(selectLastDiagnostic);
  const lastDiagnosticMonumentId = useAideStore((s) => s.lastDiagnosticMonumentId);
  const monument = useMonumentStore((s) =>
    lastDiagnosticMonumentId ? s.monuments.find((m) => m.id === lastDiagnosticMonumentId) : s.monuments[0]
  );
  useSegmentLabel();

  // If aide not in store (e.g. direct link), fetch from API
  const [fetchedAide, setFetchedAide] = useState<Aide | null>(null);
  useEffect(() => {
    if (!storeAide && aideId) {
      aideService.getById(aideId).then(setFetchedAide).catch(console.error);
    }
  }, [storeAide, aideId]);

  const aide = storeAide ?? fetchedAide;

  const matchResult = useMemo((): AideMatchResult | null => {
    if (!aide || !lastDiagnostic) return null;
    return lastDiagnostic.aidesEligibles.find((m) => m.aide.id === aide.id)
      ?? lastDiagnostic.aidesPotentiellementEligibles.find((m) => m.aide.id === aide.id)
      ?? lastDiagnostic.aidesNonEligibles.find((m) => m.aide.id === aide.id)
      ?? null;
  }, [aide, lastDiagnostic]);

  const [creating, setCreating] = useState(false);

  if (!aide) {
    return (
      <div className="space-y-4">
        <PageHeader title="Aide introuvable" />
        <p className="text-muted-foreground">Cette aide n'existe pas.</p>
        <Button asChild variant="outline">
          <Link to={ROUTES.AIDES}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Retour aux aides
          </Link>
        </Button>
      </div>
    );
  }

  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);

  const handleCreateDossier = async () => {
    if (!monument || !user || creating) return;
    setCreating(true);
    try {
      const dossier = await dossierService.create(
        monument.id,
        aide.id,
        monument.travauxEnvisages ?? []
      );
      navigate(ROUTES.DOSSIER_DETAIL(dossier.id));
    } catch (err) {
      console.error('Erreur création dossier:', err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={ROUTES.AIDES} className="hover:text-foreground transition-colors">
          Aides
        </Link>
        <span>/</span>
        <span className="text-foreground">{aide.nomCourt}</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={categoryConfig?.color ?? ''}>
              {categoryConfig?.label ?? aide.categorie}
            </Badge>
            {matchResult && (() => {
              const hasIncertitudes = matchResult.llmEvaluation?.incertitudes && matchResult.llmEvaluation.incertitudes.length > 0;
              const status = matchResult.eligible && hasIncertitudes ? 'potential' : matchResult.eligible ? 'eligible' : 'non-eligible';
              return (
                <Badge
                  variant="outline"
                  className={
                    status === 'eligible'
                      ? 'border-green-300 text-green-700 bg-green-50'
                      : status === 'potential'
                        ? 'border-amber-300 text-amber-700 bg-amber-50'
                        : 'border-red-200 text-red-600 bg-red-50'
                  }
                >
                  {status === 'eligible' ? (
                    <>
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Éligible
                    </>
                  ) : status === 'potential' ? (
                    <>
                      <HelpCircle className="h-3 w-3 mr-1" />
                      Potentiellement éligible
                    </>
                  ) : (
                    <>
                      <XCircle className="h-3 w-3 mr-1" />
                      Non éligible
                    </>
                  )}
                </Badge>
              );
            })()}
          </div>
          <h1 className="text-2xl font-bold">{decodeHtml(aide.nom)}</h1>
        </div>

        {matchResult?.eligible && monument && (
          <Button onClick={handleCreateDossier} className="shrink-0" disabled={creating}>
            <FileText className="h-4 w-4 mr-2" />
            {creating ? 'Création...' : 'Créer un dossier'}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Description */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-line">
                {decodeHtml(aide.descriptionLongue || aide.description)}
              </p>
            </CardContent>
          </Card>

          {/* Eligibility analysis */}
          {matchResult && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Analyse d'éligibilité
                  {monument && (
                    <span className="text-muted-foreground font-normal ml-1">
                      pour {monument.nom}
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {matchResult.criteresRemplis.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    <span>{c}</span>
                  </div>
                ))}
                {matchResult.criteresNonRemplis.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                    <span className="text-red-700">{c}</span>
                  </div>
                ))}
                {matchResult.llmEvaluation?.incertitudes && matchResult.llmEvaluation.incertitudes.length > 0 && (
                  <>
                    <div className="pt-2 text-sm font-medium text-amber-700">Points à vérifier :</div>
                    {matchResult.llmEvaluation.incertitudes.map((c, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <HelpCircle className="h-4 w-4 text-amber-500 shrink-0" />
                        <span className="text-amber-700">{typeof c === 'string' ? c : c.detail}</span>
                      </div>
                    ))}
                  </>
                )}
                {matchResult.llmEvaluation?.explication && (
                  <p className="pt-2 text-sm text-muted-foreground italic">
                    {matchResult.llmEvaluation.explication}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Démarche */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Démarche à suivre</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                {decodeHtml(aide.demarcheDescription).split('\n').filter(Boolean).map((line, i) => (
                  <div key={i} className="flex gap-2">
                    <ArrowRight className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <span>{line}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Documents requis */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Documents requis</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1.5 text-sm">
                {aide.documentsRequis.map((doc, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    {doc}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Informations clés</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div>
                <p className="text-muted-foreground">Organisme</p>
                <p className="font-medium flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5" />
                  {aide.organisme}
                </p>
              </div>

              {aide.tauxMax && (
                <div>
                  <p className="text-muted-foreground">Taux maximum</p>
                  <p className="font-medium text-lg text-primary">
                    {formatPercentage(aide.tauxMax)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Base {aide.baseTTC ? 'TTC' : 'HT'}
                  </p>
                </div>
              )}

              {aide.montantMax && (
                <div>
                  <p className="text-muted-foreground">Montant maximum</p>
                  <p className="font-medium text-lg text-primary">
                    {formatCurrency(aide.montantMax)}
                  </p>
                </div>
              )}

              <Separator />

              <div>
                <p className="text-muted-foreground">Disponibilité</p>
                <p className="font-medium flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  {aide.permanent ? 'Appel permanent' : `Date limite : ${aide.dateLimite ?? 'NC'}`}
                </p>
              </div>

              <div>
                <p className="text-muted-foreground">Délai d'instruction</p>
                <p className="font-medium">{aide.delaiInstruction}</p>
              </div>

              {aide.urlOfficielle && (
                <>
                  <Separator />
                  <Button asChild variant="outline" size="sm" className="w-full">
                    <a href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                      Site officiel
                    </a>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

        </div>
      </div>

      <Disclaimer />
    </div>
  );
}
