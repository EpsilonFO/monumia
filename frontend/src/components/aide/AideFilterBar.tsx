import { Search, SlidersHorizontal } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { WORK_TYPES } from '@/constants/monument-options';
import { useAideStore } from '@/stores/useAideStore';
import type { AideCategory, WorkType } from '@/types';

export function AideFilterBar() {
  const filters = useAideStore((s) => s.filters);
  const setFilters = useAideStore((s) => s.setFilters);

  const toggleCategory = (cat: AideCategory) => {
    const current = filters.categories;
    const next = current.includes(cat)
      ? current.filter((c) => c !== cat)
      : [...current, cat];
    setFilters({ categories: next });
  };

  const toggleTravaux = (t: WorkType) => {
    const current = filters.travauxFiltres;
    const next = current.includes(t)
      ? current.filter((v) => v !== t)
      : [...current, t];
    setFilters({ travauxFiltres: next });
  };

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Rechercher une aide..."
          value={filters.searchQuery}
          onChange={(e) => setFilters({ searchQuery: e.target.value })}
        />
      </div>

      {/* Mode toggle */}
      <div className="flex items-center gap-3">
        <Switch
          id="mode-projet"
          checked={filters.modeProjet}
          onCheckedChange={(v) => setFilters({ modeProjet: v })}
        />
        <Label htmlFor="mode-projet" className="cursor-pointer text-sm">
          <span className="font-medium">Mode projet</span>
          <span className="text-muted-foreground ml-1">
            — filtrer par type de travaux
          </span>
        </Label>
      </div>

      {/* Travaux filter (only in project mode) */}
      {filters.modeProjet && (
        <div className="space-y-2">
          <p className="text-sm font-medium flex items-center gap-1.5">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Travaux envisagés
          </p>
          <div className="flex flex-wrap gap-1.5">
            {WORK_TYPES.map((w) => {
              const active = filters.travauxFiltres.includes(w.value as WorkType);
              return (
                <Badge
                  key={w.value}
                  variant={active ? 'default' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => toggleTravaux(w.value as WorkType)}
                >
                  {w.label}
                </Badge>
              );
            })}
          </div>
        </div>
      )}

      {/* Category filter */}
      <div className="space-y-2">
        <p className="text-sm font-medium">Catégorie</p>
        <div className="flex flex-wrap gap-1.5">
          {AIDE_CATEGORIES.map((cat) => {
            const active = filters.categories.includes(cat.value as AideCategory);
            return (
              <Badge
                key={cat.value}
                variant={active ? 'default' : 'outline'}
                className={`cursor-pointer text-xs ${active ? cat.color : ''}`}
                onClick={() => toggleCategory(cat.value as AideCategory)}
              >
                {cat.label}
              </Badge>
            );
          })}
        </div>
      </div>
    </div>
  );
}
