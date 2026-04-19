import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ChevronLeft, ChevronRight, Image, Loader2, X } from 'lucide-react';
import {
  PROTECTION_LEVELS,
  OWNERSHIP_TYPES,
  ETATS_CONSERVATION,
  URGENCE_TRAVAUX,
  WORK_TYPES,
} from '@/constants/monument-options';
import type { Monument, WorkType } from '@/types';

export interface PendingPhoto {
  file: File;
  preview: string;
  nom: string;
}

interface MonumentFormProps {
  initialData?: Partial<Monument>;
  onSubmit: (data: Partial<Monument>, pendingPhotos: PendingPhoto[]) => void;
  isEditing?: boolean;
  saving?: boolean;
}

const STEPS = [
  { number: 1, title: 'Identification', description: 'Nom et localisation' },
  { number: 2, title: 'Statut juridique', description: 'Protection et propriété' },
  { number: 3, title: 'Description physique', description: 'Architecture et matériaux' },
  { number: 4, title: 'État actuel', description: 'Conservation et travaux' },
  { number: 5, title: 'Photos', description: 'Documentation photographique' },
];

function isStepValid(step: number, data: Partial<Monument>): boolean {
  switch (step) {
    case 1:
      return !!(data.nom?.trim() && data.commune?.trim());
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
  const [pendingPhotos, setPendingPhotos] = useState<PendingPhoto[]>([]);

  const update = (updates: Partial<Monument>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  };

  const canProceed = isStepValid(currentStep, formData);

  const handleNext = () => {
    if (!canProceed) return;
    if (currentStep < 5) setCurrentStep(currentStep + 1);
    else onSubmit(formData, pendingPhotos);
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
          {currentStep === 5 && <Step5Photos pendingPhotos={pendingPhotos} setPendingPhotos={setPendingPhotos} />}
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
    </div>
  );
}

function Step3DescriptionPhysique({ data, onChange }: StepProps) {
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
      <div className="md:col-span-2">
        <Label htmlFor="descriptionGenerale">Description générale de la protection</Label>
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

function Step5Photos({ pendingPhotos, setPendingPhotos }: {
  pendingPhotos: PendingPhoto[];
  setPendingPhotos: React.Dispatch<React.SetStateAction<PendingPhoto[]>>;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const MAX_SIZE = 10 * 1024 * 1024; // 10 Mo
  const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];

  const addFiles = useCallback((files: FileList | File[]) => {
    const valid = Array.from(files).filter(
      (f) => ACCEPTED.includes(f.type) && f.size <= MAX_SIZE
    );
    const newPhotos = valid.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
      nom: file.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' '),
    }));
    setPendingPhotos((prev) => [...prev, ...newPhotos]);
  }, [setPendingPhotos]);

  const removePhoto = (index: number) => {
    setPendingPhotos((prev) => {
      URL.revokeObjectURL(prev[index].preview);
      return prev.filter((_, i) => i !== index);
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragOver ? 'border-primary bg-primary/5' : ''
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <Image className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm font-medium">Glissez-déposez vos photos ici</p>
        <p className="text-xs text-muted-foreground mt-1">
          JPG, PNG, WebP — max 10 Mo par fichier
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) addFiles(e.target.files);
            e.target.value = '';
          }}
        />
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          type="button"
          onClick={() => fileInputRef.current?.click()}
        >
          Parcourir
        </Button>
      </div>

      {pendingPhotos.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {pendingPhotos.map((photo, index) => (
            <div key={index} className="space-y-1.5">
              <div className="relative group aspect-[4/3] rounded-lg overflow-hidden bg-muted">
                <img
                  src={photo.preview}
                  alt={photo.nom}
                  className="w-full h-full object-cover"
                />
                <button
                  type="button"
                  onClick={() => removePhoto(index)}
                  className="absolute top-1 right-1 bg-black/60 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <Input
                value={photo.nom}
                onChange={(e) =>
                  setPendingPhotos((prev) =>
                    prev.map((p, i) => i === index ? { ...p, nom: e.target.value } : p)
                  )
                }
                placeholder="Nom de la photo"
                className="text-xs h-7"
              />
            </div>
          ))}
        </div>
      )}

      {pendingPhotos.length === 0 && (
        <p className="text-sm text-muted-foreground text-center">
          Aucune photo ajoutée. Vous pouvez en ajouter plus tard.
        </p>
      )}
    </div>
  );
}
