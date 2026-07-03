import type { ReactNode, ComponentType } from 'react';
import { IconInfo, IconConseil, IconDocument, IconAttention } from '@/components/icons';
import { C } from '@/lib/brand';

/* eslint-disable @typescript-eslint/no-explicit-any */
interface BlockProps {
  node?: any;
  children?: ReactNode;
}

type Variant = 'remarque' | 'attention' | 'astuce' | 'exemple';

const TONE: Record<
  Variant,
  { label: string; fg: string; tint: string; node: string; Icon: ComponentType<{ size?: number; className?: string }> }
> = {
  remarque: { label: 'Remarque', fg: C.blue, tint: C.paleBlue, node: C.blueLight, Icon: IconInfo },
  attention: { label: 'Attention', fg: C.danger, tint: C.paleDanger, node: C.danger, Icon: IconAttention },
  astuce: { label: 'Astuce', fg: C.orange, tint: C.paleOrange, node: C.orange, Icon: IconConseil },
  exemple: { label: 'Exemple', fg: C.ink, tint: '#f3eee1', node: C.blueDark, Icon: IconDocument },
};

export function Callout({ node, children }: BlockProps) {
  const variant = (node?.properties?.variant as Variant) ?? 'remarque';
  const t = TONE[variant] ?? TONE.remarque;
  const title = (node?.properties?.title as string)?.trim() || t.label;
  const { Icon } = t;
  return (
    <aside className="relative my-6 overflow-hidden rounded-2xl border" style={{ background: C.card, borderColor: C.border }}>
      <span className="absolute inset-y-0 left-0 w-1.5" style={{ background: t.node }} aria-hidden />
      <div className="flex gap-3.5 px-5 py-4 pl-6">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: t.tint, color: t.fg }}>
          <Icon className="h-[18px] w-[18px]" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: t.fg }}>
            {title}
          </p>
          <div
            className="mt-1.5 text-[14.5px] leading-relaxed [&_a]:font-medium [&_a]:text-[#f17105] [&_a]:underline [&_p]:mt-2 [&_p:first-child]:mt-0 [&_strong]:font-semibold [&_strong]:text-[#222b35] [&_ul]:mt-2 [&_ul]:list-disc [&_ul]:pl-5"
            style={{ color: C.ink }}
          >
            {children}
          </div>
        </div>
      </div>
    </aside>
  );
}
