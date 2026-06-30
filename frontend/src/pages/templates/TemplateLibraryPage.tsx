import { useEffect, useMemo, useState } from 'react';
import { IconRecherche, IconModele } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { TemplateCard } from '@/components/template/TemplateCard';
import { useTemplateStore } from '@/stores/useTemplateStore';
import { normalize } from '@/lib/template-matching';

export function TemplateLibraryPage() {
  const { templates, loaded, loading, fetchAll } = useTemplateStore();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');

  useEffect(() => {
    if (!loaded) fetchAll();
  }, [loaded, fetchAll]);

  const types = useMemo(
    () => Array.from(new Set(templates.map((t) => t.typeDocument))).sort(),
    [templates],
  );

  const filtered = useMemo(() => {
    let list = templates;
    if (filterType !== 'all') list = list.filter((t) => t.typeDocument === filterType);
    if (search.trim()) {
      const tokens = normalize(search);
      list = list.filter((t) => {
        const haystack = [t.nom, t.description ?? '', t.organisme ?? '', ...t.tags].join(' ').toLowerCase();
        return tokens.every((tok) => haystack.includes(tok));
      });
    }
    return list;
  }, [templates, search, filterType]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Bibliothèque de modèles"
        description="Modèles de documents à télécharger, remplir, puis joindre à vos dossiers."
      />

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <IconRecherche className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-9 h-10 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10"
            placeholder="Rechercher un modèle..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-full sm:w-56 h-10 text-[14px] bg-card border-border">
            <SelectValue placeholder="Type de document" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les types</SelectItem>
            {types.map((t) => (
              <SelectItem key={t} value={t}>
                {t.replace(/_/g, ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Content */}
      {loading && !loaded ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-44 rounded-xl bg-border/30 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={IconModele}
          title="Aucun modèle"
          description={
            search || filterType !== 'all'
              ? 'Aucun modèle ne correspond à votre recherche.'
              : 'La bibliothèque de modèles est en cours de constitution.'
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((template) => (
            <TemplateCard key={template.id} template={template} />
          ))}
        </div>
      )}
    </div>
  );
}
