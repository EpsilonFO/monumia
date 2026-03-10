import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ChevronLeft, ChevronRight, Image, Loader2 } from 'lucide-react';
import {
  DENOMINATIONS,
  PROTECTION_LEVELS,
  OWNERSHIP_TYPES,
  ETATS_CONSERVATION,
  URGENCE_TRAVAUX,
  WORK_TYPES,
  MATERIAUX,
  AFFECTATAIRES,
} from '@/constants/monument-options';
import { REGIONS } from '@/constants/regions';
import type { Monument, WorkType } from '@/types';

interface MonumentFormProps {
  initialData?: Partial<Monument>;
  onSubmit: (data: Partial<Monument>) => void;
  isEditing?: boolean;
  saving?: boolean;
}

const STEPS = [
  { number: 1, title: 'Identification', description: 'Nom, adresse et localisation' },
  { number: 2, title: 'Statut juridique', description: 'Protection et propriété' },
  { number: 3, title: 'Description physique', description: 'Architecture et matériaux' },
  { number: 4, title: 'État actuel', description: 'Conservation et travaux' },
  { number: 5, title: 'Photos', description: 'Documentation photographique' },
];

function isStepValid(step: number, data: Partial<Monument>): boolean {
  switch (step) {
    case 1:
      return !!(data.nom?.trim() && data.denomination && data.adresse?.trim() && data.commune?.trim());
    case 2:
      return !!(data.protection && data.proprietaire);
    case 4:
      return !!(data.etatConservation);
    default:
      return true;
  }
}

export function MonumentForm({ initialData, onSubmit, isEditing, saving }: MonumentFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<Partial<Monument>>(initialData ?? {});

  const update = (updates: Partial<Monument>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  };

  const canProceed = isStepValid(currentStep, formData);

  const handleNext = () => {
    if (!canProceed) return;
    if (currentStep < 5) setCurrentStep(currentStep + 1);
    else onSubmit(formData);
  };

  const handlePrev = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  const progressPercent = ((currentStep - 1) / (STEPS.length - 1)) * 100;
  const currentStepInfo = STEPS[currentStep - 1];

  return (
    <div className="space-y-6">
      {/* Step Indicator */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">{currentStepInfo.title}</span>
          <span className="text-muted-foreground">Étape {currentStep} / {STEPS.length}</span>
        </div>
        <Progress value={progressPercent} className="h-1.5" />
        <p className="text-xs text-muted-foreground">{currentStepInfo.description}</p>
      </div>

      {/* Step Content */}
      <Card>
        <CardContent className="pt-6">
          {currentStep === 1 && <Step1Identification data={formData} onChange={update} />}
          {currentStep === 2 && <Step2StatutJuridique data={formData} onChange={update} />}
          {currentStep === 3 && <Step3DescriptionPhysique data={formData} onChange={update} />}
          {currentStep === 4 && <Step4EtatActuel data={formData} onChange={update} />}
          {currentStep === 5 && <Step5Photos data={formData} />}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={handlePrev}
          disabled={currentStep === 1}
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          Précédent
        </Button>
        <Button onClick={handleNext} disabled={!canProceed || (saving && currentStep === 5)}>
          {saving && currentStep === 5
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : currentStep === 5
              ? isEditing ? 'Enregistrer' : 'Terminer'
              : <>Suivant <ChevronRight className="h-4 w-4 ml-1" /></>}
        </Button>
      </div>
    </div>
  );
}

// --- Step Components ---

interface StepProps {
  data: Partial<Monument>;
  onChange: (updates: Partial<Monument>) => void;
}

function Step1Identification({ data, onChange }: StepProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="md:col-span-2">
        <Label htmlFor="nom">Nom du monument *</Label>
        <Input
          id="nom"
          value={data.nom ?? ''}
          onChange={(e) => onChange({ nom: e.target.value })}
          placeholder="Ex : Église Saint-Malo"
        />
      </div>
      <div>
        <Label htmlFor="denomination">Dénomination *</Label>
        <Select
          value={data.denomination ?? ''}
          onValueChange={(v) => onChange({ denomination: v })}
        >
          <SelectTrigger id="denomination">
            <SelectValue placeholder="Sélectionner..." />
          </SelectTrigger>
          <SelectContent>
            {DENOMINATIONS.map((d) => (
              <SelectItem key={d.value} value={d.value}>
                {d.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="md:col-span-2">
        <Label htmlFor="adresse">Adresse *</Label>
        <Input
          id="adresse"
          value={data.adresse ?? ''}
          onChange={(e) => onChange({ adresse: e.target.value })}
          placeholder="Ex : Place du Château"
        />
      </div>
      <div>
        <Label htmlFor="commune">Commune *</Label>
        <Input
          id="commune"
          value={data.commune ?? ''}
          onChange={(e) => onChange({ commune: e.target.value })}
          placeholder="Ex : Valognes"
        />
      </div>
    </div>
  );
}

function Step2StatutJuridique({ data, onChange }: StepProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <Label htmlFor="protection">Niveau de protection *</Label>
        <Select
          value={data.protection ?? ''}
          onValueChange={(v) => onChange({ protection: v as Monument['protection'] })}
        >
          <SelectTrigger id="protection">
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
      <div>
        <Label htmlFor="dateProtection">Date de protection</Label>
        <Input
          id="dateProtection"
          type="date"
          value={data.dateProtection ?? ''}
          onChange={(e) => onChange({ dateProtection: e.target.value })}
        />
      </div>
      <div className="md:col-span-2">
        <Label htmlFor="typeProtection">Détail de la protection</Label>
        <Input
          id="typeProtection"
          value={data.typeProtection ?? ''}
          onChange={(e) => onChange({ typeProtection: e.target.value })}
          placeholder="Ex : Classé MH par arrêté du 16 juin 1928"
        />
      </div>
      <div>
        <Label htmlFor="proprietaire">Type de propriétaire *</Label>
        <Select
          value={data.proprietaire ?? ''}
          onValueChange={(v) => onChange({ proprietaire: v as Monument['proprietaire'] })}
        >
          <SelectTrigger id="proprietaire">
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
      <div>
        <Label htmlFor="affectataire">Affectation</Label>
        <Select
          value={data.affectataire ?? ''}
          onValueChange={(v) => onChange({ affectataire: v })}
        >
          <SelectTrigger id="affectataire">
            <SelectValue placeholder="Sélectionner..." />
          </SelectTrigger>
          <SelectContent>
            {AFFECTATAIRES.map((a) => (
              <SelectItem key={a.value} value={a.value}>
                {a.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

function Step3DescriptionPhysique({ data, onChange }: StepProps) {
  const selectedMateriaux = data.materiaux ?? [];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <Label htmlFor="siecleConstruction">Siècle de construction</Label>
        <Input
          id="siecleConstruction"
          value={data.siecleConstruction ?? ''}
          onChange={(e) => onChange({ siecleConstruction: e.target.value })}
          placeholder="Ex : XVe siècle"
        />
      </div>
      <div>
        <Label htmlFor="superficie">Superficie (m²)</Label>
        <Input
          id="superficie"
          type="number"
          value={data.superficie ?? ''}
          onChange={(e) => onChange({ superficie: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="Ex : 1200"
        />
      </div>
      <div>
        <Label htmlFor="typeCouverture">Type de couverture</Label>
        <Input
          id="typeCouverture"
          value={data.typeCouverture ?? ''}
          onChange={(e) => onChange({ typeCouverture: e.target.value })}
          placeholder="Ex : ardoise"
        />
      </div>
      <div>
        <Label htmlFor="nombreNiveaux">Nombre de niveaux</Label>
        <Input
          id="nombreNiveaux"
          type="number"
          value={data.nombreNiveaux ?? ''}
          onChange={(e) => onChange({ nombreNiveaux: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="Ex : 2"
        />
      </div>
      <div className="md:col-span-2">
        <Label>Matériaux</Label>
        <div className="flex flex-wrap gap-2 mt-2">
          {MATERIAUX.map((m) => {
            const selected = selectedMateriaux.includes(m.value);
            return (
              <Badge
                key={m.value}
                variant={selected ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => {
                  const next = selected
                    ? selectedMateriaux.filter((v) => v !== m.value)
                    : [...selectedMateriaux, m.value];
                  onChange({ materiaux: next });
                }}
              >
                {m.label}
              </Badge>
            );
          })}
        </div>
      </div>
      <div className="md:col-span-2">
        <Label htmlFor="descriptionGenerale">Description générale</Label>
        <Textarea
          id="descriptionGenerale"
          value={data.descriptionGenerale ?? ''}
          onChange={(e) => onChange({ descriptionGenerale: e.target.value })}
          placeholder="Décrivez votre monument..."
          rows={4}
        />
      </div>
    </div>
  );
}

function Step4EtatActuel({ data, onChange }: StepProps) {
  const selectedTravaux = (data.travauxEnvisages ?? []) as WorkType[];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <Label htmlFor="etatConservation">État de conservation *</Label>
        <Select
          value={data.etatConservation ?? ''}
          onValueChange={(v) => onChange({ etatConservation: v as Monument['etatConservation'] })}
        >
          <SelectTrigger id="etatConservation">
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
      </div>
      <div>
        <Label htmlFor="urgenceTravaux">Urgence des travaux</Label>
        <Select
          value={data.urgenceTravaux ?? ''}
          onValueChange={(v) => onChange({ urgenceTravaux: v as Monument['urgenceTravaux'] })}
        >
          <SelectTrigger id="urgenceTravaux">
            <SelectValue placeholder="Sélectionner..." />
          </SelectTrigger>
          <SelectContent>
            {URGENCE_TRAVAUX.map((u) => (
              <SelectItem key={u.value} value={u.value}>
                {u.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="md:col-span-2">
        <Label>Travaux envisagés</Label>
        <div className="flex flex-wrap gap-2 mt-2">
          {WORK_TYPES.map((w) => {
            const selected = selectedTravaux.includes(w.value as WorkType);
            return (
              <Badge
                key={w.value}
                variant={selected ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => {
                  const next = selected
                    ? selectedTravaux.filter((v) => v !== w.value)
                    : [...selectedTravaux, w.value as WorkType];
                  onChange({ travauxEnvisages: next });
                }}
              >
                {w.label}
              </Badge>
            );
          })}
        </div>
      </div>
      <div className="md:col-span-2 flex items-center gap-2">
        <Checkbox
          id="diagnosticRealise"
          checked={data.diagnosticRealise ?? false}
          onCheckedChange={(checked) =>
            onChange({ diagnosticRealise: checked === true })
          }
        />
        <Label htmlFor="diagnosticRealise" className="cursor-pointer">
          Un diagnostic a été réalisé
        </Label>
      </div>
      <div>
        <Label htmlFor="derniersTravaux">Date des derniers travaux</Label>
        <Input
          id="derniersTravaux"
          type="date"
          value={data.derniersTravaux ?? ''}
          onChange={(e) => onChange({ derniersTravaux: e.target.value })}
        />
      </div>
      <div className="md:col-span-2">
        <Label htmlFor="descriptionEtat">Description de l'état actuel</Label>
        <Textarea
          id="descriptionEtat"
          value={data.descriptionEtat ?? ''}
          onChange={(e) => onChange({ descriptionEtat: e.target.value })}
          placeholder="Décrivez les dégradations, urgences..."
          rows={4}
        />
      </div>
    </div>
  );
}

function Step5Photos({ data }: { data: Partial<Monument> }) {
  const photos = data.photos ?? [];

  return (
    <div className="space-y-4">
      <div className="border-2 border-dashed rounded-lg p-8 text-center">
        <Image className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm font-medium">Glissez-déposez vos photos ici</p>
        <p className="text-xs text-muted-foreground mt-1">
          JPG, PNG — max 10 Mo par fichier
        </p>
        <Button variant="outline" size="sm" className="mt-3">
          Parcourir
        </Button>
      </div>

      {photos.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {photos.map((photo) => (
            <div
              key={photo.id}
              className="aspect-[4/3] rounded-lg bg-muted flex items-center justify-center"
            >
              <div className="text-center">
                <Image className="h-6 w-6 text-muted-foreground mx-auto" />
                <p className="text-xs text-muted-foreground mt-1 px-2 truncate">
                  {photo.legende}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {photos.length === 0 && (
        <p className="text-sm text-muted-foreground text-center">
          Aucune photo ajoutée. Vous pouvez en ajouter plus tard.
        </p>
      )}
    </div>
  );
}
