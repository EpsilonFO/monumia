import { useCallback, useEffect, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { IconRecherche } from '@/components/icons';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { adminService } from '@/services/admin.service';
import {
  LIBELLE_ETAT,
  filtrerConditions,
  inventaireSurcharges,
  operateursPour,
  phraseLisible,
  predicatUtile,
} from '@/lib/admin-predicats';
import { C, SERIF } from '@/lib/brand';
import type {
  AdminCondition,
  ConditionOrpheline,
  InventaireConditions,
  OperateurPredicat,
} from '@/types/admin.types';

interface Props {
  onErreur: (err: unknown, repli: string) => void;
}

type Brouillon = { operateur: OperateurPredicat; valeurs: string[]; motif: string };

const cle = (slug: string, conditionId: string) => `${slug}/${conditionId}`;

function brouillonDe(condition: AdminCondition): Brouillon {
  return {
    operateur: (condition.operateur || 'eq') as OperateurPredicat,
    valeurs: [...condition.valeurs],
    motif: condition.surcharge?.motif ?? '',
  };
}

/**
 * Les PRÉDICATS des conditions : ce qu'une réponse doit valoir pour qu'une aide
 * reste éligible.
 *
 * Le mandat est étroit, et c'est ce qui rend l'écran sûr : seuls les gates
 * portant sur une question à choix apparaissent, et l'éditeur est un menu plus
 * des cases à cocher — jamais du JSON. Le TEXTE de la condition est en lecture
 * seule : il vient de la source, on ne le reformule pas.
 *
 * Le YAML reste la vérité éditoriale. Une correction durable se reporte dans
 * `data/aides/<slug>.yaml`, puis la ligne se rétablit ici — sinon elle fige la
 * version d'avant.
 */
export function AdminConditionsPanel({ onErreur }: Props) {
  const { t } = useTranslation(['admin', 'common']);
  const [inventaire, setInventaire] = useState<InventaireConditions>({
    conditions: [],
    orphelines: [],
  });
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState('');
  const [cleOuverte, setCleOuverte] = useState<string | null>(null);
  const [brouillon, setBrouillon] = useState<Brouillon | null>(null);
  const [impact, setImpact] = useState<Awaited<
    ReturnType<typeof adminService.simulerPredicat>
  > | null>(null);
  const [simulation, setSimulation] = useState(false);
  const [enregistrement, setEnregistrement] = useState(false);
  const [confirmRetablir, setConfirmRetablir] = useState(false);

  useEffect(() => {
    let vivant = true;
    adminService
      .listConditions()
      .then((data) => vivant && setInventaire(data))
      .catch((err) => vivant && onErreur(err, t('AdminConditionsPanel.conditionsIndisponibles')))
      .finally(() => vivant && setChargement(false));
    return () => {
      vivant = false;
    };
  }, [onErreur, t]);

  const visibles = useMemo(
    () => filtrerConditions(inventaire.conditions, recherche),
    [inventaire.conditions, recherche],
  );
  const surchargees = useMemo(
    () => inventaireSurcharges(inventaire.conditions, inventaire.orphelines),
    [inventaire],
  );

  const ouvert = useMemo(
    () => inventaire.conditions.find((c) => cle(c.aideSlug, c.conditionId) === cleOuverte) ?? null,
    [inventaire.conditions, cleOuverte],
  );

  const ouvrir = (condition: AdminCondition) => {
    setCleOuverte(cle(condition.aideSlug, condition.conditionId));
    setBrouillon(brouillonDe(condition));
    setImpact(null);
  };

  /** Remplace la ligne modifiée sans relister tout le catalogue. */
  const rafraichir = useCallback(async () => {
    try {
      setInventaire(await adminService.listConditions());
    } catch (err) {
      onErreur(err, t('AdminConditionsPanel.conditionsIndisponibles'));
    }
  }, [onErreur, t]);

  const simuler = useCallback(async (): Promise<void> => {
    if (!ouvert || !brouillon || brouillon.valeurs.length === 0) return;
    setSimulation(true);
    try {
      setImpact(
        await adminService.simulerPredicat(
          ouvert.aideSlug,
          ouvert.conditionId,
          brouillon.operateur,
          brouillon.valeurs,
        ),
      );
    } catch (err) {
      onErreur(err, t('AdminPanneaux.impactIndisponible'));
    } finally {
      setSimulation(false);
    }
  }, [ouvert, brouillon, onErreur, t]);

  const utile = ouvert && brouillon ? predicatUtile(ouvert, brouillon) : null;
  const enregistrable = !!brouillon && brouillon.valeurs.length > 0 && !enregistrement;

  const enregistrer = async () => {
    if (!ouvert || !brouillon) return;
    // L'impact est rafraîchi avant d'écrire : on ne veut pas enregistrer sur la
    // foi d'un impact calculé pour un autre brouillon.
    await simuler();
    setEnregistrement(true);
    try {
      if (utile) {
        await adminService.surchargerPredicat(
          ouvert.aideSlug,
          ouvert.conditionId,
          utile.operateur,
          utile.valeurs,
          brouillon.motif,
        );
        toast.success(t('AdminConditionsPanel.toastMiseAJour'));
      } else {
        await adminService.retablirPredicat(ouvert.aideSlug, ouvert.conditionId);
        toast.success(t('AdminConditionsPanel.toastRetablie'));
      }
      await rafraichir();
    } catch (err) {
      onErreur(err, t('AdminPanneaux.enregistrementImpossible'));
    } finally {
      setEnregistrement(false);
    }
  };

  const retablir = async (slug: string, conditionId: string) => {
    setConfirmRetablir(false);
    setEnregistrement(true);
    try {
      await adminService.retablirPredicat(slug, conditionId);
      await rafraichir();
      toast.success(t('AdminConditionsPanel.toastRetablie'));
    } catch (err) {
      onErreur(err, t('AdminPanneaux.retablissementImpossible'));
    } finally {
      setEnregistrement(false);
    }
  };

  const cocher = (id: string, coche: boolean) =>
    setBrouillon((b) =>
      b
        ? { ...b, valeurs: coche ? [...b.valeurs, id] : b.valeurs.filter((v) => v !== id) }
        : b,
    );

  return (
    <div className="space-y-4">
      {surchargees.length > 0 && (
        <div className="space-y-1.5 rounded-xl border border-border bg-card p-3">
          <p className="text-[15px] font-medium text-foreground">
            {t('AdminConditionsPanel.surchargesEnPlace', { nb: surchargees.length })}
          </p>
          {surchargees.map((ligne: AdminCondition | ConditionOrpheline) => {
            const etat = ligne.surcharge?.etat ?? 'active';
            const alerte = etat !== 'active';
            return (
              <div
                key={cle(ligne.aideSlug, ligne.conditionId)}
                className="flex flex-wrap items-center gap-2 rounded-md px-2 py-1.5 text-[14.5px]"
                style={alerte ? { background: C.paleOrange, color: C.ink } : undefined}
              >
                <span className="font-mono text-[13px]">
                  {ligne.aideSlug}/{ligne.conditionId}
                </span>
                <span>{LIBELLE_ETAT[etat]}</span>
                {'text' in ligne ? (
                  <button
                    type="button"
                    onClick={() => ouvrir(ligne)}
                    className="ml-auto font-medium underline"
                    style={{ color: C.blue }}
                  >
                    {t('AdminConditionsPanel.ouvrir')}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => retablir(ligne.aideSlug, ligne.conditionId)}
                    className="ml-auto font-medium underline"
                    style={{ color: C.grayFg }}
                  >
                    {t('AdminConditionsPanel.supprimerLigne')}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="relative sm:max-w-md">
        <IconRecherche
          className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
          strokeWidth={1.8}
        />
        <Input
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          placeholder={t('AdminConditionsPanel.recherche')}
          className="h-10 pl-9 text-[16px]"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_480px]">
        <div className="max-h-[70vh] space-y-2 overflow-y-auto rounded-xl border border-border bg-card p-2">
          {chargement ? (
            <p className="px-2 py-8 text-center text-[16px] text-muted-foreground">{t('common:etats.chargement')}</p>
          ) : visibles.length === 0 ? (
            <p className="px-2 py-8 text-center text-[16px] text-muted-foreground">
              {t('AdminConditionsPanel.aucunResultat')}
            </p>
          ) : (
            visibles.map((condition) => (
              <button
                key={cle(condition.aideSlug, condition.conditionId)}
                type="button"
                onClick={() => ouvrir(condition)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-secondary ${
                  cle(condition.aideSlug, condition.conditionId) === cleOuverte ? 'bg-secondary' : ''
                }`}
              >
                <p className="font-mono text-[13.5px] text-muted-foreground">
                  {condition.aideSlug}/{condition.conditionId}
                </p>
                <p className="mt-0.5 line-clamp-2 text-[16px] text-foreground">{condition.text}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {condition.surcharge && (
                    <Badge>{LIBELLE_ETAT[condition.surcharge.etat]}</Badge>
                  )}
                  {!condition.engineReady && (
                    <Badge variant="outline">{t('AdminPanneaux.nonTypee')}</Badge>
                  )}
                  {condition.retiree && (
                    <Badge variant="outline">{t('AdminConditionsPanel.aideRetiree')}</Badge>
                  )}
                  <span className="text-[13.5px] text-muted-foreground">
                    {phraseLisible(
                      condition.question,
                      condition.operateur,
                      condition.valeurs,
                      condition.reponses,
                      condition.choixMultiple,
                    )}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>

        <aside className="space-y-3 rounded-xl border border-border bg-card p-4">
          {!ouvert || !brouillon ? (
            <p className="py-8 text-center text-[16px] text-muted-foreground">
              {t('AdminConditionsPanel.selectionner')}
            </p>
          ) : (
            <>
              <div>
                <p className="text-[18px] font-semibold" style={{ fontFamily: SERIF }}>
                  {ouvert.aideNom}
                </p>
                <p className="font-mono text-[13.5px] text-muted-foreground">
                  {ouvert.aideSlug}/{ouvert.conditionId}
                </p>
              </div>

              {/* Le texte vient de la SOURCE : il se corrige dans le YAML, pas ici. */}
              <div className="rounded-lg bg-secondary px-3 py-2.5">
                <p className="text-[13.5px] font-medium text-muted-foreground">
                  {t('AdminConditionsPanel.texteLectureSeule')}
                </p>
                <p className="mt-1 text-[15px] text-foreground">{ouvert.text}</p>
              </div>

              {ouvert.surcharge && ouvert.surcharge.etat !== 'active' && (
                <div
                  className="space-y-1 rounded-lg px-3 py-2.5 text-[14.5px]"
                  style={{ background: C.paleOrange, color: C.ink }}
                >
                  <p className="font-medium">{LIBELLE_ETAT[ouvert.surcharge.etat]}</p>
                  {ouvert.surcharge.detail && <p>{ouvert.surcharge.detail}</p>}
                  {ouvert.surcharge.conditionTextActuel !== null &&
                    ouvert.surcharge.conditionTextActuel !== ouvert.surcharge.conditionText && (
                      <p className="mt-1">
                        <Trans
                          t={t}
                          i18nKey="AdminConditionsPanel.texteAuMomentDecision"
                          values={{ texte: ouvert.surcharge.conditionText }}
                          components={{ gras: <span className="font-medium" /> }}
                        />
                      </p>
                    )}
                </div>
              )}

              <div className="space-y-2">
                <p className="text-[15px] font-medium text-foreground">
                  {ouvert.question ?? ouvert.factKey}
                </p>
                <Select
                  value={brouillon.operateur}
                  onValueChange={(v) =>
                    setBrouillon({ ...brouillon, operateur: v as OperateurPredicat })
                  }
                >
                  <SelectTrigger className="h-9 w-52 text-[15px]" aria-label={t('AdminConditionsPanel.operateurAria')}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {operateursPour(ouvert.choixMultiple).map((o) => (
                      <SelectItem key={o.valeur} value={o.valeur}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {ouvert.reponses.map((reponse) => (
                  <label
                    key={reponse.id}
                    className="flex items-center gap-2 text-[15px] text-foreground"
                  >
                    <Checkbox
                      checked={brouillon.valeurs.includes(reponse.id)}
                      onCheckedChange={(v) => cocher(reponse.id, v === true)}
                    />
                    {reponse.label}
                    <span className="font-mono text-[13px] text-muted-foreground">
                      {reponse.id}
                    </span>
                  </label>
                ))}

                <p className="text-[14.5px] text-muted-foreground">
                  {phraseLisible(
                    ouvert.question,
                    brouillon.operateur,
                    brouillon.valeurs,
                    ouvert.reponses,
                    ouvert.choixMultiple,
                  )}
                </p>
                {brouillon.valeurs.length === 0 && (
                  <p className="text-[14.5px]" style={{ color: C.danger }}>
                    {t('AdminConditionsPanel.cochezUneReponse')}
                  </p>
                )}
              </div>

              <div className="space-y-2 rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[15px] font-medium text-foreground">
                    {t('AdminConditionsPanel.impactSurAide')}
                  </p>
                  <button
                    type="button"
                    onClick={simuler}
                    disabled={simulation || brouillon.valeurs.length === 0}
                    className="text-[14.5px] font-medium underline disabled:opacity-50"
                    style={{ color: C.blue }}
                  >
                    {simulation ? t('AdminPanneaux.calcul') : t('AdminPanneaux.verifierImpact')}
                  </button>
                </div>

                {impact?.parReponse.map((ligne) => (
                  <p
                    key={ligne.id}
                    className={`text-[14.5px] ${ligne.changement ? 'text-foreground' : 'text-muted-foreground'}`}
                  >
                    <Trans
                      t={t}
                      i18nKey={
                        ligne.changement
                          ? ligne.apresEcarte
                            ? 'AdminConditionsPanel.impact.ecarteraDesormais'
                            : 'AdminConditionsPanel.impact.necarteraPlus'
                          : ligne.apresEcarte
                            ? 'AdminConditionsPanel.impact.ecarteInchange'
                            : 'AdminConditionsPanel.impact.necartePasInchange'
                      }
                      values={{ id: ligne.id }}
                      components={{ code: <span className="font-mono text-[13px]" /> }}
                    />
                  </p>
                ))}

                {impact?.avertissements.map((texte) => (
                  <p
                    key={texte}
                    className="rounded-md px-2 py-1.5 text-[14.5px]"
                    style={{ background: C.paleOrange, color: C.ink }}
                  >
                    {texte}
                  </p>
                ))}

                {impact && (
                  <p className="text-[13.5px] text-muted-foreground">
                    {t('AdminConditionsPanel.verdictCritere')}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="motif-condition"
                  className="text-[15px] font-medium text-foreground"
                >
                  {t('AdminPanneaux.motif')}
                </label>
                <Textarea
                  id="motif-condition"
                  value={brouillon.motif}
                  onChange={(e) => setBrouillon({ ...brouillon, motif: e.target.value })}
                  rows={2}
                  placeholder={t('AdminConditionsPanel.motifPlaceholder')}
                  className="text-[16px]"
                />
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={enregistrer}
                  disabled={!enregistrable}
                  className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{ background: C.blue }}
                >
                  {enregistrement ? t('common:etats.enregistrement') : t('common:actions.enregistrer')}
                </button>
                {ouvert.surcharge && (
                  <button
                    type="button"
                    onClick={() => setConfirmRetablir(true)}
                    className="text-[15px] font-medium underline"
                    style={{ color: C.grayFg }}
                  >
                    {t('AdminPanneaux.retablir')}
                  </button>
                )}
              </div>
            </>
          )}
        </aside>
      </div>

      <AlertDialog open={confirmRetablir} onOpenChange={setConfirmRetablir}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('AdminConditionsPanel.confirmation.titre')}</AlertDialogTitle>
            <AlertDialogDescription>
              <Trans
                t={t}
                i18nKey="AdminConditionsPanel.confirmation.description"
                values={{ fichier: `data/aides/${ouvert?.aideSlug ?? ''}.yaml` }}
                components={{ code: <span className="font-mono" /> }}
              />
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common:actions.annuler')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => ouvert && retablir(ouvert.aideSlug, ouvert.conditionId)}
            >
              {t('AdminPanneaux.retablir')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
