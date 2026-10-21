import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { communeService, type CommuneResult } from '@/services/commune.service';
import { surlignerDebut } from './surligner';

interface ChampCommuneProps {
  id: string;
  value: string;
  /** Commune reconnue dans le référentiel (code INSEE posé). */
  reconnue: boolean;
  /** Saisie libre : le code INSEE n'est plus fiable, le parent le remet à zéro. */
  onChange: (nom: string) => void;
  onSelect: (commune: CommuneResult) => void;
}

const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;

/**
 * Recherche de commune au dessin de la maquette (`.ac`, `.ac-list`), sur le
 * référentiel INSEE du serveur : même logique que `CommuneAutocomplete`, qui
 * reste celle du formulaire d'édition.
 *
 * Choisir dans la liste fournit le code INSEE, dont le backend déduit
 * département, région et population : c'est ce qui rend les aides
 * territoriales évaluables. Une saisie libre n'est acceptée que si le serveur
 * retrouve la commune par son nom exact (`resolve_code_insee`, sinon 400
 * « Commune introuvable ») : le message de liste vide ne promet donc pas
 * qu'on peut la garder. La recherche part de la frappe, jamais de `value` : un
 * préremplissage Mérimée n'ouvre pas la liste.
 */
export function ChampCommune({ id, value, reconnue, onChange, onSelect }: ChampCommuneProps) {
  const { t } = useTranslation('monuments');
  const listId = `${id}-liste`;
  const [results, setResults] = useState<CommuneResult[]>([]);
  const [requete, setRequete] = useState('');
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const blurRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      setOpen(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(() => {
      const controller = new AbortController();
      abortRef.current = controller;
      communeService.search(query, controller.signal).then((data) => {
        if (controller.signal.aborted) return;
        setResults(data);
        setRequete(query);
        setActive(0);
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
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    if (e.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (results.length === 0) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => (i + step + results.length) % results.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(results[active]);
    }
  };

  return (
    <>
      <div className="ac">
        <input
          className="txt"
          id={id}
          value={value}
          placeholder={t('ChampCommune.placeholder')}
          autoComplete="off"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open && results.length ? `${listId}-${active}` : undefined}
          onChange={(e) => {
            onChange(e.target.value);
            search(e.target.value);
          }}
          onKeyDown={onKeyDown}
          onBlur={() => {
            blurRef.current = setTimeout(() => setOpen(false), 120);
          }}
        />
        {loading && <Loader2 className="spin animate-spin" aria-hidden="true" />}
        <ul className="ac-list" id={listId} role="listbox" hidden={!open}>
          {results.length > 0 ? (
            results.map((c, i) => (
              <li
                key={c.codeInsee}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                // Garder le focus dans le champ : sans ça, le blur referme la
                // liste avant que le clic n'aboutisse.
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(c);
                }}
                onMouseEnter={() => setActive(i)}
              >
                <span>{surlignerDebut(c.nom, requete)}</span>
                <small>
                  {c.codeDepartement}
                  {c.departement ? ` · ${c.departement}` : ''}
                </small>
              </li>
            ))
          ) : (
            <li className="none">
              {t('ChampCommune.aucunResultat', { requete })}
            </li>
          )}
        </ul>
      </div>
      {reconnue && value.trim() && (
        <span className="ac-ok">
          <Picto nom="coche" />
          {t('ChampCommune.reconnue')}
        </span>
      )}
    </>
  );
}
