import { Link } from 'react-router';

import { type BlogCategory, categoryTone } from '@/content/blog/categories';

interface CategoryBadgeProps {
  category: BlogCategory;
  asLink?: boolean;
}

export function CategoryBadge({ category, asLink = false }: CategoryBadgeProps) {
  const tone = categoryTone(category);
  const Icon = category.icon;
  const className =
    'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-semibold uppercase tracking-wide';
  const style = { background: tone.soft, color: tone.fg };
  const content = (
    <>
      <Icon className="h-3.5 w-3.5" />
      {category.shortLabel}
    </>
  );
  if (asLink) {
    return (
      <Link to={`/blog/categorie/${category.slug}`} className={className} style={style}>
        {content}
      </Link>
    );
  }
  return (
    <span className={className} style={style}>
      {content}
    </span>
  );
}
