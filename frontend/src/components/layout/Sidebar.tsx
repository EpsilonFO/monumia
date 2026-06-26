import { landingUrl } from '@/lib/session';
import { SidebarNav } from './SidebarNav';
import { ownerSections, OwnerAccount, useOwnerBrand } from './ownerNav';

export function Sidebar() {
  const { tagline } = useOwnerBrand();
  return (
    <aside
      className="hidden shrink-0 md:flex md:w-[240px] md:flex-col"
      style={{ borderRight: '1px solid var(--color-border)' }}
    >
      <SidebarNav
        brand={{ name: 'Monumia', tagline, href: landingUrl() }}
        sections={ownerSections}
        account={<OwnerAccount />}
      />
    </aside>
  );
}
