import { useTranslation } from 'react-i18next';
import { C } from '@/lib/brand';

interface ProgressRingProps {
  value: number;
  size?: number;
  color?: string;
  label?: string;
}

export function ProgressRing({ value, size = 56, color = C.blue, label }: ProgressRingProps) {
  const { t } = useTranslation('dashboard');
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const stroke = Math.max(4, Math.round(size * 0.1));
  const radius = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;

  return (
    <div
      className="relative inline-flex shrink-0 items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={
        label
          ? t('ProgressRing.libelle', { libelle: label, pct: clamped })
          : t('ProgressRing.progression', { pct: clamped })
      }
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={C.paleBlue}
          strokeWidth={stroke}
        />
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          transform={`rotate(-90 ${cx} ${cy})`}
          className="transition-all duration-500"
        />
      </svg>
      <span
        className="absolute font-semibold tabular-nums"
        style={{
          fontFamily: 'var(--font-serif)',
          color,
          fontSize: Math.round(size * 0.26),
        }}
      >
        {clamped}%
      </span>
    </div>
  );
}
