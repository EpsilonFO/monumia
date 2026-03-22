import { Navigate } from 'react-router';
import { useAuthStore } from '@/stores/useAuthStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** If set, only users with this segment can access. Others are redirected. */
  segment?: 'commune' | 'prive' | 'btp';
}

export function ProtectedRoute({ children, segment }: ProtectedRouteProps) {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);

  if (!user || !token) {
    return <Navigate to="/login" replace />;
  }

  if (segment && user.segment !== segment) {
    return <Navigate to={user.segment === 'btp' ? '/btp' : '/app'} replace />;
  }

  return <>{children}</>;
}
