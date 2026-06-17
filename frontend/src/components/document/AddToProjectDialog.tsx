import { useEffect, useMemo, useState } from 'react';
import { Building2, Check, Loader2, Search } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { availableProjectsForDocument } from '@/lib/document-projects';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { toast } from 'sonner';
import type { Document } from '@/types';

interface AddToProjectDialogProps {
  document: Document | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddToProjectDialog({ document, open, onOpenChange }: AddToProjectDialogProps) {
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
      toast.success(`Document rattaché à ${count} projet${count > 1 ? 's' : ''}`);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du rattachement');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Ajouter à un autre projet</DialogTitle>
          {document && (
            <p className="text-[13px] text-[#8E92A4] truncate">{document.nom}</p>
          )}
        </DialogHeader>

        {projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2 text-center">
            <Building2 className="h-8 w-8 text-[#8E92A4]/50" />
            <p className="text-sm text-[#5C6178]">Aucun autre projet disponible.</p>
            <p className="text-xs text-[#8E92A4]">
              Ce document est déjà rattaché à tous vos projets.
            </p>
          </div>
        ) : (
          <>
            {projects.length > 8 && (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8E92A4]" />
                <Input
                  className="pl-9 h-10 text-[14px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
                  aria-label="Rechercher un projet"
                  placeholder="Rechercher un projet..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            )}

            <div className="flex-1 min-h-0 overflow-y-auto border border-[#E4E2DC] rounded-lg divide-y divide-[#E4E2DC]/60">
              {filtered.map((m) => {
                const isSelected = selected.has(m.id);
                return (
                  <button
                    key={m.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggle(m.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
                      isSelected ? 'bg-[#E8EAF6]' : 'hover:bg-[#F8F7F4]',
                    )}
                  >
                    <div className="h-8 w-8 shrink-0 rounded-lg flex items-center justify-center bg-[#E8EAF6]">
                      <Building2 className="h-4 w-4 text-[#1A237E]" strokeWidth={1.8} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-[#1B1E2E] truncate">{m.nom}</p>
                      {m.commune && (
                        <p className="text-[11px] text-[#8E92A4] truncate">{m.commune}</p>
                      )}
                    </div>
                    <div
                      className={cn(
                        'h-5 w-5 shrink-0 rounded-md border flex items-center justify-center transition-colors',
                        isSelected ? 'border-[#1A237E] bg-[#1A237E]' : 'border-[#E4E2DC]',
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3 text-white" strokeWidth={2.5} />}
                    </div>
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="text-sm text-[#8E92A4] text-center py-8">Aucun projet trouvé.</p>
              )}
            </div>

            <p className="text-[11px] text-[#8E92A4]">
              Le même document sera rattaché à chaque projet sélectionné, sans créer de copie.
            </p>
          </>
        )}

        <DialogFooter>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
            className="px-4 py-2 text-[13px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors"
          >
            Annuler
          </button>
          {projects.length > 0 && (
            <button
              type="button"
              onClick={handleAdd}
              disabled={selected.size === 0 || submitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg disabled:opacity-50 hover:shadow-md transition-all"
              style={{ background: '#1A237E' }}
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Rattacher à {selected.size} projet{selected.size > 1 ? 's' : ''}
            </button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
