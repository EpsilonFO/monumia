import type { ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { Trans, useTranslation } from 'react-i18next';
import { IconMonument, IconProtection, IconTemps, LogoMonumia } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';
import { SelecteurLangue } from '@/i18n/SelecteurLangue';

interface AuthLayoutProps {
  /** Contenu de la colonne droite (formulaire, titres…). */
  children: ReactNode;
  /** Titre du panneau bleu (défaut : accroche produit). */
  panelHeadline?: ReactNode;
  /** Paragraphe sous le titre (défaut : pitch produit). */
  panelDescription?: ReactNode;
  /** Libellé orange en petites capitales, au-dessus du titre du panneau
   *  (défaut : « Votre espace patrimoine »). */
  panelEyebrow?: string;
  /** Largeur max et espacement vertical de la colonne droite
   *  (défaut : max-w-md space-y-8). */
  contentClassName?: string;
}

// Les libellés sont des clés `shell:AuthLayout.reassurance.*`, traduites au rendu.
const REASSURANCE = [
  { icon: IconMonument, cle: 'aides' },
  { icon: IconProtection, cle: 'donnees' },
  { icon: IconTemps, cle: 'instantane' },
] as const;

/**
 * Coquille du parcours d'authentification, calquée sur l'identité du tableau de
 * bord : un panneau bleu profond (couleur de la sidebar) accueille dès le premier
 * écran, et la colonne de droite est l'atelier crème de l'application.
 *
 * Le panneau bleu est collant et tenu à la hauteur du viewport (`self-start`
 * l'empêche d'être étiré par la colonne droite). Sans cela, un formulaire plus
 * haut que l'écran — l'onglet Inscription — grandit le conteneur, et le
 * `justify-between` du panneau fait descendre l'accroche d'un onglet à l'autre.
 */
export function AuthLayout({
  children,
  panelHeadline,
  panelDescription,
  panelEyebrow,
  contentClassName = 'max-w-md space-y-8',
}: AuthLayoutProps) {
  const { t } = useTranslation('shell');
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex" style={{ background: C.cream }}>
      {/* ═══════ GAUCHE — panneau bleu (esprit sidebar) ═══════ */}
      <div
        className="relative hidden lg:flex lg:sticky lg:top-0 lg:h-screen lg:self-start lg:w-[44%] xl:w-[40%] flex-col justify-between overflow-hidden p-12 xl:p-16"
        style={{ background: C.blue }}
      >
        {/* Atmosphère : halos diffus (repris du héros du dashboard) */}
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          <div className="absolute -right-20 -top-24 h-80 w-80 rounded-full blur-[148px]" style={{ background: 'rgba(92,149,255,0.40)' }} />
          <div className="absolute -bottom-28 -left-16 h-72 w-72 rounded-full blur-[148px]" style={{ background: 'rgba(241,113,5,0.18)' }} />
        </div>

        {/* Logo */}
        <div className="relative z-10">
          <button onClick={() => navigate('/')} className="group flex items-center gap-2.5">
            <LogoMonumia className="h-8 w-8" label="Monumia" />
            <div className="text-left">
              <span className="block text-[22px] font-bold leading-none tracking-[-0.01em]" style={{ fontFamily: SERIF, color: C.cream }}>
                Monumia
              </span>
              <span className="mt-1 block text-[12px] font-bold uppercase tracking-[0.18em]" style={{ color: C.orange }}>
                {panelEyebrow ?? t('AuthLayout.surtitre')}
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
              <Trans
                t={t}
                i18nKey="AuthLayout.accroche"
                components={{ br: <br />, orange: <span style={{ color: C.orange }} /> }}
              />
            )}
          </h2>
          <p className="max-w-sm text-[17px] leading-[1.7]" style={{ color: C.blueLight }}>
            {panelDescription ?? t('AuthLayout.pitch')}
          </p>
        </div>

        {/* Réassurance */}
        <div className="relative z-10 flex flex-col gap-3.5">
          {REASSURANCE.map(({ icon: Icon, cle }) => (
            <div key={cle} className="flex items-center gap-3 text-[15px] font-medium" style={{ color: C.cream }}>
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                style={{ background: 'rgba(255,255,255,0.08)', color: C.orange }}
              >
                <Icon className="h-[17px] w-[17px]" strokeWidth={1.9} aria-hidden />
              </span>
              {t(`AuthLayout.reassurance.${cle}`)}
            </div>
          ))}
        </div>
      </div>

      {/* ═══════ DROITE — atelier crème ═══════ */}
      <div className="flex flex-1 flex-col">
        {/* Barre mobile */}
        <div className="flex items-center justify-between px-6 py-5 lg:hidden" style={{ borderBottom: `1px solid ${C.border}` }}>
          <button onClick={() => navigate('/')} className="flex items-center gap-2">
            <LogoMonumia className="h-7 w-7" label="Monumia" />
            <span className="text-[18px] font-bold" style={{ fontFamily: SERIF, color: C.ink }}>Monumia</span>
          </button>
          <SelecteurLangue className="text-[14px]" />
        </div>
        {/* En bureau, la langue se pose seule en haut de la colonne : la barre
            mobile, qui la porte sur téléphone, y est masquée. */}
        <div className="hidden justify-end px-8 pt-6 lg:flex">
          <SelecteurLangue className="text-[14px]" />
        </div>

        <div className="flex flex-1 items-center justify-center px-6 py-8">
          <div className={`w-full ${contentClassName}`}>{children}</div>
        </div>
      </div>
    </div>
  );
}

/** Surtitre éditorial réutilisable : tiret orange + petites capitales bleues (motif du dashboard). */
export function AuthEyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2.5 text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.blue }}>
      <span aria-hidden style={{ width: 25, height: 2, borderRadius: 2, background: C.orange }} />
      {children}
    </span>
  );
}
