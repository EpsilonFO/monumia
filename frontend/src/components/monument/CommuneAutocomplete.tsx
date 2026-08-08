import { useEffect, useId, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { IconLocalisation } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { communeService, type CommuneResult } from '@/services/commune.service';

interface CommuneAutocompleteProps {
  /** Nom saisi ou choisi. */
  value: string;
  /** Saisie libre : le code INSEE n'est plus fiable, le parent le remet à zéro. */
  onChange: (nom: string) => void;
  /** Commune choisie dans la liste : nom + code INSEE du référentiel. */
  onSelect: (commune: CommuneResult) => void;
  id?: string;
  placeholder?: string;
}

/** Sous ce seuil, l'API ne répond pas (et une lettre ramènerait 35 000 communes). */
const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;

/**
 * Champ « Commune » avec suggestions du référentiel INSEE, dans l'esprit de la
 * recherche Mérimée : on tape « gome », on choisit « Gometz-la-Ville ».
 *
 * L'enjeu n'est pas cosmétique : choisir dans la liste fournit le code INSEE,
 * dont le backend déduit département, région et population — donc l'éligibilité
 * aux aides territoriales. La saisie libre reste possible (commune introuvable,
 * API en panne) : le backend retombe alors sur la résolution par nom.
 *
 * La recherche est déclenchée par la frappe, jamais par un effet sur `value` :
 * un préremplissage Mérimée ne doit ni requêter ni ouvrir la liste.
 */
export function CommuneAutocomplete({
  value,
  onChange,
  onSelect,
  id,
  placeholder = 'Ex : Valognes',
}: CommuneAutocompleteProps) {
  const listId = useId();
  const [results, setResults] = useState<CommuneResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const blurRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Au démontage : ni requête en vol, ni minuteur qui réveille un composant mort.
  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (blurRef.current) clearTimeout(blurRef.current);
      abortRef.current?.abort();
    },
    [],
  );

  const search = (query: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    abortRef.current?.abort();
    if (query.trim().length < MIN_CHARS) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(() => {
      const controller = new AbortController();
      abortRef.current = controller;
      communeService.search(query, controller.signal).then((data) => {
        // Réponse d'une frappe périmée : la suivante a déjà pris la main.
        if (controller.signal.aborted) return;
        setResults(data);
        setActive(-1);
        setLoading(false);
        setOpen(true);
      });
    }, DEBOUNCE_MS);
  };

  const choose = (commune: CommuneResult) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    abortRef.current?.abort();
    onSelect(commune);
    setResults([]);
    setLoading(false);
    setOpen(false);
    setActive(-1);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => (i + step + results.length) % results.length);
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault();
      choose(results[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const showList = open && results.length > 0;

  return (
    <div className="relative">
      <Input
        id={id}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          search(e.target.value);
        }}
        onKeyDown={onKeyDown}
        onFocus={() => setOpen(true)}
        // Le clic sur une suggestion passe par le blur : on laisse le temps au
        // clic d'aboutir avant de refermer.
        onBlur={() => {
          blurRef.current = setTimeout(() => setOpen(false), 150);
        }}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
      />
      {loading && (
        <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
      )}

      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-md border border-border bg-popover py-1 shadow-md"
        >
          {results.map((commune, i) => (
            <li key={commune.codeInsee} role="option" aria-selected={i === active}>
              <button
                type="button"
                // Garder le focus dans le champ : sans ça, le blur programme la
                // fermeture de la liste avant que le clic n'aboutisse.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(commune)}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors',
                  i === active ? 'bg-accent/10' : 'hover:bg-muted',
                )}
              >
                <IconLocalisation className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{commune.nom}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                  {commune.codeDepartement}
                  {commune.departement ? ` · ${commune.departement}` : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
