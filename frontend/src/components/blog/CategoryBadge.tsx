import { Link } from 'react-router';

import type { BlogCategory } from '@/content/blog/categories';
import { cn } from '@/lib/utils';

interface CategoryBadgeProps {
  category: BlogCategory;
  asLink?: boolean;
}

export function CategoryBadge({ category, asLink = false }: CategoryBadgeProps) {
  const className = cn(
    'inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
    category.accentClass,
  );
  if (asLink) {
    return (
      <Link to={`/blog/categorie/${category.slug}`} className={className}>
        {category.label}
      </Link>
    );
  }
  return <span className={className}>{category.label}</span>;
}
