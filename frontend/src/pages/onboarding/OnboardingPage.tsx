import { Outlet } from 'react-router';
import { Landmark } from 'lucide-react';

export function OnboardingPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="flex items-center gap-2 px-6 py-4 border-b">
        <Landmark className="h-6 w-6 text-primary" />
        <span className="text-lg font-bold tracking-tight">PatriAlta</span>
      </header>
      <main className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
