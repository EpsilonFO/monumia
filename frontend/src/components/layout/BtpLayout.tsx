import { useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Menu, LogOut } from 'lucide-react';
import { BtpSidebar } from './BtpSidebar';
import { useAuthStore } from '@/stores/useAuthStore';

function BtpMobileNav() {
  return (
    <div className="flex flex-col h-full">
      <BtpSidebar />
    </div>
  );
}

export function BtpLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) {
      navigate('/login');
    } else if (user.segment !== 'btp') {
      navigate('/');
    }
  }, [user, navigate]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <BtpSidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* TopBar */}
        <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-4 md:px-6 bg-background border-b border-border">
          <div className="flex items-center gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0">
                <SheetTitle className="sr-only">Navigation BTP</SheetTitle>
                <BtpMobileNav />
              </SheetContent>
            </Sheet>
            {user?.btp && (
              <span className="text-sm font-medium text-muted-foreground hidden md:block">
                {user.btp.raisonSociale}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={handleLogout} title="Changer de profil">
              <LogOut className="h-5 w-5" />
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
