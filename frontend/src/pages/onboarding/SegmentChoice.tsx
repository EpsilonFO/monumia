import { useNavigate } from 'react-router';
import { Building2, Home, ArrowRight } from 'lucide-react';

const C = {
  text: '#1B1E2E',
  textMuted: '#5C6178',
  textLight: '#8E92A4',
  royal: '#1A237E',
  royalPale: '#E8EAF6',
  terra: '#C75B3A',
  terraPale: '#FBF0EC',
  border: '#E4E2DC',
  bgAlt: '#FFFFFF',
} as const;

export function SegmentChoice() {
  const navigate = useNavigate();

  const segments = [
    {
      key: 'commune',
      icon: Building2,
      title: 'Je suis une commune',
      desc: 'Maire, adjoint au patrimoine, secrétaire de mairie… Gérez les monuments de votre collectivité.',
      tint: C.royalPale,
      accent: C.royal,
      path: '/onboarding/profil?segment=commune',
    },
    {
      key: 'prive',
      icon: Home,
      title: 'Je suis propriétaire privé',
      desc: 'Propriétaire d\'un château, manoir, demeure historique… Trouvez les aides pour votre bien.',
      tint: C.terraPale,
      accent: C.terra,
      path: '/onboarding/profil?segment=prive',
    },
  ];

  return (
    <div className="space-y-10">
      {/* heading */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="h-px w-12" style={{ background: C.terra }} />
          <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>
            Étape 1
          </span>
        </div>
        <h1
          className="text-[clamp(1.8rem,4vw,2.8rem)] font-light tracking-[-0.02em]"
          style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
        >
          Bienvenue sur <em className="italic" style={{ color: C.royal }}>PatriAlta</em>
        </h1>
        <p className="max-w-lg text-[16px] leading-[1.75]" style={{ color: C.textMuted }}>
          Identifiez les aides disponibles pour restaurer votre patrimoine historique.
          Commencez par nous indiquer votre situation.
        </p>
      </div>

      {/* segment cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {segments.map((seg) => (
          <button
            key={seg.key}
            onClick={() => navigate(seg.path)}
            className="group relative flex flex-col items-start text-left p-8 border transition-all duration-500 hover:shadow-lg hover:shadow-black/[0.04]"
            style={{ borderColor: C.border, background: C.bgAlt }}
          >
            {/* icon */}
            <div
              className="flex h-14 w-14 items-center justify-center rounded-full mb-6 transition-all duration-500 group-hover:scale-105"
              style={{ background: seg.tint, color: seg.accent }}
            >
              <seg.icon className="h-6 w-6" />
            </div>

            <h3
              className="text-[22px] font-normal mb-3"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
            >
              {seg.title}
            </h3>
            <p className="flex-1 text-[15px] leading-[1.75] mb-6" style={{ color: C.textMuted }}>
              {seg.desc}
            </p>

            <div
              className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.08em] transition-colors duration-300"
              style={{ color: seg.accent }}
            >
              Continuer
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" />
            </div>

            {/* hover accent line */}
            <div
              className="absolute bottom-0 left-8 right-8 h-[2px] scale-x-0 group-hover:scale-x-100 transition-transform duration-700 origin-left"
              style={{ background: seg.accent }}
            />
          </button>
        ))}
      </div>
    </div>
  );
}
