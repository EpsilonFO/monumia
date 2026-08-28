import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { CommuneAutocomplete } from '@/components/monument/CommuneAutocomplete';
import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import {
  PROTECTION_LEVELS,
  OWNERSHIP_TYPES,
  ETATS_CONSERVATION,
} from '@/constants/monument-options';
import type { Monument } from '@/types';

interface MonumentFormProps {
  initialData?: Partial<Monument>;
  onSubmit: (data: Partial<Monument>) => void;
  isEditing?: boolean;
  saving?: boolean;
}

const CREATION_STEPS = [
  { number: 1, title: 'Identification', description: 'Nom et localisation' },
  { number: 2, title: 'Statut juridique', description: 'Protection et propriété' },
  { number: 3, title: 'Description physique', description: 'Architecture et état du monument' },
];

/** Dans l'ordre des étapes : `STEP_COMPONENTS[i]` sert l'étape `i + 1`. */
const STEP_COMPONENTS = [Step1Identification, Step2StatutJuridique, Step3DescriptionPhysique];

function isStepValid(step: number, data: Partial<Monument>): boolean {
  switch (step) {
    case 1:
      return !!(data.nom?.trim() && data.commune?.trim());
    case 2:
      return !!(data.protection && data.proprietaire);
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
          <span className="font-medium">{currentStepInfo.title}</span>
          <span className="text-muted-foreground">Étape {currentStep} / {lastStep}</span>
        </div>
        <Progress value={progressPercent} className="h-1.5" />
        <p className="text-xs text-muted-foreground">{currentStepInfo.description}</p>
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
                tabulation) et `inert` (hors de l'arbre d'accessibilité). */}
            <div className="grid">
              {STEP_COMPONENTS.map((Step, i) => {
                const actif = currentStep === i + 1;
                return (
                  <div
                    key={i}
                    className={cn(
                      'col-start-1 row-start-1 min-w-0',
                      !actif && 'invisible pointer-events-none'
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
            Précédent
          </Button>
          <Button
            onClick={handleNext}
            disabled={!canProceed || (saving && currentStep === lastStep)}
            className="h-12 px-8 text-base"
          >
            {saving && currentStep === lastStep
              ? <Loader2 className="h-5 w-5 animate-spin" />
              : currentStep === lastStep
                ? isEditing ? 'Enregistrer' : 'Terminer'
                : <>Suivant <ChevronRight className="h-5 w-5 ml-1.5" /></>}
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
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="nom">Nom du monument *</Label>
        <Input
          id="nom"
          value={data.nom ?? ''}
          onChange={(e) => onChange({ nom: e.target.value })}
          placeholder="Ex : Église Saint-Malo"
        />
      </div>
      {/* Pleine largeur comme le nom : « Saint-Caradec-Trégomel » ou
          « Colleville-Montgomery » doivent tenir en entier dans le champ, et
          les suggestions (qui en épousent la largeur) rester lisibles. */}
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="commune">Commune *</Label>
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
        <Label htmlFor="protection">Niveau de protection *</Label>
        <Select value={data.protection ?? ''} onValueChange={setProtection}>
          <SelectTrigger id="protection" className={SELECT_TRIGGER}>
            <SelectValue placeholder="Sélectionner..." />
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
          Date de protection
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
          Détail de la protection
        </Label>
        <Input
          id="typeProtection"
          value={data.typeProtection ?? ''}
          onChange={(e) => onChange({ typeProtection: e.target.value })}
          placeholder={
            sansProtection
              ? 'Sans objet pour un bien non protégé'
              : 'Ex : Classé MH par arrêté du 16 juin 1928'
          }
          disabled={sansProtection}
        />
      </div>
      <div className={FIELD}>
        <Label htmlFor="proprietaire">Type de propriétaire *</Label>
        <Select
          value={data.proprietaire ?? ''}
          onValueChange={(v) => onChange({ proprietaire: v as Monument['proprietaire'] })}
        >
          <SelectTrigger id="proprietaire" className={SELECT_TRIGGER}>
            <SelectValue placeholder="Sélectionner..." />
          </SelectTrigger>
          <SelectContent>
            {OWNERSHIP_TYPES.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

function Step3DescriptionPhysique({ data, onChange }: StepProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={FIELD}>
        <Label htmlFor="siecleConstruction">Siècle de construction</Label>
        <Input
          id="siecleConstruction"
          value={data.siecleConstruction ?? ''}
          onChange={(e) => onChange({ siecleConstruction: e.target.value })}
          placeholder="Ex : XVe siècle"
        />
      </div>
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="descriptionGenerale">Description générale de la protection</Label>
        <Textarea
          id="descriptionGenerale"
          value={data.descriptionGenerale ?? ''}
          onChange={(e) => onChange({ descriptionGenerale: e.target.value })}
          placeholder="Décrivez votre monument..."
          rows={4}
        />
      </div>
      <div className={cn(FIELD, 'md:col-span-2')}>
        <Label htmlFor="etatConservation">État de conservation *</Label>
        <Select
          value={data.etatConservation ?? ''}
          onValueChange={(v) => onChange({ etatConservation: v as Monument['etatConservation'] })}
        >
          <SelectTrigger id="etatConservation" className={SELECT_TRIGGER}>
            <SelectValue placeholder="Sélectionner..." />
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
          Un monument en péril ou en mauvais état ouvre les dispositifs d&rsquo;urgence.
          Cette réponse vaut pour tous vos projets de travaux sur ce monument.
        </p>
      </div>
    </div>
  );
}
