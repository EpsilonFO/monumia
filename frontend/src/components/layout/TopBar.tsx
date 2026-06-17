import { useState } from 'react';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet';
import { MobileNav } from './MobileNav';

export function TopBar() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 md:px-6 h-14 shrink-0 bg-white/60 backdrop-blur-xl border-b border-[#E0DDD6]/60">
      <div className="flex items-center gap-3">
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden h-8 w-8">
              <Menu className="h-4 w-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[220px] p-0">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <MobileNav onNavigate={() => setMobileNavOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
