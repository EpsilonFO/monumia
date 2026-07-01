import type { ReactNode } from 'react';

interface DocumentGridProps<T> {
  items: T[];
  keyOf: (item: T) => string;
  renderItem: (item: T) => ReactNode;
}

/**
 * Liste de documents en rangées pleine largeur empilées. Une rangée occupe
 * toujours toute la largeur : la page est remplie quel que soit le nombre de
 * documents (1, 2, 4 ou 40) — jamais de vide de grille.
 */
export function DocumentGrid<T>({ items, keyOf, renderItem }: DocumentGridProps<T>) {
  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => (
        <div key={keyOf(item)}>{renderItem(item)}</div>
      ))}
    </div>
  );
}
