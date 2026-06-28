import { Info, FolderOpen } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { C, SERIF } from '@/lib/brand';
import { projectColor } from '@/lib/project-color';
import type { Document } from '@/types';

interface Props {
  document: Document;
  monumentNames: Record<string, string>;
  dossiersById: Record<string, { titre: string; monumentId: string }>;
}

export function DocumentLocationsPopover({ document, monumentNames, dossiersById }: Props) {
  // Dossiers regroupés sous leur projet (un dossier appartient à un seul projet).
  const dossiersByProject = new Map<string, string[]>();
  for (const did of document.dossiersUtilises) {
    const d = dossiersById[did];
    if (!d) continue;
    const list = dossiersByProject.get(d.monumentId) ?? [];
    list.push(d.titre);
    dossiersByProject.set(d.monumentId, list);
  }

  // Fix M2/I2: only render project entries we actually know about (skip unnamed).
  const renderedProjectIds = document.monumentIds.filter((mid) => monumentNames[mid] !== undefined);

  // Dossiers not already grouped under a rendered project.
  const orphanDossiers: string[] = [];
  for (const did of document.dossiersUtilises) {
    const d = dossiersById[did];
    if (!d) continue;
    if (!renderedProjectIds.includes(d.monumentId)) {
      orphanDossiers.push(d.titre);
    }
  }

  const hasNothing = renderedProjectIds.length === 0 && orphanDossiers.length === 0;

  return (
    <Popover>
      <PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
        <button
          className="shrink-0 p-1 rounded-md transition-colors hover:bg-black/[0.04]"
          title="Où est utilisé ce fichier ?"
          aria-label="Informations : où est utilisé ce fichier"
        >
          <Info className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-72 max-h-80 overflow-y-auto p-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b" style={{ borderColor: C.border }}>
          <p className="text-[13px]" style={{ fontFamily: SERIF, color: C.ink }}>
            Où est ce fichier ?
          </p>
        </div>
        <div className="p-2 space-y-1">
          {hasNothing && (
            <p className="px-2 py-3 text-[12px] text-muted-foreground">
              Ce document n'est rattaché à aucun projet ni dossier.
            </p>
          )}
          {renderedProjectIds.map((mid) => {
            const dossiers = dossiersByProject.get(mid) ?? [];
            return (
              <div key={mid} className="rounded-lg px-2 py-2" style={{ background: C.cream }}>
                <div className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: projectColor(mid) }}
                  />
                  <span className="text-[12px] font-medium break-words" style={{ color: C.ink }}>
                    {monumentNames[mid]}
                  </span>
                </div>
                {dossiers.length > 0 && (
                  <ul className="mt-1.5 ml-[18px] space-y-1">
                    {dossiers.map((titre, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-1.5 text-[11px] break-words text-muted-foreground"
                      >
                        <FolderOpen className="h-3 w-3 shrink-0 mt-0.5" strokeWidth={1.8} />
                        <span className="break-words">{titre}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
          {orphanDossiers.length > 0 && (
            <div className="rounded-lg px-2 py-2" style={{ background: C.cream }}>
              <div className="flex items-center gap-2 mb-1.5">
                <FolderOpen className="h-3 w-3 shrink-0 text-muted-foreground" strokeWidth={1.8} />
                <span className="text-[12px] font-medium" style={{ color: C.ink }}>Dossiers</span>
              </div>
              <ul className="ml-[18px] space-y-1">
                {orphanDossiers.map((titre, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-[11px] break-words text-muted-foreground"
                  >
                    <FolderOpen className="h-3 w-3 shrink-0 mt-0.5" strokeWidth={1.8} />
                    <span className="break-words">{titre}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
