import type { ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkDirective from 'remark-directive';

import remarkMonumiaDirectives from './remarkMonumiaDirectives';
import { slugify } from './slugify';
import { Callout } from './Callout';
import { Figure } from './Figure';
import { KeyFigures } from './KeyFigures';
import { BarChart } from './BarChart';
import { Comparison } from './Comparison';
import { Steps } from './Steps';
import { Timeline } from './Timeline';
import { DecisionTree } from './DecisionTree';
import { Quote } from './Quote';
import { Checklist } from './Checklist';
import { CostBreakdown } from './CostBreakdown';
import { PullStat } from './PullStat';

// Classes de style du corps Markdown — charte Monumia (PT Serif via font-serif, palette C).
const MARKDOWN_CLASS =
  'text-[17.5px] leading-[1.75] text-[#222b35] ' +
  // Premier paragraphe (l'accroche) = cadre « problématique » qui se détache.
  '[&>p:first-child]:mt-0 [&>p:first-child]:rounded-xl [&>p:first-child]:border [&>p:first-child]:border-[#ece3d2] [&>p:first-child]:bg-[#fffefb] [&>p:first-child]:px-5 [&>p:first-child]:py-4 [&>p:first-child]:shadow-[inset_3px_0_0_0_#f17105] [&>p:first-child]:text-[18.5px] [&>p:first-child]:leading-[1.72] [&>p:first-child]:text-[#222b35] ' +
  '[&_h2]:mt-10 [&_h2]:scroll-mt-24 [&_h2]:font-serif [&_h2]:text-[27px] [&_h2]:font-normal [&_h2]:text-[#222b35] ' +
  '[&_h3]:mt-7 [&_h3]:scroll-mt-24 [&_h3]:font-serif [&_h3]:text-[20.5px] [&_h3]:font-semibold [&_h3]:text-[#222b35] ' +
  '[&_p]:mt-4 [&_ul]:mt-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mt-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mt-1.5 ' +
  '[&_a]:font-medium [&_a]:text-[#f17105] [&_a]:underline hover:[&_a]:no-underline [&_strong]:font-semibold [&_strong]:text-[#222b35] ' +
  '[&_blockquote]:mt-4 [&_blockquote]:border-l-2 [&_blockquote]:border-[#f17105] [&_blockquote]:bg-[#fdf9f0] [&_blockquote]:px-4 [&_blockquote]:py-2 [&_blockquote]:italic [&_blockquote]:text-[#6a7180]';

/** Texte brut d'un arbre de nœuds React (pour les ancres de titres). */
function textOf(node: ReactNode): string {
  if (node == null || node === false || node === true) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const props = (node as any)?.props;
  return props ? textOf(props.children) : '';
}

const components = {
  h2: ({ children }: { children?: ReactNode }) => (
    <h2 id={slugify(textOf(children))}>{children}</h2>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 id={slugify(textOf(children))}>{children}</h3>
  ),
  'mon-callout': Callout,
  'mon-figure': Figure,
  'mon-keyfigures': KeyFigures,
  'mon-barchart': BarChart,
  'mon-comparison': Comparison,
  'mon-steps': Steps,
  'mon-timeline': Timeline,
  'mon-decision': DecisionTree,
  'mon-quote': Quote,
  'mon-checklist': Checklist,
  'mon-cost': CostBreakdown,
  'mon-pullstat': PullStat,
} as unknown as Components;

export function MarkdownArticle({ body }: { body: string }) {
  return (
    <div className={MARKDOWN_CLASS}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkDirective, remarkMonumiaDirectives]}
        components={components}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
