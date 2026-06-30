import { Link } from 'react-router';
import { IconAttention, IconDiagnostic, IconInfo, IconNotification } from '@/components/icons';
import { cn } from '@/lib/utils';
import { formatRelative } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import type { Notification } from '@/types';

interface NotificationItemProps {
  notification: Notification;
  onRead?: (id: string) => void;
}

const typeIcons = {
  urgent: IconAttention,
  opportunite: IconDiagnostic,
  info: IconInfo,
};

const typeColors = {
  urgent: 'text-destructive',
  opportunite: 'text-warning',
  info: 'text-info',
};

function getLink(n: Notification): string | undefined {
  if (!n.lienVers) return undefined;
  switch (n.lienVers.type) {
    case 'aide': return ROUTES.AIDE_DETAIL(n.lienVers.id);
    case 'dossier': return ROUTES.DOSSIER_DETAIL(n.lienVers.id);
    case 'monument': return ROUTES.MONUMENT_DETAIL(n.lienVers.id);
    default: return undefined;
  }
}

export function NotificationItem({ notification, onRead }: NotificationItemProps) {
  const Icon = typeIcons[notification.type] ?? IconNotification;
  const link = getLink(notification);

  const content = (
    <div
      className={cn(
        'flex items-start gap-3 p-3 rounded-lg transition-colors',
        !notification.lue && 'bg-primary/5',
        link && 'hover:bg-muted/50 cursor-pointer',
      )}
      onClick={() => {
        if (!notification.lue && onRead) onRead(notification.id);
      }}
    >
      <div className={cn('mt-0.5 shrink-0', typeColors[notification.type])}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0 space-y-0.5">
        <div className="flex items-center gap-2">
          <p className={cn('text-sm leading-tight', !notification.lue && 'font-medium')}>
            {notification.titre}
          </p>
          {!notification.lue && (
            <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
          )}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2">
          {notification.message}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatRelative(notification.dateCreation)}
        </p>
      </div>
    </div>
  );

  if (link) {
    return <Link to={link}>{content}</Link>;
  }

  return content;
}
