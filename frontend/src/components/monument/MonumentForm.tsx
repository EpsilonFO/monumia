import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Card, CardContent } from '@/components/ui/card';
import { CommuneAutocomplete } from '@/components/monument/CommuneAutocomplete';
import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';
import { ChevronDown, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { PROTECTION_LEVELS, ETATS_CONSERVATION } from '@/constants/monument-options';
import {
  GROUPES_TYPE_EDIFICE,
  affectationApplicable,
  architectureRomaneApplicable,
  avecTypesEdifice,
  basculerChoix,
  groupesProprietaire,
  proprietairesCoches,
  typesCoches,
  type GroupeChoix,
} from '@/lib/fiche-monument';
import type { Monument } from '@/types';

interface MonumentFormProps {
  initialData?: Partial<Monument>;
  onSubmit: (data: Partial<Monument>) => void;
  isEditing?: boolean;
  saving?: boolean;
}

// Des clés, traduites au rendu : la table est évaluée à l'import.
const CREATION_STEPS = [
  { number: 1, cle: 'identification' },
  { number: 2, cle: 'statutJuridique' },
  { number: 3, cle: 'descriptionPhysique' },
] as const;

/** Dans l'ordre des étapes : `STEP_COMPONENTS[i]` sert l'étape `i + 1`. */
const STEP_COMPONENTS = [Step1Identification, Step2StatutJuridique, Step3DescriptionPhysique];

function isStepValid(step: number, data: Partial<Monument>): boolean {
  switch (step) {
    case 1:
      return !!(data.nom?.trim() && data.commune?.trim());
    case 2:
      return !!data.protection && proprietairesCoches(data).length > 0;
    case 3:
      // Dernière étape avant « Terminer » : c'est la seule garantie que l'état
      // sanitaire soit renseigné, faute de quoi les gates des dispositifs
      // d'urgence ({in: [mauvais, peril]}) ne discrimineraient jamais rien.
      return !!data.etatConservation;
    default:
      return true;
  }
}

/**
 * Les travaux envisagés ne sont pas dans ce formulaire : ils cadrent un PROJET,
 * se saisissent dans son wizard et se modifient sur sa page.
 */
export function MonumentForm({ initialData, onSubmit, isEditing, saving }: MonumentFormProps) {
  const { t } = useTranslation(['monuments', 'common']);
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<Partial<Monument>>(initialData ?? {});

  const update = (updates: Partial<Monument>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  };

  const canProceed = isStepValid(currentStep, formData);
  const lastStep = CREATION_STEPS.length;

  const handleNext = () => {
    if (!canProceed) return;
    if (currentStep < lastStep) setCurrentStep(currentStep + 1);
    else onSubmit(formData);
  };

  const handlePrev = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  const progressPercent = ((currentStep - 1) / (lastStep - 1)) * 100;
  const currentStepInfo = CREATION_STEPS[currentStep - 1];

  return (
    <div className="space-y-6">
      {/* Step Indicator */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            {t(`MonumentForm.etapes.${currentStepInfo.cle}.titre`)}
          </span>
          <span className="text-muted-foreground">
            {t('MonumentForm.etape', { courante: currentStep, total: lastStep })}
          </span>
        </div>
        <Progress value={progressPercent} className="h-1.5" />
        <p className="text-xs text-muted-foreground">
          {t(`MonumentForm.etapes.${currentStepInfo.cle}.description`)}
        </p>
      </div>

      {/* Carré blanc + navigation en colonne à sa droite. En mobile, la colonne
          repasse sous le carré. */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <Card className="min-w-0 flex-1">
          <CardContent>
            {/* Les trois étapes occupent la MÊME cellule de grille : le carré
                prend une bonne fois la hauteur de la plus grande (l'étape 3) et
                ne bouge plus d'une étape à l'autre — donc les boutons non plus.
                Une hauteur en dur se serait décalée au premier champ ajouté.
                Les étapes inactives sont `invisible` (donc hors du parcours de
                tabulation) et `inert` (hors de l'arbre d'accessibilité).
                Sauf sur téléphone, où elles sortent tout à fait : les boutons y
                passent sous le carré de toute façon, et l'étape 1 (deux champs)
                laissait 500 px de blanc au-dessus d'eux. */}
            <div className="grid">
              {STEP_COMPONENTS.map((Step, i) => {
                const actif = currentStep === i + 1;
                return (
                  <div
                    key={i}
                    className={cn(
                      'col-start-1 row-start-1 min-w-0',
                      !actif && 'invisible pointer-events-none max-sm:hidden'
                    )}
                    inert={!actif}
                  >
                    <Step data={formData} onChange={update} />
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <div className="flex shrink-0 items-center justify-end gap-3 sm:w-44 sm:flex-col sm:items-stretch">
          <Button
            variant="outline"
            size="lg"
            onClick={handlePrev}
            disabled={currentStep === 1}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            {t('common:actions.precedent')}
          </Button>
          <Button
            onClick={handleNext}
            disabled={!canProceed || (saving && currentStep === lastStep)}
            className="h-12 px-8 text-base"
          >
            {saving && currentStep === lastStep
              ? <Loader2 className="h-5 w-5 animate-spin" />
              : currentStep === lastStep
                ? isEditing ? t('common:actions.enregistrer') : t('MonumentForm.terminer')
                : <>{t('common:actions.suivant')} <ChevronRight className="h-5 w-5 ml-1.5" /></>}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- Step Components ---

interface StepProps {
  data: Partial<Monument>;
  onChange: (updates: Partial<Monument>) => void;
}

/**
 * Un champ = son intitulé, un peu d'air, puis la saisie. Sans cet interligne,
 * l'intitulé collait au placeholder et les deux se lisaient comme un seul bloc.
 */
const FIELD = 'space-y-1.5';

/**
 * `w-fit` (défaut shadcn) laisse le déclencheur grandir avec le libellé choisi :
 * « Site Patrimonial Remarquable (SPR) » débordait alors sur le champ voisin.
 * On fixe la largeur à la cellule dès le placeholder, et on tronque au-delà (…).
 */
const SELECT_TRIGGER =
  'w-full min-w-0 [&>span[data-slot=select-value]]:block [&>span[data-slot=select-value]]:truncate';

function Step1Identification({ data, onChange }: StepProps) {
  const { t } = useTranslation(['monuments', 'common']);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="nom">{t('MonumentForm.nom')}</Label>
        <Input
          id="nom"
          value={data.nom ?? ''}
          onChange={(e) => onChange({ nom: e.target.value })}
          placeholder={t('MonumentForm.nomPlaceholder')}
        />
      </div>
      {/* Pleine largeur comme le nom : « Saint-Caradec-Trégomel » ou
          « Colleville-Montgomery » doivent tenir en entier dans le champ, et
          les suggestions (qui en épousent la largeur) rester lisibles. */}
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="commune">{t('MonumentForm.commune')}</Label>
        {/* Choisir dans la liste fournit le code INSEE, dont le backend déduit
            département, région et population : c'est ce qui rend les aides
            territoriales évaluables. La saisie libre reste acceptée. */}
        <CommuneAutocomplete
          id="commune"
          value={data.commune ?? ''}
          onChange={(nom) => onChange({ commune: nom, codeInsee: '' })}
          onSelect={(commune) =>
            onChange({ commune: commune.nom, codeInsee: commune.codeInsee })
          }
        />
      </div>
    </div>
  );
}

function Step2StatutJuridique({ data, onChange }: StepProps) {
  const { t } = useTranslation(['monuments', 'common']);
  // Un bien non protégé n'a ni date ni détail de protection : les deux champs
  // sont grisés, et vidés au passage pour qu'aucune valeur saisie avant ne
  // survive en douce dans la fiche.
  const sansProtection = data.protection === 'non_protege';

  const setProtection = (protection: Monument['protection']) => {
    onChange(
      protection === 'non_protege'
        ? { protection, dateProtection: '', typeProtection: '' }
        : { protection },
    );
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={FIELD}>
        <Label htmlFor="protection">{t('MonumentForm.protection')}</Label>
        <Select value={data.protection ?? ''} onValueChange={setProtection}>
          <SelectTrigger id="protection" className={SELECT_TRIGGER}>
            <SelectValue placeholder={t('MonumentForm.selectionner')} />
          </SelectTrigger>
          <SelectContent>
            {PROTECTION_LEVELS.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className={FIELD}>
        {/* Champ désactivé : l'intitulé s'estompe avec lui, sinon seul le cadre
            grisé le signale et l'œil ne le voit pas. */}
        <Label htmlFor="dateProtection" className={cn(sansProtection && 'opacity-60')}>
          {t('MonumentForm.dateProtection')}
        </Label>
        <Input
          id="dateProtection"
          type="date"
          value={data.dateProtection ?? ''}
          onChange={(e) => onChange({ dateProtection: e.target.value })}
          disabled={sansProtection}
        />
      </div>
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="typeProtection" className={cn(sansProtection && 'opacity-60')}>
          {t('MonumentForm.detailProtection')}
        </Label>
        <Input
          id="typeProtection"
          value={data.typeProtection ?? ''}
          onChange={(e) => onChange({ typeProtection: e.target.value })}
          placeholder={
            sansProtection
              ? t('MonumentForm.detailSansObjet')
              : t('MonumentForm.detailPlaceholder')
          }
          disabled={sansProtection}
        />
      </div>
      <div className={FIELD}>
        <Label htmlFor="proprietaire">{t('MonumentForm.proprietaire')}</Label>
        <ChoixMultiple
          id="proprietaire"
          groupes={groupesProprietaire(data)}
          valeurs={proprietairesCoches(data)}
          vide={t('MonumentForm.selectionner')}
          onChange={(v) =>
            onChange({
              proprietaire: proprietairesCoches({ proprietaire: v as Monument['proprietaire'] }),
            })
          }
        />
        <p className="text-xs text-muted-foreground">
          {t('MonumentForm.proprietaireAide')}
        </p>
      </div>
    </div>
  );
}

/**
 * Radix n'admet pas d'item à valeur vide : « Non renseigné » a sa sentinelle,
 * traduite en `null` pour que l'enregistrement EFFACE la valeur en base.
 */
const NON_RENSEIGNE = '__non_renseigne';

function lireOuiNon(v: boolean | null | undefined): string {
  return v === true ? 'oui' : v === false ? 'non' : NON_RENSEIGNE;
}

function ecrireOuiNon(v: string): boolean | null {
  return v === 'oui' ? true : v === 'non' ? false : null;
}

/**
 * Choix multiple de l'édition (types d'édifice, propriétaires) : une liste à
 * cocher, rangée par famille, dans un menu déroulant. Le formulaire de
 * création en a l'équivalent avec `MenuChoix` ; celui-ci garde la charte
 * shadcn de l'édition.
 */
function ChoixMultiple({
  id,
  groupes,
  valeurs,
  vide,
  onChange,
}: {
  id: string;
  groupes: readonly GroupeChoix[];
  valeurs: readonly string[];
  /** Texte du bouton quand rien n'est coché. */
  vide: string;
  onChange: (valeurs: string[]) => void;
}) {
  const libelles = groupes
    .flatMap((g) => g.options)
    .filter((o) => valeurs.includes(o.value))
    .map((o) => o.label);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          className="w-full min-w-0 justify-between font-normal"
        >
          <span className={cn('truncate', libelles.length === 0 && 'text-muted-foreground')}>
            {libelles.length > 0 ? libelles.join(', ') : vide}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="max-h-80 w-(--radix-popover-trigger-width) overflow-y-auto p-1.5"
      >
        {groupes.map((g) => (
          <div key={g.titre} className="py-1">
            <p className="px-2 py-1 text-xs font-medium text-muted-foreground">{g.titre}</p>
            {g.options.map((o) => {
              const idOption = `${id}-${o.value}`;
              return (
                <label
                  key={o.value}
                  htmlFor={idOption}
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                >
                  <Checkbox
                    id={idOption}
                    checked={valeurs.includes(o.value)}
                    onCheckedChange={() => onChange(basculerChoix(valeurs, o.value))}
                  />
                  {o.label}
                </label>
              );
            })}
          </div>
        ))}
      </PopoverContent>
    </Popover>
  );
}

function Step3DescriptionPhysique({ data, onChange }: StepProps) {
  const { t } = useTranslation(['monuments', 'common']);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="typeEdifice">{t('MonumentForm.typeEdifice')}</Label>
        <ChoixMultiple
          id="typeEdifice"
          groupes={GROUPES_TYPE_EDIFICE}
          valeurs={typesCoches(data)}
          vide={t('MonumentForm.nonRenseigne')}
          onChange={(v) => onChange(avecTypesEdifice(data, v))}
        />
        <p className="text-xs text-muted-foreground">
          {t('MonumentForm.typeEdificeAide')}
        </p>
      </div>
      {affectationApplicable(data) && (
        <div className={FIELD}>
          <Label htmlFor="affecteAuCulte">{t('MonumentForm.affectationCulte')}</Label>
          <Select
            value={lireOuiNon(data.affecteAuCulte)}
            onValueChange={(v) => onChange({ affecteAuCulte: ecrireOuiNon(v) })}
          >
            <SelectTrigger id="affecteAuCulte" className={SELECT_TRIGGER}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NON_RENSEIGNE}>{t('MonumentForm.nonRenseigne')}</SelectItem>
              <SelectItem value="oui">{t('MonumentForm.toujoursAffecte')}</SelectItem>
              <SelectItem value="non">{t('MonumentForm.desaffecte')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      {architectureRomaneApplicable(data) && (
        <div className={FIELD}>
          <Label htmlFor="architectureRomane">{t('MonumentForm.architectureRomane')}</Label>
          <Select
            value={lireOuiNon(data.architectureRomane)}
            onValueChange={(v) => onChange({ architectureRomane: ecrireOuiNon(v) })}
          >
            <SelectTrigger id="architectureRomane" className={SELECT_TRIGGER}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NON_RENSEIGNE}>{t('MonumentForm.nonRenseigne')}</SelectItem>
              <SelectItem value="oui">{t('MonumentForm.romaneOui')}</SelectItem>
              <SelectItem value="non">{t('common:reponses.non')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      <div className={FIELD}>
        <Label htmlFor="siecleConstruction">{t('MonumentForm.siecleConstruction')}</Label>
        <Input
          id="siecleConstruction"
          value={data.siecleConstruction ?? ''}
          onChange={(e) => onChange({ siecleConstruction: e.target.value })}
          placeholder={t('MonumentForm.sieclePlaceholder')}
        />
      </div>
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="descriptionGenerale">{t('MonumentForm.descriptionGenerale')}</Label>
        <Textarea
          id="descriptionGenerale"
          value={data.descriptionGenerale ?? ''}
          onChange={(e) => onChange({ descriptionGenerale: e.target.value })}
          placeholder={t('MonumentForm.descriptionPlaceholder')}
          rows={4}
        />
      </div>
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="etatConservation">{t('MonumentForm.etatConservation')}</Label>
        <Select
          value={data.etatConservation ?? ''}
          onValueChange={(v) => onChange({ etatConservation: v as Monument['etatConservation'] })}
        >
          <SelectTrigger id="etatConservation" className={SELECT_TRIGGER}>
            <SelectValue placeholder={t('MonumentForm.selectionner')} />
          </SelectTrigger>
          <SelectContent>
            {ETATS_CONSERVATION.map((e) => (
              <SelectItem key={e.value} value={e.value}>
                {e.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {t('MonumentForm.etatAide')}
        </p>
      </div>
    </div>
  );
}
