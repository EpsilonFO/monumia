import { C } from '@/lib/brand';

interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DonutSlice[];
  size?: number;
}

export function DonutChart({ data, size = 168 }: DonutChartProps) {
  const total = data.reduce((acc, d) => acc + d.value, 0);
  const stroke = Math.round(size * 0.16);
  const radius = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;

  if (total === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-full text-[14px]"
        style={{ width: size, height: size, color: C.ink, opacity: 0.5 }}
        role="img"
        aria-label="Aucune donnée à afficher"
      >
        Aucune donnée
      </div>
    );
  }

  const segments = data
    .filter((d) => d.value > 0)
    .reduce<
      {
        list: Array<{
          label: string;
          value: number;
          color: string;
          dashArray: string;
          dashOffset: number;
          percent: number;
        }>;
        cumOffset: number;
      }
    >(
      ({ list, cumOffset }, d) => {
        const fraction = d.value / total;
        const dash = fraction * circumference;
        list.push({
          ...d,
          dashArray: `${dash} ${circumference - dash}`,
          dashOffset: -cumOffset,
          percent: Math.round(fraction * 100),
        });
        return { list, cumOffset: cumOffset + dash };
      },
      { list: [], cumOffset: 0 }
    ).list;

  const aria = data
    .filter((d) => d.value > 0)
    .map((d) => `${d.label} : ${d.value} (${Math.round((d.value / total) * 100)}%)`)
    .join(', ');

  return (
    <div className="@container">
      <div className="flex flex-col items-center gap-4 @md:flex-row @md:items-center @md:gap-6">
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          <svg
            width={size}
            height={size}
            viewBox={`0 0 ${size} ${size}`}
            role="img"
            aria-label={`Répartition : ${aria}`}
          >
            <circle
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke={C.paleBlue}
              strokeWidth={stroke}
            />
            {segments.map((s) => (
              <circle
                key={s.label}
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke={s.color}
                strokeWidth={stroke}
                strokeDasharray={s.dashArray}
                strokeDashoffset={s.dashOffset}
                transform={`rotate(-90 ${cx} ${cy})`}
                strokeLinecap="butt"
              />
            ))}
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span
              className="text-[30px] font-bold leading-none"
              style={{ fontFamily: 'var(--font-serif)', color: C.blue }}
            >
              {total}
            </span>
            <span className="mt-1 text-[12px] uppercase tracking-[0.12em]" style={{ color: C.ink, opacity: 0.5 }}>
              total
            </span>
          </div>
        </div>

        <ul className="flex w-full min-w-0 flex-col gap-1.5 @md:flex-1">
          {segments.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-[14px]">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate" style={{ color: C.ink }}>
                {s.label}
              </span>
              <span className="font-semibold tabular-nums" style={{ color: C.blue }}>
                {s.value}
              </span>
              <span className="w-9 text-right tabular-nums" style={{ color: C.ink, opacity: 0.5 }}>
                {s.percent}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
