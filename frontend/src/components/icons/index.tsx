import type { ReactNode, SVGProps } from 'react';

type IconProps = Omit<SVGProps<SVGSVGElement>, 'strokeWidth'> & {
  size?: number;
  strokeWidth?: number;
};

type IconBaseProps = IconProps & { children: ReactNode };

function IconBase({ size = 20, strokeWidth = 1.75, children, ...props }: IconBaseProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export function IconDashboard(p: IconProps) {
  return (
    <IconBase {...p}>
      <rect x="3" y="3" width="7" height="9" rx="2" />
      <rect x="14" y="3" width="7" height="5" rx="2" />
      <rect x="14" y="12" width="7" height="9" rx="2" />
      <rect x="3" y="16" width="7" height="5" rx="2" />
    </IconBase>
  );
}

export function IconMonument(p: IconProps) {
  return (
    <IconBase {...p}>
      <path d="M4 9 L12 4 L20 9" />
      <path d="M5.5 9 v9 M10 9 v9 M14 9 v9 M18.5 9 v9" />
      <path d="M3.5 18 h17 M3 21 h18" />
    </IconBase>
  );
}

export function IconDocuments(p: IconProps) {
  return (
    <IconBase {...p}>
      <path d="M8 3 h6 l4 4 v11 a2 2 0 0 1 -2 2 H8 a2 2 0 0 1 -2 -2 V5 a2 2 0 0 1 2 -2 Z" />
      <path d="M14 3 v4 h4" />
      <path d="M9.5 12.5 h5 M9.5 15.5 h5" />
    </IconBase>
  );
}

export function IconAgenda(p: IconProps) {
  return (
    <IconBase {...p}>
      <rect x="3.5" y="5" width="17" height="16" rx="2.5" />
      <path d="M3.5 9.5 h17 M8 3 v4 M16 3 v4" />
      <circle cx="12" cy="15" r="1.5" fill="currentColor" stroke="none" />
    </IconBase>
  );
}

export function IconAide(p: IconProps) {
  return (
    <IconBase {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M14.6 9.4 a3.4 3.4 0 0 0 -5.1 1.1 M8.7 12 h5 M8.7 13.8 h5 M14.4 15 a3.4 3.4 0 0 1 -4.9 -0.9" />
    </IconBase>
  );
}

export function IconDossier(p: IconProps) {
  return (
    <IconBase {...p}>
      <path d="M3 7 a2 2 0 0 1 2 -2 h4 l2 2 h8 a2 2 0 0 1 2 2 v8 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 Z" />
    </IconBase>
  );
}

export function IconDepot(p: IconProps) {
  return (
    <IconBase {...p}>
      <path d="M12 15 V4 M8 8 l4 -4 l4 4" />
      <path d="M4 14 v3 a2 2 0 0 0 2 2 h12 a2 2 0 0 0 2 -2 v-3" />
    </IconBase>
  );
}

export function IconSuivi(p: IconProps) {
  return (
    <IconBase {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.5 12.5 l2.5 2.5 l4.5 -5" />
    </IconBase>
  );
}

export function IconHelp(p: IconProps) {
  return (
    <IconBase {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.6 9.6 a2.4 2.4 0 0 1 4.3 1.4 c0 1.6 -1.9 1.8 -1.9 3.2" />
      <circle cx="12" cy="17" r="0.7" fill="currentColor" stroke="none" />
    </IconBase>
  );
}

export function IconAccount(p: IconProps) {
  return (
    <IconBase {...p}>
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M5.5 19 a6.5 6.5 0 0 1 13 0" />
    </IconBase>
  );
}
