import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { IconAjouter, IconRecherche, IconSupprimer } from '@/components/icons';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { adminService } from '@/services/admin.service';
import { faitEffectif, filtrerFaits, payloadSurcharge } from '@/lib/admin-catalogue';
import { C, SERIF } from '@/lib/brand';
import type { AdminFait, ImpactOptions, OptionSurchargee } from '@/types/admin.types';

interface Props {
  onErreur: (err: unknown, repli: string) => void;
}

const ID_VALIDE = /^[a-z0-9_]+$/;

/** Les faits dont les réponses se modifient ici. Seules les tranches d'un fait
 *  numérique restent fabriquées par le moteur à partir des seuils des aides :
 *  elles n'existent pas dans l'ontologie, et le serveur refuse une liste posée
 *  dessus.
 *
 *  Un `boolean` s'édite, lui, parce que chaque réponse y déclare la VALEUR
 *  qu'elle envoie aux prédicats des aides : c'est ce qui permet d'offrir plus
 *  de deux réponses à une question binaire sans retyper un seul prédicat. */
const A_OPTIONS = new Set(['enum', 'multi_enum', 'boolean']);

/** Les deux réponses qu'un booléen ne peut pas perdre : les réponses déjà
 *  enregistrées par les utilisateurs les citent, et sans elles l'une des deux
 *  valeurs de vérité deviendrait inatteignable. Miroir de
 *  `OPTIONS_BOOLEEN_IMPLICITES` et de la règle R1 du serveur. */
const IDS_BOOLEEN_FIGES = new Set(['oui', 'non']);

/** Les trois entrées du sélecteur de valeur, dans l'ordre d'affichage. */
const VALEURS = [
  { cle: 'oui', valeur: true as boolean | null, label: 'Oui' },
  { cle: 'non', valeur: false as boolean | null, label: 'Non' },
  { cle: 'neutre', valeur: null as boolean | null, label: 'Ne tranche pas' },
];

const cleValeur = (valeur: boolean | null | undefined) =>
  valeur === true ? 'oui' : valeur === false ? 'non' : 'neutre';

type Brouillon = { question: string; help: string; options: OptionSurchargee[] };

function brouillonDe(fait: AdminFait): Brouillon {
  const effectif = faitEffectif(fait);
  return {
    question: effectif.question,
    help: effectif.help ?? '',
    options: effectif.options.map((o) => ({ ...o })),
  };
}

/**
 * Les questions du QCM : leur formulation, leur aide contextuelle et leurs
 * réponses possibles.
 *
 * Le point délicat tient en une phrase : les IDENTIFIANTS des réponses sont
 * cités par les prédicats des aides, les LIBELLÉS ne le sont pas. Renommer est
 * donc sans risque, supprimer ne l'est pas — d'où le bloc d'impact, qui dit
 * avant l'enregistrement quelles aides chaque réponse écarte et quelles aides
 * citent une réponse qu'on s'apprête à retirer.
 */
export function AdminFaitsPanel({ onErreur }: Props) {
  const [faits, setFaits] = useState<AdminFait[]>([]);
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState('');
  const [keyOuverte, setKeyOuverte] = useState<string | null>(null);
  const [brouillon, setBrouillon] = useState<Brouillon | null>(null);
  const [impact, setImpact] = useState<ImpactOptions | null>(null);
  const [simulation, setSimulation] = useState(false);
  const [enregistrement, setEnregistrement] = useState(false);
  const [confirmRetablir, setConfirmRetablir] = useState(false);
  const [deplies, setDeplies] = useState<Set<string>>(new Set());

  useEffect(() => {
    let annule = false;
    adminService
      .listFaits()
      .then((lignes) => {
        if (!annule) setFaits(lignes);
      })
      .catch((err) => onErreur(err, 'Ontologie indisponible'))
      .finally(() => {
        if (!annule) setChargement(false);
      });
    return () => {
      annule = true;
    };
  }, [onErreur]);

  const visibles = useMemo(() => filtrerFaits(faits, recherche), [faits, recherche]);
  const ouvert = faits.find((f) => f.key === keyOuverte) ?? null;
  const editable = ouvert ? A_OPTIONS.has(ouvert.type) : false;

  const ouvrir = (fait: AdminFait) => {
    setKeyOuverte(fait.key);
    setBrouillon(brouillonDe(fait));
    setImpact(fait.impactParOption);
    setDeplies(new Set());
  };

  const remplacer = (fait: AdminFait) => {
    setFaits((lignes) => lignes.map((l) => (l.key === fait.key ? fait : l)));
    setBrouillon(brouillonDe(fait));
    setImpact(fait.impactParOption);
  };

  const simuler = useCallback(async (): Promise<ImpactOptions | null> => {
    if (!ouvert || !brouillon || !editable) return null;
    setSimulation(true);
    try {
      const resultat = await adminService.simulerOptions(ouvert.key, brouillon.options);
      setImpact(resultat);
      return resultat;
    } catch (err) {
      onErreur(err, 'Impact indisponible');
      return null;
    } finally {
      setSimulation(false);
    }
  }, [ouvert, brouillon, editable, onErreur]);

  const idsInvalides = brouillon
    ? brouillon.options.filter((o) => !ID_VALIDE.test(o.id)).map((o) => o.id)
    : [];
  const libellesVides = brouillon ? brouillon.options.some((o) => !o.label.trim()) : false;
  const questionVide = brouillon ? !brouillon.question.trim() : false;
  // R1 du serveur, rejouée ici : un booléen doit garder « oui » et « non » avec
  // leurs valeurs. La garde est dans `enregistrable` pour que le bouton ne
  // propose jamais un geste que le serveur refusera par un 422.
  const booleenCasse =
    !!brouillon &&
    ouvert?.type === 'boolean' &&
    [...IDS_BOOLEEN_FIGES].some((id) => {
      const option = brouillon.options.find((o) => o.id === id);
      return !option || option.valeur !== (id === 'oui');
    });
  const enregistrable =
    !!brouillon &&
    !questionVide &&
    !libellesVides &&
    !booleenCasse &&
    idsInvalides.length === 0 &&
    !enregistrement;

  const enregistrer = async () => {
    if (!ouvert || !brouillon) return;
    // L'impact est rafraîchi avant d'écrire : on ne veut pas enregistrer une
    // suppression de réponse sur la foi d'un impact calculé pour un autre
    // brouillon.
    await simuler();
    setEnregistrement(true);
    try {
      const payload = payloadSurcharge(ouvert, brouillon);
      const fait = payload
        ? await adminService.surchargerFait(ouvert.key, payload)
        : await adminService.retablirFait(ouvert.key);
      remplacer(fait);
      toast.success(payload ? 'Question mise à jour' : 'Question revenue à sa version d’origine');
    } catch (err) {
      onErreur(err, 'Enregistrement impossible');
    } finally {
      setEnregistrement(false);
    }
  };

  const retablir = async () => {
    if (!ouvert) return;
    setConfirmRetablir(false);
    setEnregistrement(true);
    try {
      remplacer(await adminService.retablirFait(ouvert.key));
      toast.success('Question revenue à sa version d’origine');
    } catch (err) {
      onErreur(err, 'Rétablissement impossible');
    } finally {
      setEnregistrement(false);
    }
  };

  const majOption = (index: number, champs: Partial<OptionSurchargee>) =>
    setBrouillon((b) =>
      b ? { ...b, options: b.options.map((o, i) => (i === index ? { ...o, ...champs } : o)) } : b,
    );

  const deplier = (id: string) =>
    setDeplies((actuels) => {
      const suivant = new Set(actuels);
      if (suivant.has(id)) suivant.delete(id);
      else suivant.add(id);
      return suivant;
    });

  const labelOriginal = (id: string) => ouvert?.original.options.find((o) => o.id === id)?.label;

  return (
    <div className="space-y-4">
      <div className="relative sm:max-w-md">
        <IconRecherche
          className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
          strokeWidth={1.8}
        />
        <Input
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          placeholder="Rechercher une question (clé, texte, réponse)…"
          className="h-10 pl-9 text-[16px]"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_480px]">
        <div className="max-h-[70vh] space-y-2 overflow-y-auto rounded-xl border border-border bg-card p-2">
          {chargement ? (
            <p className="px-2 py-8 text-center text-[16px] text-muted-foreground">Chargement…</p>
          ) : visibles.length === 0 ? (
            <p className="px-2 py-8 text-center text-[16px] text-muted-foreground">
              Aucune question ne correspond à votre recherche.
            </p>
          ) : (
            visibles.map((fait) => (
              <button
                key={fait.key}
                type="button"
                onClick={() => ouvrir(fait)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-secondary ${
                  fait.key === keyOuverte ? 'bg-secondary' : ''
                }`}
              >
                <p className="font-mono text-[13.5px] text-muted-foreground">{fait.key}</p>
                <p className="mt-0.5 line-clamp-2 text-[16px] text-foreground">
                  {faitEffectif(fait).question}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {fait.surcharge && <Badge>Surchargée</Badge>}
                  {fait.pending && <Badge variant="outline">En attente</Badge>}
                  <span className="text-[13.5px] text-muted-foreground">
                    {fait.nbAides} aide{fait.nbAides > 1 ? 's' : ''}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>

        <aside className="h-fit space-y-4 rounded-xl border border-border bg-card p-5">
          {!ouvert || !brouillon ? (
            <p className="text-[16px] text-muted-foreground">
              Sélectionnez une question pour reformuler son texte ou ses réponses.
            </p>
          ) : (
            <>
              <div>
                <h2 className="text-[19px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  Reformuler la question
                </h2>
                <p className="font-mono text-[13.5px] text-muted-foreground">{ouvert.key}</p>
              </div>

              {/* Dépendance intrinsèque du fait, en LECTURE SEULE : elle vaut
                  pour toutes les aides à la fois et relève de l'éditorial (le
                  YAML), pas de l'exploitation. L'afficher évite de chercher
                  pourquoi une question ne se pose « jamais ». */}
              {ouvert.pertinentSi && (
                <p
                  className="rounded-lg px-3 py-2 text-[14.5px]"
                  style={{ background: C.paleBlue, color: C.blue }}
                >
                  Posée seulement si{' '}
                  <span className="font-mono">{ouvert.pertinentSi.fact}</span>{' '}
                  <span className="font-mono">
                    {JSON.stringify(ouvert.pertinentSi.predicate)}
                  </span>
                  . Cette dépendance est déclarée sur le fait dans{' '}
                  <span className="font-mono">facts.yaml</span> et ne se modifie pas ici.
                </p>
              )}

              <div className="space-y-1.5">
                <label htmlFor="question-fait" className="text-[15px] font-medium text-foreground">
                  Question posée
                </label>
                <Textarea
                  id="question-fait"
                  value={brouillon.question}
                  onChange={(e) => setBrouillon({ ...brouillon, question: e.target.value })}
                  rows={2}
                  className="text-[16px]"
                />
                {brouillon.question.trim() !== ouvert.original.question && (
                  <p className="text-[13.5px] text-muted-foreground">
                    Original&nbsp;: {ouvert.original.question}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="help-fait" className="text-[15px] font-medium text-foreground">
                  Aide contextuelle
                </label>
                <Textarea
                  id="help-fait"
                  value={brouillon.help}
                  onChange={(e) => setBrouillon({ ...brouillon, help: e.target.value })}
                  rows={2}
                  placeholder="Facultative — affichée sous la question."
                  className="text-[16px]"
                />
              </div>

              {editable ? (
                <div className="space-y-2">
                  <p className="text-[15px] font-medium text-foreground">Réponses possibles</p>
                  {brouillon.options.map((option, index) => {
                    const originale = labelOriginal(option.id);
                    const nouvelle = originale === undefined;
                    const booleen = ouvert.type === 'boolean';
                    const figee = booleen && IDS_BOOLEEN_FIGES.has(option.id);
                    return (
                      <div key={index} className="space-y-1.5 rounded-lg border border-border p-2.5">
                        <div className="flex items-center gap-2">
                          {nouvelle ? (
                            <Input
                              value={option.id}
                              onChange={(e) => majOption(index, { id: e.target.value })}
                              placeholder="identifiant_technique"
                              aria-label="Identifiant de la réponse"
                              className="h-8 w-44 font-mono text-[14px]"
                            />
                          ) : (
                            <Badge variant="outline" className="font-mono text-[13px]">
                              {option.id}
                            </Badge>
                          )}
                          {figee ? (
                            <span className="ml-auto text-[13.5px] text-muted-foreground">
                              Non supprimable&nbsp;: les réponses déjà enregistrées s’appuient
                              dessus.
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() =>
                                setBrouillon({
                                  ...brouillon,
                                  options: brouillon.options.filter((_, i) => i !== index),
                                })
                              }
                              aria-label={`Supprimer la réponse ${option.label || option.id}`}
                              className="ml-auto rounded-md p-1.5 transition-colors hover:bg-destructive-muted"
                            >
                              <IconSupprimer className="h-4 w-4" style={{ color: C.danger }} />
                            </button>
                          )}
                        </div>
                        <Input
                          value={option.label}
                          onChange={(e) => majOption(index, { label: e.target.value })}
                          aria-label="Libellé de la réponse"
                          className="h-9 text-[16px]"
                        />
                        {originale !== undefined && originale !== option.label && (
                          <p className="text-[13.5px] text-muted-foreground">
                            Original&nbsp;: {originale}
                          </p>
                        )}
                        {booleen && (
                          <label className="flex items-center gap-2 text-[14.5px] text-muted-foreground">
                            <span className="shrink-0">Valeur envoyée au moteur</span>
                            <Select
                              value={cleValeur(option.valeur)}
                              disabled={figee}
                              onValueChange={(cle) =>
                                majOption(index, {
                                  valeur: VALEURS.find((v) => v.cle === cle)?.valeur ?? null,
                                  // R4 : une réponse qui tranche n'est pas neutre.
                                  ...(cle === 'neutre' ? {} : { unknown: false }),
                                })
                              }
                            >
                              <SelectTrigger
                                className="h-8 w-44 text-[15px]"
                                aria-label={`Valeur envoyée au moteur pour la réponse ${option.label || option.id}`}
                              >
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {VALEURS.map((v) => (
                                  <SelectItem key={v.cle} value={v.cle}>
                                    {v.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </label>
                        )}
                        <label className="flex items-center gap-2 text-[14.5px] text-muted-foreground">
                          <Checkbox
                            checked={option.unknown}
                            // Une réponse qui envoie une valeur au moteur n'est
                            // pas neutre : la case n'a plus de sens (R4).
                            disabled={booleen && option.valeur !== null && option.valeur !== undefined}
                            onCheckedChange={(v) => majOption(index, { unknown: v === true })}
                          />
                          Réponse neutre (n’écarte aucune aide)
                        </label>
                      </div>
                    );
                  })}

                  <button
                    type="button"
                    onClick={() =>
                      setBrouillon({
                        ...brouillon,
                        options: [
                          ...brouillon.options,
                          // Sur un booléen, une réponse neuve part à « ne
                          // tranche pas » : inoffensive par construction, à
                          // l'administrateur de décider ce qu'elle vaut.
                          { id: '', label: '', unknown: false, valeur: null },
                        ],
                      })
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[15px] font-medium transition-colors hover:bg-secondary"
                    style={{ color: C.blue }}
                  >
                    <IconAjouter className="h-3.5 w-3.5" />
                    Ajouter une réponse
                  </button>

                  {idsInvalides.length > 0 && (
                    <p className="text-[14.5px]" style={{ color: C.danger }}>
                      Un identifiant ne contient que des minuscules, des chiffres et des tirets bas.
                    </p>
                  )}
                </div>
              ) : (
                <p className="rounded-lg bg-secondary px-3 py-2.5 text-[14.5px] text-muted-foreground">
                  Les tranches d’un fait <span className="font-mono">{ouvert.type}</span> sont
                  calculées par le moteur à partir des seuils des aides&nbsp;: seuls la question et
                  son aide contextuelle se modifient ici.
                </p>
              )}

              {editable && (
                <div className="space-y-2 rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[15px] font-medium text-foreground">Impact sur les aides</p>
                    <button
                      type="button"
                      onClick={simuler}
                      disabled={simulation}
                      className="text-[14.5px] font-medium underline disabled:opacity-50"
                      style={{ color: C.blue }}
                    >
                      {simulation ? 'Calcul…' : 'Vérifier l’impact'}
                    </button>
                  </div>

                  {impact?.parOption.map((ligne) => (
                    <div key={ligne.id} className="text-[14.5px]">
                      <button
                        type="button"
                        onClick={() => deplier(ligne.id)}
                        className="w-full text-left text-muted-foreground hover:text-foreground"
                      >
                        <span className="font-mono text-[13px]">{ligne.id}</span>{' '}
                        {ligne.unknown
                          ? '— réponse neutre, n’écarte aucune aide'
                          : ouvert.type === 'boolean' && (ligne.valeur ?? null) === null
                            ? '— ne tranche pas, n’écarte aucune aide'
                            : `— écarte ${ligne.ecarte.length} aide${ligne.ecarte.length > 1 ? 's' : ''}`}
                      </button>
                      {deplies.has(ligne.id) && ligne.ecarte.length > 0 && (
                        <ul className="ml-3 mt-1 list-disc space-y-0.5 pl-3 text-muted-foreground">
                          {ligne.ecarte.map((aide) => (
                            <li key={aide.slug}>{aide.nom}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}

                  {impact?.supprimees.map((ligne) => (
                    <div
                      key={ligne.id}
                      className="rounded-md px-2 py-1.5 text-[14.5px]"
                      style={{ background: C.paleOrange, color: C.ink }}
                    >
                      <button type="button" onClick={() => deplier(ligne.id)} className="text-left">
                        <span className="font-mono text-[13px]">{ligne.id}</span> supprimée —
                        référencée par {ligne.referenceePar.length} aide
                        {ligne.referenceePar.length > 1 ? 's' : ''}
                        {ligne.referenceePar.length > 0 &&
                          ' : ces aides ne pourront plus être ouvertes par cette question.'}
                      </button>
                      {deplies.has(ligne.id) && ligne.referenceePar.length > 0 && (
                        <ul className="ml-3 mt-1 list-disc space-y-0.5 pl-3">
                          {ligne.referenceePar.map((aide) => (
                            <li key={aide.slug}>{aide.nom}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={enregistrer}
                  disabled={!enregistrable}
                  className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{ background: C.blue }}
                >
                  {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
                </button>
                {ouvert.surcharge && (
                  <button
                    type="button"
                    onClick={() => setConfirmRetablir(true)}
                    className="text-[15px] font-medium underline"
                    style={{ color: C.grayFg }}
                  >
                    Rétablir l’original
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
            <AlertDialogTitle>Rétablir la question d’origine&nbsp;?</AlertDialogTitle>
            <AlertDialogDescription>
              La reformulation est supprimée et la question revient au texte de{' '}
              <span className="font-mono">facts.yaml</span>. Les réponses déjà enregistrées par les
              utilisateurs ne changent pas.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={retablir}>Rétablir</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
