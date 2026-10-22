import { useEffect, useMemo, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { IconProjet, IconRecherche } from '@/components/icons';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { C } from '@/lib/brand';
import { availableProjectsForDocument } from '@/lib/document-projects';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import type { Document } from '@/types';

interface AddToProjectDialogProps {
  document: Document | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddToProjectDialog({ document, open, onOpenChange }: AddToProjectDialogProps) {
  const { t } = useTranslation(['documents', 'common']);
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const addToProjects = useDocumentStore((s) => s.addToProjects);

  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setSearch('');
      setSelected(new Set());
    }
  }, [open]);

  const projects = useMemo(
    () => availableProjectsForDocument(monuments, user?.id ?? '', document),
    [monuments, user?.id, document],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (m) => m.nom.toLowerCase().includes(q) || (m.commune ?? '').toLowerCase().includes(q),
    );
  }, [projects, search]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAdd = async () => {
    if (!document || selected.size === 0) return;
    const count = selected.size;
    setSubmitting(true);
    try {
      await addToProjects(document.id, [...selected]);
      toast.success(t('AddToProjectDialog.rattache', { count }));
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('AddToProjectDialog.erreurRattachement'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{t('AddToProjectDialog.titre')}</DialogTitle>
          {document && (
            <p className="text-[15px] truncate text-muted-foreground">{document.nom}</p>
          )}
        </DialogHeader>

        {projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2 text-center">
            <IconProjet className="h-8 w-8 text-muted-foreground opacity-50" />
            <p className="text-sm text-muted-foreground">{t('AddToProjectDialog.aucunAutre')}</p>
            <p className="text-xs text-muted-foreground">
              {t('AddToProjectDialog.dejaPartout')}
            </p>
          </div>
        ) : (
          <>
            {projects.length > 8 && (
              <div className="relative">
                <IconRecherche className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-9 h-10 text-[16px]"
                  style={{ background: C.card, borderColor: C.border }}
                  aria-label={t('AddToProjectDialog.rechercher')}
                  placeholder={t('AddToProjectDialog.rechercherPlaceholder')}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            )}

            <div className="flex-1 min-h-0 overflow-y-auto rounded-lg divide-y" style={{ border: `1px solid ${C.border}`, borderColor: C.border }}>
              {filtered.map((m) => {
                const isSelected = selected.has(m.id);
                return (
                  <button
                    key={m.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggle(m.id)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors"
                    style={{ background: isSelected ? C.paleBlue : undefined }}
                  >
                    <div className="h-8 w-8 shrink-0 rounded-lg flex items-center justify-center" style={{ background: C.paleBlue }}>
                      <IconProjet className="h-4 w-4" style={{ color: C.blue }} strokeWidth={1.8} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] font-medium truncate" style={{ color: C.ink }}>{m.nom}</p>
                      {m.commune && (
                        <p className="text-[13px] truncate text-muted-foreground">{m.commune}</p>
                      )}
                    </div>
                    <div
                      className="h-5 w-5 shrink-0 rounded-md border flex items-center justify-center transition-colors"
                      style={{
                        borderColor: isSelected ? C.blue : C.border,
                        background: isSelected ? C.blue : undefined,
                      }}
                    >
                      {isSelected && <Check className="h-3 w-3 text-white" strokeWidth={2.5} />}
                    </div>
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="text-sm text-center py-8 text-muted-foreground">{t('AddToProjectDialog.aucunTrouve')}</p>
              )}
            </div>

            <p className="text-[13px] text-muted-foreground">
              {t('AddToProjectDialog.explication')}
            </p>
          </>
        )}

        <DialogFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="px-4 py-2 text-[15px] font-medium rounded-lg transition-colors text-muted-foreground"
            style={{ border: `1px solid ${C.border}` }}
          >
            {t('common:actions.annuler')}
          </button>
          {projects.length > 0 && (
            <button
              type="button"
              onClick={handleAdd}
              disabled={selected.size === 0 || submitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-[15px] font-semibold text-white rounded-lg disabled:opacity-50 hover:shadow-md transition-all"
              style={{ background: C.orange }}
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {t('AddToProjectDialog.rattacher', { count: selected.size })}
            </button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
