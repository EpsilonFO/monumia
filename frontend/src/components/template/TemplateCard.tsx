import { Download, FileText, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { templateService } from '@/services/template.service';
import { formatBadge } from '@/lib/template-format';
import { formatFileSize } from '@/lib/format-utils';
import { C, SERIF } from '@/lib/brand';
import type { Template } from '@/types';

interface TemplateCardProps {
  template: Template;
}

export function TemplateCard({ template }: TemplateCardProps) {
  const badge = formatBadge(template.extension);
  const categories = template.categoriesAide
    .map((c) => AIDE_CATEGORIES.find((cat) => cat.value === c))
    .filter((c): c is (typeof AIDE_CATEGORIES)[number] => Boolean(c));

  return (
    <div
      className="group flex h-full flex-col overflow-hidden rounded-xl border transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:-translate-y-0.5"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex flex-1 flex-col px-5 pt-5 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
            style={{ background: C.paleBlue }}
          >
            <FileText className="h-5 w-5" style={{ color: C.blue }} strokeWidth={1.8} />
          </div>
          <span
            className={`shrink-0 rounded-md px-2 py-0.5 text-[11px] font-bold tracking-wide ${badge.className}`}
          >
            {badge.label}
          </span>
        </div>

        <h3
          className="mt-3 text-[16px] leading-snug"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          {template.nom}
        </h3>
        {template.description && (
          <p className="mt-1 line-clamp-2 text-[13px]" style={{ color: '#6a7180' }}>
            {template.description}
          </p>
        )}

        {(categories.length > 0 || template.organisme) && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {categories.map((cat) => (
              <Badge key={cat.value} className={cat.color}>
                {cat.label}
              </Badge>
            ))}
            {template.organisme && (
              <Badge variant="outline" className="font-normal">
                {template.organisme}
              </Badge>
            )}
          </div>
        )}
      </div>

      <div
        className="flex items-center justify-between gap-2 border-t px-5 py-3"
        style={{ borderColor: C.border }}
      >
        <span className="text-[11px]" style={{ color: '#8E92A4' }}>
          {template.tailleFichier ? formatFileSize(template.tailleFichier) : template.nomFichier}
        </span>
        <div className="flex items-center gap-1.5">
          {template.sourceUrl && (
            <a
              href={template.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-[30px] w-[30px] items-center justify-center rounded-lg border transition-colors hover:bg-[#F8F7F4]"
              style={{ borderColor: C.border, color: '#6a7180' }}
              aria-label="Source officielle"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          <button
            type="button"
            onClick={() => templateService.download(template)}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold text-white transition-all hover:shadow-md"
            style={{ background: C.blue }}
          >
            <Download className="h-3.5 w-3.5" strokeWidth={2} />
            Télécharger
          </button>
        </div>
      </div>
    </div>
  );
}
