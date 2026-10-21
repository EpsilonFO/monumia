import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import {
  ArrowRight,
  Bell,
  BellRing,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronDown,
  Download,
  FileText,
  FolderOpen,
  HeartHandshake,
  Info,
  Lock,
  Mail,
  Search,
  Sparkles,
} from 'lucide-react';
import type { TFunction } from 'i18next';
import { Trans, useTranslation } from 'react-i18next';
import { changerLangue, LANGUES, langueCourante, localeIntl } from './i18n';
import { sessionActive } from './session';

const APP_URL = import.meta.env.VITE_APP_URL || 'https://app.monumia.fr';

// Préfixe des assets de public/ : '/' en prod, '/landing/' en beta.
// import.meta.env.BASE_URL finit toujours par '/' (garanti par Vite).
const BASE = import.meta.env.BASE_URL;

/* ────────────────────────────────────────────
   Charte Monumia — couleurs
   ──────────────────────────────────────────── */

export const C = {
  blue:       '#0a369d',   // bleu profond — institutionnel, confiance
  blueLight:  '#5c95ff',   // bleu clair — liens, infographies, soutien
  orange:     '#f17105',   // orange — action, signature
  orangeVif:  '#fc8905',   // orange vif — accentuation, parcimonie
  cream:      '#fdf9f0',   // crème — fond par excellence
  ink:        '#222b35',   // noir bleuté — corps de texte
  inkSoft:    'rgba(34, 43, 53, 0.74)',
  inkFaint:   'rgba(34, 43, 53, 0.52)',
  card:       '#fffefb',   // carte, à peine plus claire que le crème
  border:     '#ece3d2',   // bordure chaude
  paleBlue:   '#eef3ff',   // teinte du bleu clair
  paleOrange: '#feeedd',   // teinte de l’orange
} as const;

/* La fleur Monumia (public/logo.svg) servie en masque CSS : la couleur se
   pilote par `color` (currentColor), comme un glyphe vectoriel recolorable. */
const LOGO_URL = `url(${BASE}logo.svg)`;

/* ────────────────────────────────────────────
   Briques graphiques
   ──────────────────────────────────────────── */

export function Clover({
  className = '',
  style,
}: {
  className?: string;
  style?: CSSProperties;
  /* Conservés pour compat avec les appels existants, sans effet sur la fleur. */
  strokeWidth?: number;
  filled?: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className={className}
      style={{
        display: 'inline-block',
        backgroundColor: 'currentColor',
        WebkitMaskImage: LOGO_URL,
        maskImage: LOGO_URL,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
        ...style,
      }}
    />
  );
}

function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function useInView(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

function Reveal({
  children,
  className = '',
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const { ref, inView } = useInView(0.08);
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (inView) {
      const t = setTimeout(() => setShow(true), delay);
      return () => clearTimeout(t);
    }
  }, [inView, delay]);
  return (
    <div
      ref={ref}
      className={`transition-all duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] ${
        show ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
      } ${className}`}
    >
      {children}
    </div>
  );
}

/* Décalage doux au défilement : l’élément dérive lentement autour de sa place */
function ParallaxItem({
  factor,
  className = '',
  children,
}: {
  factor: number;
  className?: string;
  children: ReactNode;
}) {
  const outer = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const measure = outer.current;
    const move = inner.current;
    if (!measure || !move) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const r = measure.getBoundingClientRect();
      const mid = r.top + r.height / 2 - window.innerHeight / 2;
      move.style.transform = `translateY(${(mid * factor).toFixed(1)}px)`;
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [factor]);
  return (
    <div ref={outer} className={className}>
      <div ref={inner} style={{ willChange: 'transform' }}>
        {children}
      </div>
    </div>
  );
}

/* Compteur animé, pour les montants */
function CountUp({
  to,
  duration = 1300,
  delay = 0,
}: {
  to: number;
  duration?: number;
  delay?: number;
}) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (prefersReducedMotion()) {
      setVal(to);
      return;
    }
    let raf = 0;
    const t0 = performance.now() + delay;
    const tick = (t: number) => {
      const p = Math.min(1, Math.max(0, (t - t0) / duration));
      setVal(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, duration, delay]);
  return <>{val.toLocaleString(localeIntl())}</>;
}

function goToApp() {
  window.location.href = APP_URL;
}

/* Parcours DÉCOUVERTE : le visiteur décrit son monument et obtient son
   diagnostic AVANT d'avoir un compte — le wizard monument de l'app est
   désormais public, et l'inscription n'arrive qu'à la fin. C'est la
   destination des CTA « Trouver les aides pour mon monument », qui menaient
   jusqu'ici à la liste d'attente. */
function goToDecouverte() {
  window.location.href = `${APP_URL}/app/monuments/nouveau`;
}

/* Espace du compte. La landing ne sait QUE qu'une session existe : c'est
   l'application qui choisit entre tableau de bord, fiche du monument et
   wizard d'enregistrement (elle seule connaît l'offre et les biens du
   compte). D'où cet aiguillage plutôt qu'une destination fixe. */
function goToCompte() {
  window.location.href = `${APP_URL}/mon-compte`;
}

/* Tout CTA d'ENTRÉE dans le produit passe par ici. Connecté, le parcours
   découverte n'a pas de sens : il redemanderait de décrire un monument déjà
   enregistré. Le cookie est relu à CHAQUE clic, et non au montage :
   entre-temps on a pu se déconnecter dans l'onglet d'à côté.

   Les boutons qui ne sont pas une entrée gardent leur destination : « Nous
   contacter » de l'offre Multi-monuments reste un courrier. */
function siConnecte(sinon: () => void): () => void {
  return () => (sessionActive() ? goToCompte() : sinon());
}

const entrerDansMonumia = siConnecte(goToDecouverte);

/* Offre multi-monuments : pas d'auto-inscription, on passe par un échange. */
function goToContact() {
  window.location.href = 'mailto:contact@monumia.fr';
}

function CtaButton({
  children,
  variant = 'primary',
  onClick = goToApp,
  className = '',
}: {
  children: ReactNode;
  variant?: 'primary' | 'blue' | 'ghost' | 'white';
  onClick?: () => void;
  className?: string;
}) {
  const base =
    'group inline-flex items-center justify-center gap-2.5 rounded-full px-7 py-3.5 text-[15px] font-semibold transition-all duration-300';
  const styles: Record<string, CSSProperties> = {
    primary: { background: C.orange, color: '#fff' },
    blue: { background: C.blue, color: '#fff' },
    ghost: { background: 'transparent', color: C.blue, border: `1.5px solid ${C.blue}40` },
    white: { background: '#fff', color: C.blue },
  };
  const hover: Record<string, string> = {
    primary: 'hover:shadow-[0_10px_30px_-8px_rgba(241,113,5,0.55)] hover:-translate-y-0.5',
    blue: 'hover:shadow-[0_10px_30px_-8px_rgba(10,54,157,0.5)] hover:-translate-y-0.5',
    ghost: 'hover:border-[#0a369d] hover:bg-[#0a369d]/5',
    white: 'hover:shadow-[0_10px_30px_-8px_rgba(0,0,0,0.35)] hover:-translate-y-0.5',
  };
  return (
    <button onClick={onClick} className={`${base} ${hover[variant]} ${className}`} style={styles[variant]}>
      {children}
      <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
    </button>
  );
}

/* Titre de section : titre serif, filet orange */
function SectionTitle({
  title,
  sub,
  dark = false,
  filet = true,
}: {
  title: ReactNode;
  sub?: ReactNode;
  dark?: boolean;
  /* Le filet orange sous le titre. Sans lui, le sous-titre remonte contre le
     titre plutôt que de garder l'écart que le filet occupait. */
  filet?: boolean;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <h2
        className="font-serif text-[clamp(1.9rem,3.4vw,2.4rem)] leading-[1.2] tracking-[-0.01em]"
        style={{ color: dark ? '#fff' : C.ink }}
      >
        {title}
      </h2>
      {filet && (
        <div
          className="mx-auto mt-5 h-[3px] w-12 rounded-full"
          style={{ background: dark ? C.orangeVif : C.orange }}
        />
      )}
      {sub && (
        <p
          className={`mx-auto ${filet ? 'mt-5' : 'mt-3'} max-w-2xl text-[17px] font-medium leading-[1.65]`}
          style={{ color: dark ? 'rgba(255,255,255,0.7)' : C.inkSoft }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────
   En-tête
   ──────────────────────────────────────────── */

/* La bascule de langue. Chaque langue est nommée dans sa propre langue
   (« English » reste lisible pour qui ne lit pas le français) ; le choix est
   mémorisé dans un cookie partagé avec l'application, puis la page recharge.
   Dans l'en-tête, on ne propose que l'autre langue : un mot, pas un menu. */
function SelecteurLangue({ compact = false, className = '' }: { compact?: boolean; className?: string }) {
  const { t } = useTranslation();
  const courante = langueCourante();
  const langues = compact ? LANGUES.filter((l) => l !== courante) : LANGUES;
  return (
    <div
      role="group"
      aria-label={t('SelecteurLangue.libelle')}
      className={`items-center gap-1.5 text-[13.5px] ${className || 'inline-flex'}`}
    >
      {langues.map((langue, i) => (
        <span key={langue} className="inline-flex items-center gap-1.5">
          {i > 0 && (
            <span aria-hidden="true" style={{ color: C.inkFaint }}>
              ·
            </span>
          )}
          <button
            type="button"
            lang={langue}
            aria-pressed={langue === courante}
            disabled={langue === courante}
            onClick={() => changerLangue(langue)}
            className="rounded transition-colors duration-200 hover:text-[#0a369d] disabled:cursor-default"
            style={{
              color: langue === courante ? C.ink : C.inkSoft,
              fontWeight: langue === courante ? 600 : 500,
            }}
          >
            {t(`SelecteurLangue.${langue}`)}
          </button>
        </span>
      ))}
    </div>
  );
}

function Header() {
  const { t } = useTranslation();
  const [scrolled, setScrolled] = useState(false);
  // Le seul endroit où la session change un LIBELLÉ, et non seulement une
  // destination : proposer « Trouver mes aides » à qui en a déjà une liste le
  // renverrait refaire son diagnostic. Lu au montage — la barre est rendue une
  // fois, et le clic relit le cookie de toute façon.
  const [connecte] = useState(sessionActive);
  const barRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      setScrolled(window.scrollY > 12);
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const p = max > 0 ? Math.min(1, window.scrollY / max) : 0;
      if (barRef.current) barRef.current.style.transform = `scaleX(${p})`;
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const links = [
    { href: '#methode', label: t('Navigation.methode') },
    { href: '#tarifs', label: t('Navigation.tarifs') },
    { href: '#faq', label: t('Navigation.questions') },
  ];

  return (
    <header
      className="fixed inset-x-0 top-0 z-50 transition-all duration-300"
      style={{
        background: scrolled ? 'rgba(253, 249, 240, 0.88)' : 'rgba(253, 249, 240, 0)',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(12px)' : 'none',
        borderBottom: `1px solid ${scrolled ? C.border : 'transparent'}`,
      }}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 lg:px-8">
        {/* Logo horizontal : fleur Monumia à gauche du nom (version charte pour les headers) */}
        <a href="#" className="flex items-center gap-2.5" aria-label={t('Header.retourEnHaut')}>
          <Clover className="h-7 w-7" strokeWidth={10} style={{ color: C.orange }} />
          <span className="font-serif text-[1.35rem] font-bold tracking-[-0.01em]" style={{ color: C.blue }}>
            Monumia
          </span>
        </a>

        <nav className="hidden items-center gap-7 md:flex" aria-label={t('Header.navigation')}>
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-[14px] font-medium transition-colors duration-200 hover:text-[#0a369d]"
              style={{ color: C.inkSoft }}
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-5">
          {/* Masquée sur les petits écrans, où la barre n'a pas la place : le
              pied de page porte la bascule complète. */}
          <SelecteurLangue compact className="hidden sm:inline-flex" />
          <button
            onClick={entrerDansMonumia}
            className="whitespace-nowrap rounded-full px-5 py-2.5 text-[14px] font-semibold text-white transition-all duration-300 hover:shadow-[0_8px_20px_-6px_rgba(241,113,5,0.55)]"
            style={{ background: C.orange }}
          >
            {connecte ? t('Header.monCompte') : t('Commun.trouverMesAides')}
          </button>
        </div>
      </div>
      {/* Fil de lecture : un trait orange qui suit votre progression */}
      <div
        ref={barRef}
        className="absolute bottom-[-1px] left-0 h-[2px] w-full origin-left"
        style={{ background: C.orange, transform: 'scaleX(0)', opacity: scrolled ? 1 : 0 }}
        aria-hidden="true"
      />
    </header>
  );
}

/* ────────────────────────────────────────────
   Les partenaires — sous la promesse du héros. Le logo est tenté, et son
   absence retombe sur le nom en texte : une image cassée dirait moins que le
   nom. Déposer le fichier dans public/img/ suffit à le faire apparaître.
   ──────────────────────────────────────────── */

const HAUTEUR_LOGO = 'h-20 sm:h-32';

const PARTENAIRES: Array<{ nom: string; fichier: string; hauteur?: string }> = [
  { nom: 'La Demeure Historique', fichier: 'dh.png' },
  { nom: 'French Tech', fichier: 'frenchtech.png' },
  /* Mot-symbole très large : à hauteur égale il écrase les deux autres. */
  { nom: 'Incubateur emlyon', fichier: 'emlyon.png', hauteur: 'h-12 sm:h-20' },
];

function LogoPartenaire({
  nom,
  fichier,
  hauteur = HAUTEUR_LOGO,
}: {
  nom: string;
  fichier: string;
  hauteur?: string;
}) {
  const [absent, setAbsent] = useState(false);
  if (absent) {
    return (
      <span className="font-serif text-[19px] font-bold" style={{ color: C.blue }}>
        {nom}
      </span>
    );
  }
  return (
    <img
      src={`${BASE}img/${fichier}`}
      alt={nom}
      loading="lazy"
      className={`${hauteur} w-auto opacity-90 transition-opacity duration-300 hover:opacity-100`}
      onError={() => setAbsent(true)}
    />
  );
}

function Partenaires({ className = '', style }: { className?: string; style?: CSSProperties }) {
  const { t } = useTranslation();
  return (
    <div className={className} style={style}>
      <p
        className="text-[11px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: C.inkFaint }}
      >
        {t('Partenaires.referencePar')}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-5 sm:mt-5 sm:gap-x-8">
        {PARTENAIRES.map((p) => (
          <LogoPartenaire key={p.nom} {...p} />
        ))}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────
   Héros — la promesse + le trésor
   ──────────────────────────────────────────── */

/* La carte d’estimation compacte : l’essentiel des chiffres, posé devant la photo */
function EstimationCard() {
  const { t } = useTranslation();
  const { ref, inView } = useInView(0.3);
  return (
    <div
      ref={ref}
      className="flex flex-col rounded-2xl border p-5 shadow-[0_28px_60px_-22px_rgba(10,54,157,0.38)] sm:p-6"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11.5px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.blueLight }}>
          {t('EstimationCard.titre')}
        </span>
        <span
          className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
          style={{ background: C.paleBlue, color: C.blueLight }}
        >
          {t('Commun.exemple')}
        </span>
      </div>

      <h3 className="mt-2.5 font-serif text-[1.15rem] font-bold leading-snug" style={{ color: C.ink }}>
        {t('EstimationCard.projet')}
      </h3>
      <p className="text-[12.5px]" style={{ color: C.inkFaint }}>
        {t('EstimationCard.monument')}
      </p>

      <p className="mt-4 text-[11.5px] font-medium uppercase tracking-[0.1em]" style={{ color: C.inkFaint }}>
        {t('Commun.aidesEstimees')}
      </p>
      <p className="mt-1.5 font-serif text-[1.6rem] font-bold leading-none" style={{ color: C.blue }}>
        {/* L'ordre du montant et de la devise change d'une langue à l'autre :
            les deux compteurs entrent dans la phrase traduite. */}
        <Trans
          t={t}
          i18nKey="EstimationCard.fourchette"
          components={{
            // Hors de l'écran, `to` vaut 0 : le compteur affiche « 0 » et ne
            // part qu'à l'arrivée de la carte, comme avant.
            min: <CountUp to={inView ? 420000 : 0} />,
            max: <CountUp to={inView ? 680000 : 0} duration={1600} />,
            mot: <span className="text-[1.05rem] font-normal" style={{ color: C.inkFaint }} />,
          }}
        />
      </p>
      <div className="mt-3.5 h-2 overflow-hidden rounded-full" style={{ background: C.paleBlue }}>
        <div
          className="h-full rounded-full transition-[width] duration-[1600ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{
            width: inView ? '64%' : '0%',
            background: `linear-gradient(90deg, ${C.orange}, ${C.orangeVif})`,
          }}
        />
      </div>

      <p
        className="mt-4 flex items-center gap-2 border-t pt-3.5 text-[12.5px] leading-snug"
        style={{ borderColor: C.border, color: C.inkSoft }}
      >
        <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: C.blueLight }} strokeWidth={1.8} />
        {t('EstimationCard.identifiees')}
      </p>

      <button
        onClick={entrerDansMonumia}
        className="mt-3 self-start text-[12.5px] font-semibold transition-opacity duration-200 hover:opacity-75"
        style={{ color: C.orange }}
      >
        {t('EstimationCard.etPourVous')}
      </button>
    </div>
  );
}

function Hero() {
  const { t } = useTranslation();
  return (
    <section className="relative overflow-hidden px-5 pb-24 pt-24 sm:pt-28 lg:px-8 lg:pb-28 lg:pt-32">
      <div
        className="pointer-events-none absolute -top-32 right-[-12%] h-[460px] w-[460px] rounded-full blur-[130px]"
        style={{ background: 'rgba(241, 113, 5, 0.1)' }}
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-[1.22fr_0.78fr] lg:items-start lg:gap-12">
        {/* Le texte du héros s'affiche d'emblée, sans fondu : parti d'une
            opacité nulle, il laissait un écran vide tant que le téléphone,
            occupé par ailleurs, n'avait pas démarré l'animation. Le fondu reste
            sur la colonne de l'image, qui n'est pas ce qu'on lit en premier. */}
        <div>
          <p
            className="text-[11.5px] font-semibold uppercase tracking-[0.16em]"
            style={{ color: C.orange }}
          >
            {t('Hero.surtitre')}
          </p>

          <h1
            className="mt-4 font-serif text-[clamp(1.85rem,4.2vw,2.7rem)] leading-[1.13] tracking-[-0.015em]"
            style={{ color: C.ink }}
          >
            <Trans
              t={t}
              i18nKey="Hero.titre"
              components={{
                bleu: <span style={{ color: C.blue }} />,
                orange: <span style={{ color: C.orange }} />,
              }}
            />
          </h1>

          <p
            className="mt-7 max-w-[41rem] text-[16px] font-medium leading-[1.7] sm:text-[17px]"
            style={{ color: C.inkSoft }}
          >
            {t('Hero.intro')}
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-4">
            <CtaButton variant="blue" onClick={entrerDansMonumia}>
              {t('Commun.trouverLesAides')}
            </CtaButton>
          </div>

          {/* Ce qu'engage le clic : rien. Dit avant le clic, pas après. */}
          <p className="mt-5 text-[13px]" style={{ color: C.inkFaint }}>
            {t('Hero.reassurance')}
          </p>

          {/* Ceux qui nous accompagnent, dits tout de suite : la confiance se
              gagne avant le clic, pas en bas de page. */}
          <Partenaires className="mt-8" />
        </div>

        <div
          className="fade-up relative mx-auto mt-12 w-full max-w-[460px] lg:mt-0 lg:max-w-none"
          style={{ animationDelay: '0.4s' }}
        >
          <EstimationCard />

          {/* Mini-carte d’alerte flottante : la veille incarnée */}
          <div
            className="relative z-10 -mt-3 ml-auto mr-2 flex w-[240px] max-w-[88%] items-start gap-3 rounded-xl border p-3.5 pl-4 shadow-[0_18px_40px_-16px_rgba(34,43,53,0.3)] [animation:floaty_7s_ease-in-out_infinite]"
            style={{ background: C.card, borderColor: C.border }}
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: C.paleOrange }}>
              <BellRing className="h-4.5 w-4.5" style={{ color: C.orange }} strokeWidth={1.8} />
            </span>
            <span>
              <span className="block text-[11px] font-semibold uppercase tracking-[0.1em]" style={{ color: C.orange }}>
                {t('Hero.alerteTitre')}
              </span>
              <span className="mt-0.5 block text-[12.5px] leading-snug" style={{ color: C.ink }}>
                {t('Hero.alerteTexte')}
              </span>
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   Le constat — l’état du patrimoine et l’éparpillement des guichets.
   Un chiffre, une source : le lien est en bas de section, et la phrase
   d’origine reste en commentaire à côté du chiffre, mot pour mot, comme les
   `quote` des fiches d’aides. Un chiffre sans sa source ne se corrige pas.
   ──────────────────────────────────────────── */

/* Les guichets qu’un propriétaire doit démarcher un par un, chacun avec ses
   règles et son calendrier. */
const GUICHETS = [
  'etat',
  'europe',
  'region',
  'departement',
  'intercommunalite',
  'prefecture',
  'fondations',
  'mecenat',
] as const;

/* Le rapport du Sénat : cité dans le constat, et consultable d’un clic. */
const RAPPORT_SENAT = 'https://www.senat.fr/rap/r25-865/r25-8651.pdf';

/* [clé du libellé dans `Constat.sources`, lien] */
const SOURCES_CONSTAT = [
  [
    'ministere',
    'https://www.culture.gouv.fr/mc/content/download/372748/pdf_file/MHI_EtatConservation_2019-2024_BL_20250527.pdf',
  ],
  [
    'fondation',
    'https://strapi-upload.cdn.fondation-patrimoine.org/CP_Chiffres_cles_2025_du_patrimoine_non_protege_55dcc186a8.pdf',
  ],
] as const;

/* Un chiffre du constat : pas de cadre, pas de carte — le chiffre en grand
   serif bleu, et sous lui ce qu’il désigne. Deux chiffres, posés à nu. */
function ConstatChiffre({
  chiffre,
  children,
}: {
  chiffre: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="text-center">
      <p
        className="font-serif text-[clamp(2.6rem,6.5vw,4.2rem)] font-bold leading-[1.05] tracking-[-0.02em]"
        style={{ color: C.blue }}
      >
        {chiffre}
      </p>
      <p className="mx-auto mt-4 max-w-sm text-[15.5px] leading-[1.7]" style={{ color: C.inkSoft }}>
        {children}
      </p>
    </div>
  );
}

function Constat() {
  /* Le compteur ne part qu’une fois le chiffre à l’écran : un chiffre qui a
     fini de défiler avant qu’on le regarde ne se lit pas. */
  const { t } = useTranslation();
  const { ref, inView } = useInView(0.2);
  return (
    <section id="constat" className="scroll-mt-20 px-5 py-20 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-6xl">
        {/* Les deux chiffres, sans cadre : l’état du patrimoine, d’un coup d’œil */}
        <div ref={ref} className="grid items-start gap-14 sm:grid-cols-2 sm:gap-10">
          <Reveal>
            {/* 17,88 % mauvais état + 4,90 % péril = 22,78 % sur 36 512 MH */}
            <ConstatChiffre chiffre={t('Constat.presDUnSurQuatre')}>
              {t('Constat.mauvaisEtat')}
            </ConstatChiffre>
          </Reveal>

          <Reveal delay={120}>
            {/* 67 400 sur 295 800, Fondation du patrimoine, Observatoire du
                patrimoine non protégé, 19/09/2025 */}
            <ConstatChiffre chiffre={inView ? <CountUp to={67400} /> : '0'}>
              {t('Constat.nonProteges')}
            </ConstatChiffre>
          </Reveal>
        </div>

        <ul className="mx-auto mt-10 max-w-3xl space-y-1.5 text-center text-[12px] leading-[1.6]">
          {SOURCES_CONSTAT.map(([source, href]) => (
            <li key={href} style={{ color: C.inkFaint }}>
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2 transition-colors duration-200 hover:text-[#0a369d]"
              >
                {t(`Constat.sources.${source}`)}
              </a>
            </li>
          ))}
        </ul>

        {/* Le maquis : le titre, puis les guichets qu’il faut démarcher un par un */}
        <Reveal>
          <div className="mt-24">
            <SectionTitle
              title={t('Constat.maquisTitre')}
              sub={t('Constat.maquisTexte')}
            />
            <div className="mx-auto mt-9 flex max-w-2xl flex-wrap justify-center gap-2">
              {GUICHETS.map((g) => (
                <span
                  key={g}
                  className="rounded-full border px-3.5 py-1.5 text-[13px] font-medium"
                  style={{ background: C.card, borderColor: C.border, color: C.inkSoft }}
                >
                  {t(`Constat.guichets.${g}`)}
                </span>
              ))}
            </div>
          </div>
        </Reveal>

      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   Le Sénat dit la même chose que nous, et nous l’avons construit. Posé après
   la démonstration : la recommandation se lit mieux une fois la plateforme vue.
   ──────────────────────────────────────────── */

function RapportSenat() {
  const { t } = useTranslation();
  return (
    <section className="px-5 pb-6 pt-20 lg:px-8 lg:pb-8 lg:pt-24">
      <Reveal>
        <div
          className="mx-auto grid max-w-6xl items-center gap-10 rounded-2xl border p-7 sm:p-10 md:grid-cols-[200px_minmax(0,1fr)] md:gap-12"
          style={{ background: C.card, borderColor: C.border }}
        >
          <a
            href={RAPPORT_SENAT}
            target="_blank"
            rel="noopener noreferrer"
            className="group mx-auto block w-[200px] transition-transform duration-300 hover:-translate-y-1"
          >
            {/* La couverture du rapport, telle qu’elle est publiée : la première
                page du PDF du Sénat, rendue en image */}
            <span
              className="block overflow-hidden rounded-lg border shadow-[0_18px_40px_-22px_rgba(34,43,53,0.5)]"
              style={{ background: '#fff', borderColor: C.border }}
            >
              <img
                src={`${BASE}img/rapport-senat.jpg`}
                alt={t('RapportSenat.altCouverture')}
                loading="lazy"
                width={396}
                height={560}
                className="block w-full"
              />
            </span>
            <span
              className="mt-3.5 flex items-center justify-center gap-1.5 text-[13.5px] font-semibold underline-offset-2 group-hover:underline"
              style={{ color: C.blue }}
            >
              <FileText className="h-4 w-4" strokeWidth={1.8} />
              {t('RapportSenat.consulter')}
            </span>
          </a>

          <div>
            {/* Un vrai titre de section, et non l'exergue en petites capitales
                qui tenait ici : c'est l'argument le plus fort de la page, il
                doit se lire à la hauteur des autres. Le filet orange reprend
                l'idiome de `SectionTitle`, aligné à gauche — le bloc est en
                deux colonnes, un titre centré flotterait à côté de sa
                couverture. */}
            <h2
              className="font-serif text-[clamp(1.55rem,2.9vw,2.05rem)] leading-[1.2] tracking-[-0.01em]"
              style={{ color: C.ink }}
            >
              {t('RapportSenat.titre')}
            </h2>
            <div className="mt-4 h-[3px] w-12 rounded-full" style={{ background: C.orange }} />
            <p className="mt-5 text-[16.5px] leading-[1.75]" style={{ color: C.inkSoft }}>
              {t('RapportSenat.texte')}
            </p>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/* ────────────────────────────────────────────
   Les trois missions — démonstration guidée, souris comprise
   ──────────────────────────────────────────── */

const DEMO_DURATION = 12500;
/* La scène 1 enchaîne deux écrans : on prolonge l'écran des résultats
   pour laisser le temps de le lire avant que la boucle ne reparte. */
const SCENE_TROUVER_DURATION = 15500;
/* La scène 3 enchaîne aussi deux écrans : le tableau de bord des projets,
   puis le détail du projet choisi (documents et téléchargement). */
const SCENE_DOSSIERS_DURATION = 14500;

/* Vitesse de lecture des démonstrations. Les scènes restent écrites à
   l'échelle 1 — les délais des animations CSS et les `at` du curseur sont des
   secondes de scène, lisibles telles quelles — et c'est la lecture qu'on
   ralentit, d'un seul réglage : un visiteur qui découvre la plateforme a besoin
   de lire chaque écran avant que la souris ne reparte. */
const DEMO_SPEED: number = 0.62;

/** Durée réelle (ms) d'un délai écrit en temps de scène. */
const demoMs = (sceneMs: number) => Math.round(sceneMs / DEMO_SPEED);

/* Cadre d'une scène : applique la vitesse de lecture à TOUTES ses animations.
   Régler le `playbackRate` étire d'un coup les délais et les durées, sans
   toucher aux temps écrits dans les scènes — ce que ne permettrait aucune
   propriété CSS. Seuls les comptes à rebours en JS (CountUp) restent à
   convertir à la main, via `demoMs`. */
function SceneStage({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    /* Mouvement réduit : la feuille de style écrase déjà les durées, mais pas
       les délais — les ralentir ne ferait qu'allonger l'attente. */
    if (!el || DEMO_SPEED === 1 || prefersReducedMotion()) return;
    /* getAnimations() force le recalcul de style : les animations CSS encore
       en phase de délai sont déjà là. Celle du curseur aussi — son effet est
       un effet enfant, donc joué avant celui-ci. */
    el.getAnimations({ subtree: true }).forEach((a) => {
      a.playbackRate = DEMO_SPEED;
    });
  }, []);
  return (
    <div ref={ref} className="h-full">
      {children}
    </div>
  );
}

function DemoChip({
  children,
  appear,
  select,
  demoId,
}: {
  children: ReactNode;
  appear: number;
  select?: number;
  demoId?: string;
}) {
  const anims = [`pop-in 0.5s ${appear}s cubic-bezier(0.22,1,0.36,1) both`];
  if (select != null) anims.push(`chip-select 0.45s ${select}s ease forwards`);
  return (
    <span
      data-demo={demoId}
      className="rounded-full border px-3 py-1.5 text-[12.5px] font-medium"
      style={{
        opacity: 0,
        animation: anims.join(', '),
        background: '#fff',
        borderColor: C.border,
        color: C.inkSoft,
      }}
    >
      {children}
    </span>
  );
}

/* Le curseur qui rejoue la démonstration. Plutôt que des trajectoires écrites
   à la main, il mesure la position réelle de ses cibles (attributs data-demo)
   dans la scène et glisse de centre en centre : chaque clic tombe pile au
   milieu de son bouton, quelle que soit la taille de l'écran. Il ne va que
   d'un endroit cliquable à un autre : si la prochaine cible est lointaine
   dans le temps, il s'efface sur place après son clic et réapparaît en
   glissant vers elle ; après le dernier clic, il s'efface sur place. */

type CursorStep = { at: number; target: string; click?: boolean };

/* Pointe de la flèche dans son rendu 20 px (viewBox 24) */
const CURSOR_TIP = { x: 5, y: 3 };

function Cursor({ steps, duration = DEMO_DURATION }: { steps: CursorStep[]; duration?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = prefersReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || reduced) return;
    const scene = el.parentElement;
    if (!scene) return;

    /* Centre d'une cible relatif à la scène, via la chaîne offsetParent :
       insensible aux transforms des animations d'apparition. */
    const center = (target: HTMLElement) => {
      let x = target.offsetWidth / 2 - CURSOR_TIP.x;
      let y = target.offsetHeight / 2 - CURSOR_TIP.y;
      let node: HTMLElement | null = target;
      while (node && node !== scene) {
        x += node.offsetLeft;
        y += node.offsetTop;
        node = node.offsetParent as HTMLElement | null;
      }
      return { x, y };
    };

    const pts = steps.flatMap((s) => {
      const target = scene.querySelector<HTMLElement>(`[data-demo="${s.target}"]`);
      return target ? [{ at: s.at, ...center(target) }] : [];
    });
    if (!pts.length) return;

    const D = duration / 1000;
    const TRAVEL = 0.85; // durée d'un déplacement entre deux cibles
    const VANISH_GAP = 4; // au-delà, le curseur s'éclipse plutôt que d'attendre sur place
    const EASE = 'cubic-bezier(0.5, 0.05, 0.2, 1)';
    const at = (p: { x: number; y: number }) => ({ left: `${p.x}px`, top: `${p.y}px` });
    const start = { x: pts[0].x + 64, y: pts[0].y + 88 };
    const last = pts[pts.length - 1];
    const fadeFrom = Math.min(last.at + 1.1, D - 0.7);

    const frames: Keyframe[] = [
      { offset: 0, ...at(start), opacity: 0 },
      { offset: Math.max(0, pts[0].at - TRAVEL) / D, ...at(start), opacity: 0, easing: EASE },
    ];
    pts.forEach((p, i) => {
      frames.push({ offset: p.at / D, ...at(p), opacity: 1 });
      const next = pts[i + 1];
      if (!next) return;
      if (next.at - p.at > VANISH_GAP) {
        /* Longue attente : extinction sur place, puis réapparition en
           glissant vers la cible suivante (comme l'entrée en scène). */
        const reentry = { x: next.x + 56, y: next.y + 72 };
        frames.push({ offset: (p.at + 1.0) / D, ...at(p), opacity: 1 });
        frames.push({ offset: (p.at + 1.4) / D, ...at(p), opacity: 0 });
        frames.push({ offset: (next.at - TRAVEL) / D, ...at(reentry), opacity: 0, easing: EASE });
      } else {
        const leave = Math.max(p.at, next.at - TRAVEL);
        frames.push({ offset: leave / D, ...at(p), opacity: 1, easing: EASE });
      }
    });
    frames.push({ offset: fadeFrom / D, ...at(last), opacity: 1 });
    frames.push({ offset: Math.min(fadeFrom + 0.6, D) / D, ...at(last), opacity: 0 });
    frames.push({ offset: 1, ...at(last), opacity: 0 });

    const anim = el.animate(frames, { duration, fill: 'forwards' });
    return () => anim.cancel();
  }, [steps, duration, reduced]);

  return (
    <div ref={ref} className="demo-cursor" aria-hidden="true">
      {!reduced &&
        steps
          .filter((s) => s.click)
          .map((s) => (
            <span
              key={s.at}
              className="cursor-bloom"
              style={{ animation: `cursor-bloom 0.55s ${s.at + 0.15}s ease-out forwards` }}
            />
          ))}
      <svg viewBox="0 0 24 24" className="relative h-5 w-5 drop-shadow-[0_2px_6px_rgba(10,54,157,0.35)]">
        <path
          d="M5.5 3.5 L5.5 20 L9.8 16.2 L12.2 21.8 L15.1 20.5 L12.6 15 L18.5 14.6 Z"
          fill="#f17105"
          stroke="#fff"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

/* Les aides de l’écran de résultats de la scène 1 de la démonstration */
const RESULTATS_EXEMPLE = ['drac', 'region', 'fondation', 'mecenat'] as const;

/* Scène 1 — trouver ses aides : questionnaire, puis résultats du moteur */
function SceneTrouver() {
  const { t } = useTranslation();
  return (
    <div className="relative h-full">
      {/* Écran 1 : le questionnaire de qualification */}
      <div className="absolute inset-0 flex flex-col" style={{ animation: 'screen-out 0.45s 5.8s ease forwards' }}>
        <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '0.1s' }}>
          <span className="text-[11.5px] font-semibold uppercase tracking-[0.16em]" style={{ color: C.orange }}>
            <Trans
              t={t}
              i18nKey="SceneTrouver.question"
              components={{ sur: <span style={{ color: C.inkFaint }} /> }}
            />
          </span>
          <span className="flex gap-1">
            {[...Array(5)].map((_, i) => (
              <span
                key={i}
                className="h-1.5 w-4 rounded-full"
                style={{ background: i < 3 ? C.orange : C.paleBlue }}
              />
            ))}
          </span>
        </div>

        <h4
          className="demo-pop mt-4 font-serif text-[1.1rem] font-bold leading-snug sm:text-[1.2rem]"
          style={{ color: C.ink, animationDelay: '0.3s' }}
        >
          {t('SceneTrouver.porteurs')}
        </h4>
        <p
          className="demo-pop mt-3 flex gap-2 rounded-lg border-l-2 bg-white p-3 text-[12.5px] leading-snug"
          style={{ borderColor: C.blueLight, color: C.inkSoft, animationDelay: '0.7s' }}
        >
          <Info className="mt-[2px] h-3.5 w-3.5 shrink-0" style={{ color: C.blue }} strokeWidth={2} />
          <span>{t('SceneTrouver.porteurAide')}</span>
        </p>
        <div className="mt-3.5 flex flex-wrap gap-2">
          <DemoChip appear={1.1}>{t('SceneTrouver.particulier')}</DemoChip>
          <DemoChip appear={1.25}>{t('SceneTrouver.sci')}</DemoChip>
          <DemoChip appear={1.4} select={2.4} demoId="chip-association">
            {t('SceneTrouver.association')}
          </DemoChip>
        </div>

        <div className="demo-pop mt-6" style={{ animationDelay: '3s' }}>
          <h4 className="font-serif text-[1.1rem] font-bold leading-snug sm:text-[1.2rem]" style={{ color: C.ink }}>
            {t('SceneTrouver.partiesProtegees')}
          </h4>
          <div className="mt-3 flex flex-wrap gap-2">
            <DemoChip appear={3.3} select={4.5} demoId="chip-parties-protegees">
              {t('SceneTrouver.oui')}
            </DemoChip>
            <DemoChip appear={3.45}>{t('SceneTrouver.non')}</DemoChip>
          </div>
        </div>

        <div
          className="demo-pop mt-auto flex items-center gap-2.5 rounded-xl border bg-white p-3"
          style={{ borderColor: C.border, animationDelay: '5s' }}
        >
          <Sparkles className="h-4 w-4 shrink-0" style={{ color: C.orange }} strokeWidth={1.8} />
          <span className="text-[12.5px]" style={{ color: C.inkSoft }}>
            {t('SceneTrouver.recherche')}
          </span>
          <span className="ml-auto flex gap-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="pulse-dot h-1.5 w-1.5 rounded-full"
                style={{ background: C.orange, animationDelay: `${i * 0.2}s` }}
              />
            ))}
          </span>
        </div>
      </div>

      {/* Écran 2 : les résultats, l’estimation et la fiche de l’aide */}
      <div
        className="absolute inset-0 flex flex-col"
        style={{ opacity: 0, animation: 'screen-in 0.5s 6.2s cubic-bezier(0.22,1,0.36,1) both' }}
      >
        <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '6.4s' }}>
          <span className="font-serif text-[1.05rem] font-bold" style={{ color: C.ink }}>
            {t('Commun.aidesCorrespondent')}
          </span>
          <span
            className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
            style={{ background: C.paleBlue, color: C.blueLight }}
          >
            {t('Commun.exemple')}
          </span>
        </div>

        <div className="mt-4 space-y-2.5">
          {RESULTATS_EXEMPLE.map((resultat, i) => (
            <div
              key={resultat}
              data-demo={i === 0 ? 'resultat' : undefined}
              className="flex items-center justify-between gap-2 rounded-lg bg-white px-3 py-2.5"
              style={{
                opacity: 0,
                animation:
                  i === 0
                    ? `pop-in 0.55s 6.6s cubic-bezier(0.22,1,0.36,1) forwards, row-flash 0.7s 10.3s ease forwards`
                    : `pop-in 0.55s ${6.6 + i * 0.3}s cubic-bezier(0.22,1,0.36,1) forwards`,
              }}
            >
              <span className="flex min-w-0 items-center gap-2 text-[12.5px]" style={{ color: C.ink }}>
                <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: C.blueLight }} strokeWidth={1.8} />
                {t(`ResultatsExemple.${resultat}.nom`)}
              </span>
              <span className="shrink-0 text-[12px] font-semibold" style={{ color: C.inkSoft }}>
                {t(`ResultatsExemple.${resultat}.montant`)}
              </span>
            </div>
          ))}
        </div>

        <div className="demo-pop mt-4" style={{ animationDelay: '7.9s' }}>
          <div className="flex items-center justify-between text-[12px]">
            <span className="font-medium" style={{ color: C.inkSoft }}>
              {t('Commun.chances')}
            </span>
            <span className="font-semibold" style={{ color: C.orange }}>
              {t('Commun.elevees')}
            </span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full" style={{ background: C.paleBlue }}>
            <div
              className="grow-bar h-full rounded-full"
              style={{
                ['--bar-w' as string]: '78%',
                animationDelay: '8.1s',
                background: `linear-gradient(90deg, ${C.orange}, ${C.orangeVif})`,
              }}
            />
          </div>
        </div>

        <div
          className="demo-pop mt-auto flex items-center justify-between gap-2 rounded-xl px-4 py-3.5"
          style={{ background: C.paleOrange, animationDelay: '8.5s' }}
        >
          <span className="text-[11.5px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.ink }}>
            {t('Commun.aidesEstimees')}
          </span>
          <span className="font-serif text-[1.2rem] font-bold leading-none" style={{ color: C.orange }}>
            <Trans
              t={t}
              i18nKey="SceneTrouver.fourchette"
              components={{
                min: <CountUp to={92000} delay={demoMs(8700)} duration={demoMs(1300)} />,
                max: <CountUp to={140000} delay={demoMs(8700)} duration={demoMs(1700)} />,
              }}
            />
          </span>
        </div>

        {/* La fiche de l’aide s’ouvre au clic sur la première aide */}
        <div
          className="toast-in absolute right-0 top-[104px] z-10 w-[230px] rounded-xl border bg-white p-3.5 shadow-[0_18px_40px_-18px_rgba(34,43,53,0.45)]"
          style={{ borderColor: C.border, animationDelay: '10.55s' }}
        >
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 shrink-0" style={{ color: C.blue }} strokeWidth={1.8} />
            <span className="text-[12px] font-semibold" style={{ color: C.ink }}>
              {t('SceneTrouver.fiche.titre')}
            </span>
          </div>
          <ul className="mt-2 space-y-1 text-[11.5px] leading-snug" style={{ color: C.inkSoft }}>
            <li>{t('SceneTrouver.fiche.conditions')}</li>
            <li>{t('SceneTrouver.fiche.contact')}</li>
            <li>{t('SceneTrouver.fiche.documents')}</li>
          </ul>
        </div>
      </div>

      <Cursor
        duration={SCENE_TROUVER_DURATION}
        steps={[
          { at: 2.15, target: 'chip-association', click: true },
          { at: 4.3, target: 'chip-parties-protegees', click: true },
          { at: 10.0, target: 'resultat', click: true },
        ]}
      />
    </div>
  );
}

/* Scène 2 — la veille : échéancier, alerte activée au clic, radar et détection */
function SceneVeille() {
  const { t } = useTranslation();
  const items: Array<[string, string]> = [
    [t('SceneVeille.dates.fondation.nom'), t('SceneVeille.dates.fondation.date')],
    [t('SceneVeille.dates.etat.nom'), t('SceneVeille.dates.etat.date')],
    [t('SceneVeille.dates.region.nom'), t('SceneVeille.dates.region.date')],
  ];
  return (
    <div className="relative flex h-full flex-col">
      <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '0.1s' }}>
        <span className="font-serif text-[1.05rem] font-bold" style={{ color: C.ink }}>
          {t('SceneVeille.titre')}
        </span>
        <span
          className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
          style={{ background: C.paleBlue, color: C.blueLight }}
        >
          {t('Commun.exemple')}
        </span>
      </div>

      <div className="mt-4 space-y-2.5">
        {items.map(([name, date], i) => (
          <div
            key={name}
            className="demo-pop flex items-center gap-2.5 rounded-lg bg-white px-3 py-2.5"
            style={{ animationDelay: `${0.5 + i * 0.3}s` }}
          >
            <CalendarClock className="h-4 w-4 shrink-0" style={{ color: C.blueLight }} strokeWidth={1.8} />
            <span className="min-w-0 flex-1 truncate text-[12.5px]" style={{ color: C.ink }}>
              {name}
            </span>
            <span
              className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold"
              style={{ background: C.paleBlue, color: C.blue }}
            >
              {date}
            </span>
            <span
              data-demo={i === 0 ? 'cloche' : undefined}
              className="grid h-7 w-7 shrink-0 place-items-center rounded-full border"
              style={{
                borderColor: C.border,
                color: C.inkFaint,
                background: '#fff',
                ...(i === 0 ? { animation: 'bell-on 0.45s 3.1s ease forwards' } : {}),
              }}
            >
              <Bell className="h-3.5 w-3.5" strokeWidth={2} />
            </span>
          </div>
        ))}
      </div>

      <p
        className="demo-pop mt-2.5 flex items-center gap-1.5 text-[11.5px] font-medium"
        style={{ color: C.orange, animationDelay: '3.4s' }}
      >
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
        {t('SceneVeille.alerteActivee')}
      </p>

      <div
        className="toast-in mt-auto flex items-start gap-2.5 rounded-xl border bg-white p-3 shadow-[0_12px_28px_-14px_rgba(34,43,53,0.35)]"
        style={{ borderColor: C.border, animationDelay: '7.2s' }}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: C.paleOrange }}>
          <BellRing className="h-4 w-4" style={{ color: C.orange }} strokeWidth={1.8} />
        </span>
        <span>
          <span className="block text-[10.5px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orange }}>
            {t('SceneVeille.alerteMonumia')}
          </span>
          <span className="mt-0.5 block text-[12.5px] leading-snug" style={{ color: C.ink }}>
            {t('SceneVeille.nouvelleAide')}
          </span>
        </span>
        <span
          className="ml-auto flex shrink-0 items-center gap-1.5 self-center rounded-full px-2.5 py-1 text-[10.5px] font-medium"
          style={{ background: C.paleBlue, color: C.blue }}
        >
          <HeartHandshake className="h-3 w-3" strokeWidth={2} />
          {t('SceneVeille.mecenat')}
        </span>
      </div>

      <Cursor steps={[{ at: 2.8, target: 'cloche', click: true }]} />
    </div>
  );
}

/* Scène 3 — les dossiers : on part du tableau de bord de tous les projets,
   le curseur ouvre le projet choisi, puis l'écran bascule sur son détail où
   l'on coche les pièces et télécharge le dossier. */
function SceneDossiers() {
  const { t } = useTranslation();
  /* Tous les projets en cours (écran 1). Le premier est celui qu'on ouvre. */
  const enCours: Array<[string, string, string]> = [
    [t('SceneDossiers.projets.toiture.nom'), t('SceneDossiers.projets.toiture.statut'), '70%'],
    [t('SceneDossiers.projets.vitraux.nom'), t('SceneDossiers.projets.vitraux.statut'), '40%'],
    [t('SceneDossiers.projets.electricite.nom'), t('SceneDossiers.projets.electricite.statut'), '15%'],
  ];
  /* Les pièces du dossier (écran 2). `at` = instant où la coche apparaît. */
  const pieces: Array<[string, number]> = [
    [t('SceneDossiers.pieces.devis'), 4.9],
    [t('SceneDossiers.pieces.photos'), 5.4],
    [t('SceneDossiers.pieces.financement'), 7.45],
    [t('SceneDossiers.pieces.abf'), 8.75],
  ];
  return (
    <div className="relative h-full">
      {/* Écran 1 : le tableau de bord de tous les projets en cours */}
      <div className="absolute inset-0 flex flex-col" style={{ animation: 'screen-out 0.45s 3.6s ease forwards' }}>
        <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '0.1s' }}>
          <span className="font-serif text-[1.05rem] font-bold" style={{ color: C.ink }}>
            {t('SceneDossiers.titre')}
          </span>
          <span
            className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
            style={{ background: C.paleBlue, color: C.blueLight }}
          >
            {t('Commun.exemple')}
          </span>
        </div>

        <div className="mt-4 space-y-2.5">
          {enCours.map(([name, status, pct], i) => {
            const active = i === 0;
            return (
              <div
                key={name}
                data-demo={active ? 'projet-toiture' : undefined}
                className={active ? 'rounded-xl border bg-white px-3.5 py-3' : 'demo-pop rounded-xl border bg-white px-3.5 py-3'}
                style={{
                  borderColor: active ? 'rgba(241,113,5,0.4)' : C.border,
                  ...(active
                    ? {
                        opacity: 0,
                        animation:
                          'pop-in 0.55s 0.5s cubic-bezier(0.22,1,0.36,1) forwards, row-flash 0.7s 2.7s ease forwards',
                      }
                    : { animationDelay: `${0.5 + i * 0.25}s` }),
                }}
              >
                <div className="flex items-center gap-2.5">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: C.paleBlue }}>
                    <FolderOpen className="h-4 w-4" style={{ color: C.blue }} strokeWidth={1.8} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12.5px] font-semibold" style={{ color: C.ink }}>
                      {name}
                    </span>
                    <span className="block truncate text-[11px]" style={{ color: C.inkFaint }}>
                      {status}
                    </span>
                  </span>
                  <span className="shrink-0 text-[11px] font-semibold" style={{ color: C.inkSoft }}>
                    {pct}
                  </span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full" style={{ background: C.paleBlue }}>
                  <div
                    className="grow-bar h-full rounded-full"
                    style={{
                      ['--bar-w' as string]: pct,
                      animationDelay: `${1 + i * 0.2}s`,
                      background: active ? C.orange : C.blueLight,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Écran 2 : le détail du projet ouvert — documents et téléchargement */}
      <div
        className="absolute inset-0 flex flex-col"
        style={{ opacity: 0, animation: 'screen-in 0.5s 4s cubic-bezier(0.22,1,0.36,1) both' }}
      >
        <div className="demo-pop flex items-center justify-between gap-3" style={{ animationDelay: '4.2s' }}>
          <span className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: C.paleBlue }}>
              <FolderOpen className="h-4.5 w-4.5" style={{ color: C.blue }} strokeWidth={1.8} />
            </span>
            <span className="min-w-0">
              <span className="block truncate font-serif text-[1.05rem] font-bold leading-tight" style={{ color: C.ink }}>
                {t('SceneDossiers.projets.toiture.nom')}
              </span>
              <span className="block truncate text-[11.5px]" style={{ color: C.inkFaint }}>
                {t('SceneDossiers.documentsProjet')}
              </span>
            </span>
          </span>
          <span className="flex shrink-0 items-center">
            <span
              className="grid h-7 w-7 place-items-center rounded-full border-2 border-white text-[10px] font-bold"
              style={{ background: C.paleBlue, color: C.blue }}
            >
              PB
            </span>
            <span
              className="-ml-2 grid h-7 w-7 place-items-center rounded-full border-2 border-white text-[10px] font-bold"
              style={{ background: C.paleOrange, color: C.orange }}
            >
              AR
            </span>
          </span>
        </div>

        <div className="mt-3.5 space-y-2">
          {pieces.map(([piece, at], i) => (
            <div
              key={piece}
              className="demo-pop flex items-center gap-2.5 rounded-lg bg-white px-3 py-2"
              style={{ animationDelay: '4.4s' }}
            >
              <span data-demo={`piece-${i}`} className="relative grid h-4 w-4 shrink-0 place-items-center">
                <span className="absolute h-4 w-4 rounded-full border-[1.5px]" style={{ borderColor: C.border }} />
                <CheckCircle2
                  className="check-pop relative h-4 w-4 bg-white"
                  style={{ color: C.orange, animationDelay: `${at}s` }}
                  strokeWidth={2}
                />
              </span>
              <span className="truncate text-[12.5px]" style={{ color: C.ink }}>
                {piece}
              </span>
            </div>
          ))}
        </div>

        <div
          data-demo="export"
          className="mt-3.5 flex items-center justify-center gap-2 rounded-lg py-2.5 text-[13px] font-semibold text-white"
          style={{
            background: C.blue,
            opacity: 0,
            animation: 'pop-in 0.55s 9.4s cubic-bezier(0.22,1,0.36,1) forwards, btn-press 0.3s 10.65s ease',
          }}
        >
          <Download className="h-4 w-4" strokeWidth={2} />
          {t('SceneDossiers.telecharger')}
        </div>

        <div
          className="toast-in mt-3 flex items-center gap-2.5 rounded-xl border bg-white p-2.5"
          style={{ borderColor: 'rgba(241,113,5,0.4)', animationDelay: '11.05s' }}
        >
          <CheckCircle2 className="h-4.5 w-4.5 shrink-0" style={{ color: C.orange }} strokeWidth={2} />
          <span className="text-[12.5px] leading-snug" style={{ color: C.ink }}>
            {t('SceneDossiers.pret')}
          </span>
        </div>
      </div>

      <Cursor
        duration={SCENE_DOSSIERS_DURATION}
        steps={[
          { at: 2.8, target: 'projet-toiture', click: true },
          { at: 7.2, target: 'piece-2', click: true },
          { at: 8.5, target: 'piece-3', click: true },
          { at: 10.6, target: 'export', click: true },
        ]}
      />
    </div>
  );
}

/* Les textes vivent dans `Demo.categories.<key>` (onglet, titre) et
   `Demo.fonctionnalites.<id>` (titre, texte) : ici, seulement la structure. */
const CATEGORIES = [
  {
    key: 'trouver',
    icon: Search,
    duration: SCENE_TROUVER_DURATION,
    features: ['questionnaire', 'moteur', 'fiche'],
    scene: SceneTrouver,
  },
  {
    key: 'dossiers',
    icon: FolderOpen,
    features: ['cloud', 'pieces', 'suivi', 'tableauDeBord'],
    scene: SceneDossiers,
    duration: SCENE_DOSSIERS_DURATION,
  },
  {
    key: 'veille',
    icon: BellRing,
    features: ['alertes', 'veille'],
    scene: SceneVeille,
    duration: DEMO_DURATION,
  },
] as const;

/* L’arête haute et basse de la section « L’application » : un filet orange qui
   s’éteint vers les bords, pour que la limite ne coupe pas la page en deux. */
const ARETE =
  'linear-gradient(to right, rgba(241,113,5,0) 0%, rgba(241,113,5,0.65) 28%, rgba(241,113,5,0.65) 72%, rgba(241,113,5,0) 100%)';

function Demo() {
  const { t } = useTranslation();
  const { ref, inView } = useInView(0.2);
  const [active, setActive] = useState(0);
  const [loop, setLoop] = useState(true);
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    if (prefersReducedMotion()) setLoop(false);
  }, []);

  // La scène active rejoue en boucle sur place ; elle ne change qu'au clic d'un onglet.
  useEffect(() => {
    if (!inView || !loop) return;
    const t = setTimeout(() => setCycle((c) => c + 1), demoMs(CATEGORIES[active].duration));
    return () => clearTimeout(t);
  }, [inView, loop, active, cycle]);

  /* Onglet de navigateur quitté puis retrouvé : les rAF (compteurs) ont été
     suspendus pendant l'absence — on relance la scène depuis le début plutôt
     que d'afficher un état à moitié joué (ex. « 92 000 € » resté à 0). */
  useEffect(() => {
    const onVisible = () => {
      if (!document.hidden) setCycle((c) => c + 1);
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  const select = (i: number) => {
    setActive(i);
    setCycle((c) => c + 1);
  };

  const cat = CATEGORIES[active];
  const Scene = cat.scene;

  return (
    <section
      id="methode"
      ref={ref}
      className="relative scroll-mt-20 overflow-hidden"
      style={{ background: C.blue }}
    >
      {/* Une salle éclairée : deux nappes de bleu clair, au plafond et au sol, et
          une lumière blanche qui pose le titre. Le halo du haut est bleu et non
          orange : sur ce bleu profond, un orange diffus tourne au mauve terne. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[560px]"
        style={{
          background:
            'radial-gradient(62% 100% at 50% -12%, rgba(92,149,255,0.34), rgba(92,149,255,0) 70%)',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[420px]"
        style={{
          background:
            'radial-gradient(44% 100% at 50% 8%, rgba(255,255,255,0.12), rgba(255,255,255,0) 72%)',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[460px]"
        style={{
          background:
            'radial-gradient(74% 100% at 50% 110%, rgba(92,149,255,0.32), rgba(92,149,255,0) 70%)',
        }}
      />

      {/* Les deux arêtes : un trait orange d’un cheveu d’épaisseur, éteint sur les
          côtés. La limite avec le crème est nette, mais elle est dessinée. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{ background: ARETE }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px"
        style={{ background: ARETE }}
      />

      <div className="relative z-10 mx-auto max-w-6xl px-5 py-24 lg:px-8 lg:py-32">
        <Reveal>
          <SectionTitle dark title={t('Demo.titre')} />
        </Reveal>

        {/* Les trois missions, en onglets */}
        <Reveal delay={120}>
          {/* Couche de scroll séparée : overflow-x ne clipe plus les ombres des boutons */}
          <div className="-mx-5 mt-12 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:mx-0">
          <div
            role="tablist"
            aria-label={t('Demo.missions')}
            className="flex gap-2.5 px-5 pb-10 pt-1 lg:justify-center lg:px-0"
          >
            {CATEGORIES.map((c, i) => {
              const isActive = i === active;
              const Icon = c.icon;
              return (
                <button
                  key={c.key}
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => select(i)}
                  className={`flex shrink-0 items-center gap-2.5 rounded-full border px-5 py-3 text-[14px] font-semibold transition-all duration-300 ${
                    isActive
                      ? 'shadow-[0_12px_30px_-10px_rgba(241,113,5,0.6)]'
                      : 'hover:-translate-y-0.5 hover:border-[#f17105] hover:text-[#222b35] hover:shadow-[0_8px_22px_-12px_rgba(241,113,5,0.4)]'
                  }`}
                  style={
                    isActive
                      ? { background: C.orange, color: '#fff', borderColor: C.orange }
                      : { background: C.card, color: C.inkSoft, borderColor: C.border }
                  }
                >
                  <Icon
                    className="h-[18px] w-[18px] shrink-0"
                    style={{ color: isActive ? '#fff' : C.inkFaint }}
                    strokeWidth={2}
                  />
                  {t(`Demo.categories.${c.key}.onglet`)}
                </button>
              );
            })}
          </div>
          </div>
        </Reveal>

        <Reveal delay={200}>
          {/* minmax(0,…) : la colonne ignore la largeur intrinsèque des textes nowrap des scènes */}
          <div className="mt-10 grid grid-cols-1 gap-10 lg:mt-14 lg:grid-cols-[400px_minmax(0,1fr)] lg:items-start lg:gap-14">
            {/* Le texte : titre, fonctionnalités cochées, appel à l’action */}
            <div key={cat.key} className="fade-up">
              <h3 className="font-serif text-[clamp(1.65rem,3vw,2.1rem)] leading-[1.2] tracking-[-0.01em] text-white">
                {t(`Demo.categories.${cat.key}.titre`)}
              </h3>
              <ul className="mt-7 space-y-4">
                {cat.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <span
                      className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full"
                      style={{ background: 'rgba(252,137,5,0.22)' }}
                    >
                      <Check className="h-3 w-3" style={{ color: C.orangeVif }} strokeWidth={3} />
                    </span>
                    <span>
                      <span className="block text-[14.5px] font-semibold leading-snug text-white">
                        {t(`Demo.fonctionnalites.${feature}.titre`)}
                      </span>
                      <span className="mt-0.5 block text-[13.5px] leading-[1.6] text-white/75">
                        {t(`Demo.fonctionnalites.${feature}.texte`)}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
              <CtaButton variant="white" onClick={entrerDansMonumia} className="mt-9">
                {t('Commun.trouverLesAides')}
              </CtaButton>
            </div>

            {/* L’écran de l’application, posé sur un panneau teinté */}
            <div className="rounded-[2rem] p-3 sm:p-6 lg:p-8" style={{ background: C.paleOrange }}>
              {/* L’écoulement de la démonstration, comme la barre de lecture
                  d’une vidéo : elle repart à chaque tour de boucle (clé). */}
              <div
                aria-hidden="true"
                className="mb-3 h-1.5 overflow-hidden rounded-full sm:mb-4"
                style={{ background: 'rgba(34,43,53,0.12)' }}
              >
                {inView && (
                  <div
                    key={`${active}-${cycle}`}
                    className="h-full rounded-full"
                    style={{
                      width: 0,
                      ['--bar-w' as string]: '100%',
                      animation: `grow-bar ${demoMs(cat.duration)}ms linear forwards`,
                      background: `linear-gradient(90deg, ${C.orange}, ${C.orangeVif})`,
                    }}
                  />
                )}
              </div>

              <div
                className="overflow-hidden rounded-2xl border shadow-[0_30px_70px_-30px_rgba(10,54,157,0.35)]"
                style={{ background: '#fff', borderColor: C.border }}
              >
                <div className="flex items-center gap-1.5 border-b px-4 py-3" style={{ borderColor: C.border }}>
                  {['#e8dfce', '#e8dfce', '#e8dfce'].map((c, i) => (
                    <span key={i} className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />
                  ))}
                  <span
                    className="mx-auto flex items-center gap-1.5 rounded-full px-3.5 py-1 text-[11.5px] font-medium"
                    style={{ background: C.cream, color: C.inkFaint }}
                  >
                    <Lock className="h-3 w-3" strokeWidth={2} />
                    app.monumia.fr
                  </span>
                  {/* Contrepoids des trois pastilles, pour garder l’adresse centrée */}
                  <span aria-hidden="true" className="h-2.5 w-[42px]" />
                </div>
                <div className="h-[440px] p-5 sm:h-[450px] sm:p-7" style={{ background: C.cream }}>
                  {inView && (
                    <SceneStage key={`${active}-${cycle}`}>
                      <Scene />
                    </SceneStage>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   L’équipe — des cadres rectangulaires qui
   s’éclairent au passage.
   Règle du survol : rien ne se déplace sous le
   curseur (lumière, filtres et couleurs seulement),
   la zone de hover reste parfaitement stable.
   ──────────────────────────────────────────── */

/* `id` : clé des textes dans `Team.membres` (texte alternatif, cartel). */
const TEAM: Array<{
  id: 'paul' | 'felix' | 'henri';
  name: string;
  img: string;
  lift: string;
  factor: number;
  /* Recadrage propre au portrait : les sources sont carrées, le cadre est en 9/10.
     Un `scale` remonte les plans large à la même échelle de visage que les autres. */
  imgStyle?: CSSProperties;
}> = [
  {
    id: 'paul',
    name: 'Paul VACHERET',
    img: `${BASE}img/team-paul.jpg`,
    lift: 'md:mt-0',
    factor: 0.025,
  },
  {
    id: 'felix',
    name: 'Félix OLLIVIER',
    img: `${BASE}img/team-felix.jpg`,
    lift: 'md:mt-0',
    factor: 0.025,
  },
  {
    id: 'henri',
    name: 'Henri d’ANSELME',
    img: `${BASE}img/team-henri.jpg`,
    lift: 'md:mt-0',
    factor: 0.025,
    /* Source en 16/9, sujet à droite : la fenêtre 9/10 se cale sur lui, et le
       `scale` remonte son visage à l’échelle des trois autres portraits. */
    imgStyle: {
      objectPosition: '86% 50%',
      transform: 'scale(1.3)',
      transformOrigin: '72% 34%',
    },
  },
];

function Team() {
  const { t } = useTranslation();
  return (
    <section id="equipe" className="scroll-mt-20 px-5 py-20 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionTitle
            filet={false}
            title={t('Team.titre')}
            sub={t('Team.sousTitre')}
          /> 
        </Reveal>

        <div className="mx-auto mt-14 grid max-w-2xl gap-14 md:max-w-4xl md:grid-cols-3 md:gap-10 lg:max-w-5xl lg:gap-8">
          {TEAM.map((m, i) => (
            <ParallaxItem key={m.name} factor={m.factor}>
              <Reveal delay={i * 130}>
                <figure className={`group relative mx-auto max-w-[320px] ${m.lift}`}>
                  {/* Le portrait à nu : ni cadre crème ni lueur orange, la photo
                      occupe toute la largeur de la carte */}
                  <div className="relative overflow-hidden rounded-2xl shadow-[0_26px_50px_-30px_rgba(34,43,53,0.45)] transition-shadow duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:shadow-[0_36px_70px_-30px_rgba(34,43,53,0.45)]">
                    <img
                      src={m.img}
                      alt={t(`Team.membres.${m.id}.alt`)}
                      loading="lazy"
                      className="aspect-[9/10] w-full object-cover"
                      style={m.imgStyle}
                    />
                  </div>

                  {/* Le nom gravé sur le socle, sous le portrait */}
                  <figcaption
                    className="mt-3.5 text-center font-serif text-[15px] font-bold leading-snug"
                    style={{ color: C.blue }}
                  >
                    {m.name}
                  </figcaption>

                  {/* Le cartel, comme au musée */}
                  <div className="mt-6 text-center">
                    <p
                      className="mx-auto max-w-[300px] text-[13.5px] leading-[1.6]"
                      style={{ color: C.inkSoft }}
                    >
                      {t(`Team.membres.${m.id}.description`)}
                    </p>
                  </div>
                </figure>
              </Reveal>
            </ParallaxItem>
          ))}
        </div>

      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   Tarifs — trois offres, aucune surprise
   ──────────────────────────────────────────── */

type PlanFeature = { lead: string; detail?: string };

type Plan = {
  name: string;
  audience: string;
  punchline: string;
  intro: string[];
  features: PlanFeature[];
  footer: string;
  note?: string;
  cta: string;
  badge?: string;
  tone: 'cream' | 'highlight' | 'blue';
  /* Où mène le bouton. Découverte entre dans le parcours découverte, Veille et
     Multi-monuments passent par un courrier : rien ne s’achète en libre-service. */
  onClick: () => void;
};

/* Les offres, construites au rendu : leurs textes passent par la traduction. */
function plans(t: TFunction<'landing'>): Plan[] {
  return [
    {
      name: t('Tarifs.decouverte.nom'),
      audience: t('Tarifs.decouverte.public'),
      tone: 'cream',
      // « Trouver mes aides » : un CTA d'entrée comme les autres.
      onClick: entrerDansMonumia,
      punchline: t('Tarifs.decouverte.accroche'),
      intro: [t('Tarifs.decouverte.intro')],
      features: [
        { lead: t('Tarifs.decouverte.avantages.monument') },
        { lead: t('Tarifs.decouverte.avantages.detail') },
        { lead: t('Tarifs.decouverte.avantages.prix') },
        { lead: t('Tarifs.decouverte.avantages.checklist') },
        { lead: t('Tarifs.decouverte.avantages.documents') },
      ],
      footer: t('Tarifs.decouverte.resume'),
      note: t('Tarifs.decouverte.note'),
      cta: t('Commun.trouverMesAides'),
    },
    {
      name: t('Tarifs.veille.nom'),
      audience: t('Tarifs.veille.public'),
      tone: 'highlight',
      badge: t('Tarifs.veille.badge'),
      onClick: goToContact,
      punchline: t('Tarifs.veille.accroche'),
      intro: [t('Tarifs.veille.intro1'), t('Tarifs.veille.intro2')],
      features: [
        { lead: t('Tarifs.veille.avantages.projets') },
        { lead: t('Tarifs.veille.avantages.echeancier') },
        { lead: t('Tarifs.veille.avantages.aVenir') },
        { lead: t('Tarifs.veille.avantages.equipe') },
      ],
      footer: t('Tarifs.veille.resume'),
      cta: t('Tarifs.nousContacter'),
    },
    {
      name: t('Tarifs.multi.nom'),
      audience: t('Tarifs.multi.public'),
      tone: 'blue',
      badge: t('Tarifs.multi.badge'),
      onClick: goToContact,
      punchline: t('Tarifs.multi.accroche'),
      intro: [t('Tarifs.multi.intro1'), t('Tarifs.multi.intro2')],
      features: [
        { lead: t('Tarifs.multi.avantages.monuments') },
        { lead: t('Tarifs.multi.avantages.tableauDeBord') },
        { lead: t('Tarifs.multi.avantages.documents') },
      ],
      footer: t('Tarifs.multi.resume'),
      cta: t('Tarifs.nousContacter'),
    },
  ];
}

/* Une carte d’offre. Trois traitements visuels (crème, mise en avant, bleu),
   une seule structure : nom, punchline, mise en situation, bénéfices, résumé. */
function PlanCard({ plan }: { plan: Plan }) {
  const dark = plan.tone === 'blue';
  const highlight = plan.tone === 'highlight';

  const shell = dark
    ? 'relative flex h-full flex-col overflow-hidden rounded-2xl p-8 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_30px_66px_-28px_rgba(0,0,0,0.5)]'
    : highlight
      ? 'relative flex h-full flex-col rounded-2xl border-[1.5px] p-8 shadow-[0_24px_60px_-28px_rgba(241,113,5,0.45)] transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_34px_72px_-26px_rgba(241,113,5,0.6)]'
      : 'relative flex h-full flex-col rounded-2xl border p-8 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_24px_50px_-30px_rgba(0,0,0,0.25)]';

  const shellStyle: CSSProperties = dark
    ? { background: C.blue }
    : highlight
      ? { background: '#fff', borderColor: C.orange }
      : { background: C.cream, borderColor: C.border };

  const accent = dark ? C.orangeVif : highlight ? C.orange : C.blueLight;
  const titleColor = dark ? '#fff' : C.ink;
  const audienceColor = dark ? 'rgba(255,255,255,0.6)' : C.inkFaint;
  const punchColor = dark ? '#fff' : C.blue;
  const bodyColor = dark ? 'rgba(255,255,255,0.72)' : C.inkSoft;
  const leadColor = dark ? 'rgba(255,255,255,0.95)' : C.ink;
  const ruleColor = dark ? 'rgba(255,255,255,0.18)' : C.border;

  return (
    <div className={shell} style={shellStyle}>
      {plan.badge && (
        <span
          className={
            highlight
              ? 'absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-4 py-1.5 text-[12px] font-semibold uppercase tracking-[0.08em] text-white'
              : 'absolute right-6 top-6 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-white'
          }
          style={{ background: dark ? C.orangeVif : C.orange }}
        >
          {plan.badge}
        </span>
      )}

      <div className="relative flex h-full flex-col">
        <h3 className="font-serif text-[1.3rem] font-bold" style={{ color: titleColor }}>
          {plan.name}
        </h3>
        <p className="mt-1 text-[13.5px]" style={{ color: audienceColor }}>
          {plan.audience}
        </p>

        <p
          className="mt-6 font-serif text-[1.15rem] font-bold leading-[1.35]"
          style={{ color: punchColor }}
        >
          {plan.punchline}
        </p>

        {plan.intro.map((p) => (
          <p key={p} className="mt-4 text-[14.5px] leading-[1.7]" style={{ color: bodyColor }}>
            {p}
          </p>
        ))}

        <ul
          className="mt-7 flex-1 space-y-4 border-t pt-7"
          style={{ borderColor: ruleColor }}
        >
          {plan.features.map((f) => (
            <li key={f.lead} className="flex items-start gap-2.5">
              <Check className="mt-1 h-4 w-4 shrink-0" style={{ color: accent }} strokeWidth={2.2} />
              <span className="text-[14.5px] leading-[1.6]">
                <span className="font-semibold" style={{ color: leadColor }}>
                  {f.lead}
                </span>
                {f.detail && (
                  <span style={{ color: bodyColor }}> {f.detail}</span>
                )}
              </span>
            </li>
          ))}
        </ul>

        <p
          className="mt-7 border-t pt-5 text-[13.5px] font-semibold leading-[1.6]"
          style={{ borderColor: ruleColor, color: accent }}
        >
          {plan.footer}
        </p>

        {plan.note && (
          <p className="mt-3 text-[13px] italic leading-[1.6]" style={{ color: audienceColor }}>
            {plan.note}
          </p>
        )}

        <CtaButton
          variant={dark ? 'white' : highlight ? 'primary' : 'ghost'}
          onClick={plan.onClick}
          className="mt-7 w-full"
        >
          {plan.cta}
        </CtaButton>
      </div>
    </div>
  );
}

function Pricing() {
  const { t } = useTranslation();
  return (
    <section
      id="tarifs"
      className="scroll-mt-20 border-y px-5 py-20 lg:px-8 lg:py-24"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionTitle filet={false} title={t('Tarifs.titre')} />
        </Reveal>

        <div className="mt-14 grid items-stretch gap-6 lg:grid-cols-3">
          {plans(t).map((p, i) => (
            <Reveal key={p.name} delay={i * 120} className="h-full">
              <PlanCard plan={p} />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   FAQ — les vraies questions qu’on nous pose
   ──────────────────────────────────────────── */

function FaqItem({
  question,
  answer,
  defaultOpen = false,
}: {
  question: string;
  answer: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className="rounded-2xl border transition-shadow duration-300"
      style={{ background: C.card, borderColor: open ? 'rgba(241,113,5,0.4)' : C.border }}
    >
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
      >
        <span className="font-serif text-[1.05rem] font-bold leading-snug" style={{ color: C.ink }}>
          {question}
        </span>
        <ChevronDown
          className={`h-5 w-5 shrink-0 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
          style={{ color: C.orange }}
          strokeWidth={2}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out"
        style={{ gridTemplateRows: open ? '1fr' : '0fr' }}
      >
        <div className="overflow-hidden">
          <p className="px-6 pb-6 text-[15px] leading-[1.75]" style={{ color: C.inkSoft }}>
            {answer}
          </p>
        </div>
      </div>
    </div>
  );
}

/* Les questions de la FAQ, dans l'ordre d'affichage : clés de `Faq.questions`. */
const QUESTIONS_FAQ = [
  'public',
  'nonProtege',
  'financements',
  'informatique',
  'depot',
  'prix',
  'sources',
] as const;

function Faq() {
  const { t } = useTranslation();
  return (
    <section id="faq" className="scroll-mt-20 px-5 py-20 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-3xl">
        <Reveal>
          <SectionTitle
            title={t('Faq.titre')}
            sub={
              <Trans
                t={t}
                i18nKey="Faq.contact"
                components={{
                  lien: (
                    <a
                      href="mailto:contact@monumia.fr"
                      className="underline underline-offset-4 transition-colors duration-200 hover:text-[#0a369d]"
                      style={{ color: C.orange }}
                    />
                  ),
                }}
              />
            }
          />
        </Reveal>
        <div className="mt-12 space-y-4">
          {QUESTIONS_FAQ.map((id, i) => (
            <Reveal key={id} delay={i * 60}>
              <FaqItem
                question={t(`Faq.questions.${id}.question`)}
                answer={t(`Faq.questions.${id}.reponse`)}
                defaultOpen={i === 0}
              />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   CTA final + pied de page
   ──────────────────────────────────────────── */

function FinalCta() {
  const { t } = useTranslation();
  return (
    <section className="px-5 pb-20 lg:px-8 lg:pb-24">
      <Reveal>
        <div
          className="relative mx-auto max-w-4xl overflow-hidden rounded-3xl px-7 py-16 text-center shadow-[0_30px_70px_-35px_rgba(10,54,157,0.55)] sm:px-16 sm:py-20"
          style={{ background: C.blue }}
        >
          <div className="relative">
            <h2 className="mx-auto max-w-3xl font-serif text-[clamp(1.9rem,3.6vw,2.5rem)] leading-[1.2] text-white">
              {t('FinalCta.titre')}
            </h2>
            <div className="mt-9">
              <CtaButton onClick={entrerDansMonumia}>{t('Commun.trouverLesAides')}</CtaButton>
            </div>
            <p className="mt-5 text-[13px] uppercase tracking-[0.12em] text-white/60">
              {t('FinalCta.reassurance')}
            </p>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="border-t px-5 pb-10 pt-14 lg:px-8" style={{ background: C.card, borderColor: C.border }}>
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5">
              <Clover className="h-6 w-6" strokeWidth={10} style={{ color: C.orange }} />
              <span className="font-serif text-[1.25rem] font-bold" style={{ color: C.blue }}>
                Monumia
              </span>
            </div>
            <p className="mt-4 font-serif text-[15px]" style={{ color: C.ink }}>
              {t('Footer.slogan')}
            </p>
            <p className="mt-3 max-w-xs font-serif text-[14px] italic leading-[1.7]" style={{ color: C.inkSoft }}>
              {t('Footer.citation')}
            </p>
            <p className="mt-3 text-[14px]" style={{ color: C.inkFaint }}>
              {t('Footer.concuEnFrance')}
            </p>
            <SelecteurLangue className="mt-5 inline-flex" />
          </div>

          <nav aria-label={t('Footer.planDuSite')}>
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.inkFaint }}>
              {t('Footer.decouvrir')}
            </p>
            <ul className="mt-4 space-y-2.5">
              {[
                ['#methode', t('Navigation.methode')],
                ['#equipe', t('Navigation.equipe')],
                ['#tarifs', t('Navigation.tarifs')],
                ['#faq', t('Navigation.questionsFrequentes')],
              ].map(([href, label]) => (
                <li key={href}>
                  <a
                    href={href}
                    className="text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                    style={{ color: C.inkSoft }}
                  >
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.inkFaint }}>
              {t('Footer.contact')}
            </p>
            <ul className="mt-4 space-y-2.5">
              <li>
                <a
                  href="mailto:contact@monumia.fr"
                  className="inline-flex items-center gap-2 text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.inkSoft }}
                >
                  <Mail className="h-4 w-4" strokeWidth={1.6} />
                  contact@monumia.fr
                </a>
              </li>
              <li>
                <a
                  href={`${BASE}cgu#mentions-legales`}
                  className="text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.inkSoft }}
                >
                  {t('Footer.mentionsLegales')}
                </a>
              </li>
              <li>
                <a
                  href={`${BASE}cgu`}
                  className="text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.inkSoft }}
                >
                  {t('Footer.cgu')}
                </a>
              </li>
              <li>
                <a
                  href={`${BASE}confidentialite`}
                  className="text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.inkSoft }}
                >
                  {t('Footer.confidentialite')}
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div
          className="mt-12 flex flex-col items-center justify-between gap-3 border-t pt-6 sm:flex-row"
          style={{ borderColor: C.border }}
        >
          <p className="text-[13px]" style={{ color: C.inkFaint }}>
            {t('Footer.droits', { annee: new Date().getFullYear() })}
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ────────────────────────────────────────────
   Page
   ──────────────────────────────────────────── */

export function LandingPage() {
  const { t } = useTranslation();
  return (
    <div className="font-sans" style={{ background: C.cream, color: C.ink }}>
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold"
        style={{ color: C.blue }}
      >
        {t('LandingPage.allerAuContenu')}
      </a>
      <Header />
      <main id="contenu">
        <Hero />
        <Constat />
        <Demo />
        <RapportSenat />
        <Team />
        <Pricing />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
