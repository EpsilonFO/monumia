import { Bell, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet';
import { MobileNav } from './MobileNav';

interface TopBarProps {
  unreadCount?: number;
  onNotificationsClick?: () => void;
}

export function TopBar({ unreadCount = 0, onNotificationsClick }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 md:px-6 h-14 shrink-0 bg-white/60 backdrop-blur-xl border-b border-[#E0DDD6]/60">
      <div className="flex items-center gap-3">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden h-8 w-8">
              <Menu className="h-4 w-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[220px] p-0">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <MobileNav />
          </SheetContent>
        </Sheet>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onNotificationsClick}
          className="relative flex items-center justify-center h-9 w-9 rounded-full border border-[#E0DDD6] bg-white transition-all duration-200 hover:shadow-sm hover:border-[#C75B3A]/20"
        >
          <Bell className="h-4 w-4 text-[#5C6178]" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-4 min-w-4 flex items-center justify-center px-1 rounded-full bg-[#C75B3A] text-white text-[9px] font-bold">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
