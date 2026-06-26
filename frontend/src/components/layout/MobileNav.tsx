import { landingUrl } from '@/lib/session';
import { SidebarNav } from './SidebarNav';
import { ownerSections, OwnerAccount, useOwnerBrand } from './ownerNav';

interface MobileNavProps {
  onNavigate?: () => void;
}

export function MobileNav({ onNavigate }: MobileNavProps) {
  const { tagline } = useOwnerBrand();
  return (
    <SidebarNav
      brand={{ name: 'Monumia', tagline, href: landingUrl() }}
      sections={ownerSections}
      account={<OwnerAccount onNavigate={onNavigate} />}
      onNavigate={onNavigate}
    />
  );
}
