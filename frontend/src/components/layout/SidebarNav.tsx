import type { ComponentType, ReactNode } from 'react';
import { NavLink } from 'react-router';
import { LogoMonumia } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';

export interface SidebarNavItem {
  to: string;
  icon: ComponentType<{ size?: number; className?: string }>;
  label: string;
  end?: boolean;
}

export interface SidebarSection {
  title?: string;
  items: SidebarNavItem[];
}

interface SidebarNavProps {
  brand: { name: string; tagline: string; href: string; logoSrc?: string };
  sections: SidebarSection[];
  account: ReactNode;
  onNavigate?: () => void;
}

export function SidebarNav({ brand, sections, account, onNavigate }: SidebarNavProps) {
  return (
    <div
      className="flex h-full flex-col"
      style={{ background: C.card, boxShadow: 'var(--shadow-nav)' }}
    >
      {/* En-tête de marque */}
      <a href={brand.href} className="flex items-center gap-2.5 px-5 pb-4 pt-5">
        {brand.logoSrc
          ? <img src={brand.logoSrc} alt="" className="h-8 w-8" aria-hidden />
          : <LogoMonumia className="h-8 w-8" />}
        <div className="leading-tight">
          <span className="block text-[18px] font-bold tracking-[-0.01em]" style={{ fontFamily: SERIF, color: C.ink }}>
            {brand.name}
          </span>
          <span className="block text-[10px] font-bold uppercase tracking-[0.15em]" style={{ color: C.orange }}>
            {brand.tagline}
          </span>
        </div>
      </a>

      {/* Sections de navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-2">
        {sections.map((section, si) => (
          <div key={section.title ?? si} className={si > 0 ? 'mt-5' : ''}>
            {section.title && (
              <p
                className="px-3 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.16em]"
                style={{ color: C.grayMuted }}
              >
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className="group relative flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-[14px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    style={({ isActive }) => ({
                      background: isActive ? C.paleBlue : 'transparent',
                      color: isActive ? C.blue : C.grayFg,
                    })}
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          aria-hidden
                          className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full transition-opacity"
                          style={{ background: C.orange, opacity: isActive ? 1 : 0 }}
                        />
                        <Icon size={20} className="shrink-0" />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Zone compte / aide */}
      <div className="mt-auto border-t px-3 py-3" style={{ borderColor: C.border }}>
        {account}
      </div>
    </div>
  );
}
