import type { ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { IconMonument, IconProtection, IconTemps } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';

interface AuthLayoutProps {
  /** Contenu de la colonne droite (formulaire, titres…). */
  children: ReactNode;
  /** Titre du panneau bleu (défaut : accroche produit). */
  panelHeadline?: ReactNode;
  /** Paragraphe sous le titre (défaut : pitch produit). */
  panelDescription?: ReactNode;
  /** Libellé orange en petites capitales, au-dessus du titre du panneau. */
  panelEyebrow?: string;
  /** Largeur max de la colonne droite (défaut : max-w-md). */
  contentClassName?: string;
}

const REASSURANCE = [
  { icon: IconMonument, label: '150+ aides référencées' },
  { icon: IconProtection, label: 'Vos données sécurisées' },
  { icon: IconTemps, label: 'Résultat instantané' },
];

/**
 * Coquille du parcours d'authentification, calquée sur l'identité du tableau de
 * bord : un panneau bleu profond (couleur de la sidebar) accueille dès le premier
 * écran, et la colonne de droite est l'atelier crème de l'application.
 */
export function AuthLayout({
  children,
  panelHeadline,
  panelDescription,
  panelEyebrow = 'Votre espace patrimoine',
  contentClassName = 'max-w-md',
}: AuthLayoutProps) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex" style={{ background: C.cream }}>
      {/* ═══════ GAUCHE — panneau bleu (esprit sidebar) ═══════ */}
      <div
        className="relative hidden lg:flex lg:w-[44%] xl:w-[40%] flex-col justify-between overflow-hidden p-12 xl:p-16"
        style={{ background: C.blue }}
      >
        {/* Atmosphère : halos diffus + fines règles horizontales (repris du héros du dashboard) */}
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          <div className="absolute -right-20 -top-24 h-80 w-80 rounded-full blur-[130px]" style={{ background: 'rgba(92,149,255,0.40)' }} />
          <div className="absolute -bottom-28 -left-16 h-72 w-72 rounded-full blur-[130px]" style={{ background: 'rgba(241,113,5,0.18)' }} />
          <div
            className="absolute inset-0 opacity-[0.05]"
            style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 31px, var(--card) 31px, var(--card) 32px)' }}
          />
        </div>

        {/* Logo */}
        <div className="relative z-10">
          <button onClick={() => navigate('/')} className="group flex items-center gap-2.5">
            <img src="/monumia.png" alt="Monumia" className="h-8 w-8" />
            <div className="text-left">
              <span className="block text-[19px] font-bold leading-none tracking-[-0.01em]" style={{ fontFamily: SERIF, color: C.cream }}>
                Monumia
              </span>
              <span className="mt-1 block text-[10px] font-bold uppercase tracking-[0.18em]" style={{ color: C.orange }}>
                {panelEyebrow}
              </span>
            </div>
          </button>
          {/* Filet dégradé — signature de la sidebar */}
          <div
            className="mt-6 h-px w-40"
            style={{ background: `linear-gradient(to right, color-mix(in srgb, var(--accent) 60%, transparent), ${C.blueDark}, transparent)` }}
          />
        </div>

        {/* Accroche */}
        <div className="relative z-10 space-y-6">
          <h2 className="text-[clamp(2rem,3.2vw,2.9rem)] leading-[1.12] tracking-[-0.01em]" style={{ fontFamily: SERIF, color: C.cream }}>
            {panelHeadline ?? (
              <>
                Financez la restauration<br />
                de votre <span style={{ color: C.orange }}>patrimoine</span>
              </>
            )}
          </h2>
          <p className="max-w-sm text-[15px] leading-[1.7]" style={{ color: C.blueLight }}>
            {panelDescription ?? 'Identifiez les subventions, déductions fiscales et dispositifs de mécénat disponibles pour vos monuments historiques.'}
          </p>
        </div>

        {/* Réassurance */}
        <div className="relative z-10 flex flex-col gap-3.5">
          {REASSURANCE.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-3 text-[13px] font-medium" style={{ color: C.cream }}>
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                style={{ background: 'rgba(255,255,255,0.08)', color: C.orange }}
              >
                <Icon className="h-[15px] w-[15px]" strokeWidth={1.9} aria-hidden />
              </span>
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* ═══════ DROITE — atelier crème ═══════ */}
      <div className="flex flex-1 flex-col">
        {/* Barre mobile */}
        <div className="flex items-center justify-between px-6 py-5 lg:hidden" style={{ borderBottom: `1px solid ${C.border}` }}>
          <button onClick={() => navigate('/')} className="flex items-center gap-2">
            <img src="/monumia.png" alt="Monumia" className="h-7 w-7" />
            <span className="text-[16px] font-bold" style={{ fontFamily: SERIF, color: C.ink }}>Monumia</span>
          </button>
        </div>

        <div className="flex flex-1 items-center justify-center px-6 py-12">
          <div className={`w-full ${contentClassName} space-y-8`}>{children}</div>
        </div>
      </div>
    </div>
  );
}

/** Surtitre éditorial réutilisable : tiret orange + petites capitales bleues (motif du dashboard). */
export function AuthEyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2.5 text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.blue }}>
      <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
      {children}
    </span>
  );
}
