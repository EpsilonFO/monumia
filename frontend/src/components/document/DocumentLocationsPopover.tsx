import { Trans, useTranslation } from 'react-i18next';
import { IconInfo, IconDossierOuvert, IconLocalisation } from '@/components/icons';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { C, SERIF } from '@/lib/brand';
import { projectColor } from '@/lib/project-color';
import type { Document } from '@/types';

interface Props {
  document: Document;
  monumentNames: Record<string, string>;
  dossiersById: Record<string, { titre: string; monumentId: string }>;
  /** Déclencheur libellé (chip « Où est-ce rangé ? ») plutôt que la petite icône. */
  labelled?: boolean;
}

export function DocumentLocationsPopover({ document, monumentNames, dossiersById, labelled = false }: Props) {
  const { t } = useTranslation('documents');
  // Dossiers regroupés sous leur monument (un dossier n'en a qu'un).
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

  // Résumé factuel pour le déclencheur libellé (« Rangé dans … »), sans question.
  const projectCount = renderedProjectIds.length;
  const summary = projectCount >= 2
    ? t('DocumentLocationsPopover.resumeMonuments', { nombre: projectCount })
    : projectCount === 1
      ? monumentNames[renderedProjectIds[0]]
      : orphanDossiers.length > 0
        ? t('DocumentLocationsPopover.resumeUnDossier')
        : t('DocumentLocationsPopover.resumeAucun');

  return (
    <Popover>
      <PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
        {labelled ? (
          <button
            className="inline-flex items-center gap-1.5 text-[14.5px] text-muted-foreground transition-colors hover:underline underline-offset-2"
            title={t('DocumentLocationsPopover.voirOuRange')}
          >
            <IconLocalisation className="h-4 w-4" weight="fill" style={{ color: C.blue }} />
            <Trans
              t={t}
              i18nKey="DocumentLocationsPopover.rangeDans"
              values={{ resume: summary }}
              components={{ nom: <span className="font-semibold" style={{ color: C.ink }} /> }}
            />
          </button>
        ) : (
          <button
            className="shrink-0 p-1 rounded-md transition-colors hover:bg-black/[0.04]"
            title={t('DocumentLocationsPopover.ouUtilise')}
            aria-label={t('DocumentLocationsPopover.ouUtiliseAria')}
          >
            <IconInfo className="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        )}
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-72 max-h-80 overflow-y-auto p-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b" style={{ borderColor: C.border }}>
          <p className="text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
            {t('DocumentLocationsPopover.ouEstFichier')}
          </p>
        </div>
        <div className="p-2 space-y-1">
          {hasNothing && (
            <p className="px-2 py-3 text-[14px] text-muted-foreground">
              {t('DocumentLocationsPopover.rattacheANulle')}
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
                  <span className="text-[14px] font-medium break-words" style={{ color: C.ink }}>
                    {monumentNames[mid]}
                  </span>
                </div>
                {dossiers.length > 0 && (
                  <ul className="mt-1.5 ml-[20.5px] space-y-1">
                    {dossiers.map((titre, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-1.5 text-[13px] break-words text-muted-foreground"
                      >
                        <IconDossierOuvert className="h-3 w-3 shrink-0 mt-0.5" strokeWidth={1.8} />
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
                <IconDossierOuvert className="h-3 w-3 shrink-0 text-muted-foreground" strokeWidth={1.8} />
                <span className="text-[14px] font-medium" style={{ color: C.ink }}>{t('DocumentLocationsPopover.dossiers')}</span>
              </div>
              <ul className="ml-[20.5px] space-y-1">
                {orphanDossiers.map((titre, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-[13px] break-words text-muted-foreground"
                  >
                    <IconDossierOuvert className="h-3 w-3 shrink-0 mt-0.5" strokeWidth={1.8} />
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
