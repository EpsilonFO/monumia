import { useState, useEffect, useRef } from 'react';
import { Search, MapPin, Shield, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { merimeeService } from '@/services/merimee.service';
import type { MerimeeRecord } from '@/types';

interface MerimeeSearchProps {
  onSelect: (record: MerimeeRecord) => void;
}

export function MerimeeSearch({ onSelect }: MerimeeSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MerimeeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      const data = await merimeeService.search(query);
      setResults(data);
      setLoading(false);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Rechercher par nom, commune ou référence Mérimée..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {query.length >= 2 && loading && (
        <div className="flex justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {query.length >= 2 && !loading && results.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-4">
          Aucun résultat trouvé pour &laquo;&nbsp;{query}&nbsp;&raquo;
        </p>
      )}

      {results.length > 0 && (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {results.map((record) => (
            <Card
              key={record.reference}
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => onSelect(record)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0 flex-1">
                    <p className="font-medium leading-tight">
                      {record.titre_editorial_de_la_notice}
                    </p>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">
                        {record.commune_actuelle
                          ? `${record.commune_forme_index} → ${record.commune_actuelle}`
                          : record.commune_forme_index}
                        {' — '}
                        {record.departement_en_lettres}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Shield className="h-3.5 w-3.5 shrink-0" />
                      <span>{record.typologie_de_la_protection}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <Badge variant="outline" className="text-xs font-mono">
                      {record.reference}
                    </Badge>
                    <Button size="sm" variant="ghost" className="text-xs h-7">
                      Sélectionner
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
