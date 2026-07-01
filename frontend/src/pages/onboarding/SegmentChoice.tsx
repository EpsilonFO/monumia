import { useNavigate } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { IconMonument, IconMaison, IconEquipe } from '@/components/icons';
import { AuthEyebrow } from '@/components/layout/AuthLayout';
import { C, SERIF } from '@/lib/brand';

const MUTED = 'var(--muted-foreground)';

export function SegmentChoice() {
  const navigate = useNavigate();

  const segments = [
    {
      key: 'commune',
      icon: IconMonument,
      title: 'Je suis une commune',
      desc: 'Maire, adjoint au patrimoine, secrétaire de mairie… Gérez les monuments de votre collectivité.',
      tint: C.paleBlue,
      accent: C.blue,
      path: '/onboarding/profil?segment=commune',
    },
    {
      key: 'prive',
      icon: IconMaison,
      title: 'Je suis propriétaire privé',
      desc: 'Château, manoir, demeure historique… Trouvez les aides disponibles pour votre bien.',
      tint: C.paleOrange,
      accent: C.orange,
      path: '/onboarding/profil?segment=prive',
    },
    {
      key: 'collaborateur',
      icon: IconEquipe,
      title: 'Je rejoins un projet',
      desc: 'On m’a invité à collaborer. Maire, artisan, architecte… rejoignez le projet d’une autre personne.',
      tint: C.paleBlue,
      accent: C.blueLight,
      path: '/onboarding/profil?segment=collaborateur',
    },
  ];

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <AuthEyebrow>Étape 1 — Votre profil</AuthEyebrow>
        <h1 className="text-[clamp(1.7rem,4vw,2.4rem)] leading-[1.1]" style={{ fontFamily: SERIF, color: C.ink }}>
          Qui <span style={{ color: C.blue }}>êtes-vous</span> ?
        </h1>
        <p className="max-w-lg text-[15px] leading-[1.7]" style={{ color: MUTED }}>
          Indiquez votre situation pour adapter votre espace et les aides proposées.
        </p>
      </div>

      <div className="space-y-3.5">
        {segments.map((seg) => (
          <button
            key={seg.key}
            onClick={() => navigate(seg.path)}
            className="group flex w-full items-center gap-5 rounded-2xl border px-6 py-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_10px_30px_-12px_rgba(10,54,157,0.25)]"
            style={{ background: C.card, borderColor: C.border }}
          >
            <span
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-105"
              style={{ background: seg.tint, color: seg.accent }}
            >
              <seg.icon className="h-6 w-6" strokeWidth={1.8} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
                {seg.title}
              </span>
              <span className="mt-1 block text-[13px] leading-[1.55]" style={{ color: MUTED }}>
                {seg.desc}
              </span>
            </span>
            <ArrowRight
              className="h-5 w-5 shrink-0 transition-transform duration-300 group-hover:translate-x-1"
              style={{ color: seg.accent }}
            />
          </button>
        ))}
      </div>
    </div>
  );
}
