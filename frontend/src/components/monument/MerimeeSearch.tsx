import { useState, useEffect, useRef } from 'react';
import { Loader2 } from 'lucide-react';
import { IconRecherche, IconLocalisation } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';
import { merimeeService } from '@/services/merimee.service';
import type { MerimeeRecord } from '@/types';

interface MerimeeSearchProps {
  onSelect: (record: MerimeeRecord) => void;
}

/** Tonalité du badge de protection, dérivée du texte Mérimée (pas d'enum côté API). */
function protectionTone(typologie: string | undefined): { bg: string; fg: string; label: string } {
  const t = (typologie ?? '').toLowerCase();
  if (/(?:^|[^a-zà-ÿ])classé/.test(t)) return { bg: 'var(--secondary)', fg: 'var(--primary)', label: 'Classé MH' };
  if (/(?:^|[^a-zà-ÿ])inscrit/.test(t)) return { bg: 'var(--info-muted)', fg: 'var(--info)', label: 'Inscrit MH' };
  return { bg: 'var(--muted)', fg: 'var(--gray-fg)', label: typologie || 'Protection inconnue' };
}

export function MerimeeSearch({ onSelect }: MerimeeSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MerimeeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (abortRef.current) abortRef.current.abort();

    if (query.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      const controller = new AbortController();
      abortRef.current = controller;
      const data = await merimeeService.search(query, controller.signal);
      // Ignore les réponses d'une requête annulée (frappe plus récente).
      if (controller.signal.aborted) return;
      setResults(data);
      setLoading(false);
    }, 250);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  return (
    <div className="space-y-4">
      <div className="relative">
        <IconRecherche
          className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2"
          style={{ color: C.grayMuted }}
        />
        <input
          type="search"
          className="h-14 w-full rounded-2xl border pl-12 pr-4 text-[16px] outline-none transition-shadow placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
          style={{ borderColor: C.border, background: C.card, boxShadow: 'var(--shadow-card)', color: C.ink }}
          placeholder="Nom du monument, commune ou référence…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {query.length >= 2 && loading && (
        <div className="flex justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} />
        </div>
      )}

      {query.length >= 2 && !loading && results.length === 0 && (
        <p className="py-4 text-center text-[14px]" style={{ color: C.grayMuted }}>
          Aucun résultat pour «&nbsp;{query}&nbsp;». Vous pourrez décrire votre monument
          vous-même juste en dessous.
        </p>
      )}

      {results.length > 0 && (
        <ul className="max-h-[36vh] space-y-2.5 overflow-y-auto pr-1">
          {results.map((record) => {
            const tone = protectionTone(record.typologie_de_la_protection);
            return (
              <li key={record.reference}>
                <button
                  type="button"
                  onClick={() => onSelect(record)}
                  className="group w-full rounded-2xl border-2 border-border bg-card p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-warning hover:shadow-[var(--shadow-pop)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p
                        className="text-[16px] leading-snug"
                        style={{ fontFamily: SERIF, color: C.ink }}
                      >
                        {record.titre_editorial_de_la_notice}
                      </p>
                      <p
                        className="mt-1.5 flex items-center gap-1.5 text-[13px]"
                        style={{ color: C.grayFg }}
                      >
                        <IconLocalisation className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">
                          {record.commune_actuelle || record.commune_forme_index}
                          {' — '}
                          {record.departement_en_lettres}
                        </span>
                      </p>
                      <span
                        className="mt-2 inline-flex rounded-full px-2.5 py-0.5 text-[12px] font-semibold"
                        style={{ background: tone.bg, color: tone.fg }}
                      >
                        {tone.label}
                      </span>
                    </div>
                    <span
                      className="shrink-0 rounded-md border px-1.5 py-0.5 font-mono text-[11px]"
                      style={{ borderColor: C.border, color: C.grayMuted }}
                    >
                      {record.reference}
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
