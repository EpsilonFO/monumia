import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { merimeeService } from '@/services/merimee.service';
import { protectionDeNotice } from '@/lib/fiche-monument';
import type { MerimeeRecord } from '@/types';

interface RechercheMerimeeProps {
  id: string;
  onSelect: (record: MerimeeRecord) => void;
  /** Notice en cours de chargement après un choix. */
  chargement?: boolean;
}

const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;

/**
 * La recherche dans la base Mérimée, au dessin de la recherche de commune de la
 * maquette (`.ac`, `.ac-list`). Même service et même logique que
 * `MerimeeSearch` : saisie temporisée, requête précédente annulée.
 */
export function RechercheMerimee({ id, onSelect, chargement }: RechercheMerimeeProps) {
  const { t } = useTranslation('monuments');
  const listId = `${id}-liste`;
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MerimeeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const blurRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // La recherche part de la frappe (et non d'un effet sur `query`) : une saisie
  // temporisée, la requête précédente annulée.
  const search = (q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    abortRef.current?.abort();
    if (q.trim().length < MIN_CHARS) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      const controller = new AbortController();
      abortRef.current = controller;
      const data = await merimeeService.search(q, controller.signal);
      // Réponse d'une frappe périmée : la suivante a déjà pris la main.
      if (controller.signal.aborted) return;
      setResults(data);
      setActive(0);
      setLoading(false);
    }, DEBOUNCE_MS);
  };

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (blurRef.current) clearTimeout(blurRef.current);
      abortRef.current?.abort();
    },
    [],
  );

  const choose = (record: MerimeeRecord) => {
    setOpen(false);
    onSelect(record);
  };

  const showList = open && query.trim().length >= MIN_CHARS && (!loading || results.length > 0);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (!showList || results.length === 0) return;
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
    <div className="ac">
      <Picto nom="loupe" />
      <input
        className="txt srch-in"
        id={id}
        type="search"
        value={query}
        placeholder={t('RechercheMerimee.placeholder')}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && results.length ? `${listId}-${active}` : undefined}
        disabled={chargement}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          search(e.target.value);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        onBlur={() => {
          blurRef.current = setTimeout(() => setOpen(false), 120);
        }}
      />
      {(loading || chargement) && <Loader2 className="spin animate-spin" aria-hidden="true" />}
      <ul className="ac-list" id={listId} role="listbox" hidden={!showList}>
        {results.length > 0 ? (
          results.map((r, i) => (
            <li
              key={r.reference}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(r);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span>
                {r.titre_editorial_de_la_notice}
                <small className="sub">
                  {r.commune_actuelle || r.commune_forme_index}
                  {r.departement_en_lettres ? ` · ${r.departement_en_lettres}` : ''}
                </small>
              </span>
              <small>
                {protectionDeNotice(r.typologie_de_la_protection)} · {r.reference}
              </small>
            </li>
          ))
        ) : (
          <li className="none">
            {t('RechercheMerimee.aucunResultat', { requete: query.trim() })}
          </li>
        )}
      </ul>
    </div>
  );
}
