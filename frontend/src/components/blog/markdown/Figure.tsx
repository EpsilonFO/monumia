import type { ReactNode } from 'react';
import { C } from '@/lib/brand';

/* eslint-disable @typescript-eslint/no-explicit-any */
interface BlockProps {
  node?: any;
  children?: ReactNode;
}

export function Figure({ node, children }: BlockProps) {
  const caption = (node?.properties?.caption as string)?.trim() || '';
  return (
    <figure className="my-6 rounded-2xl border p-4 text-center" style={{ background: C.card, borderColor: C.border }}>
      <div className="[&_img]:mx-auto [&_img]:rounded-xl">{children}</div>
      {caption && (
        <figcaption className="mt-3 text-[15px] italic" style={{ color: '#6a7180' }}>
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
