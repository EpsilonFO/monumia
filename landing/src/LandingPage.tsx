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
  Radar,
  Search,
  Sparkles,
} from 'lucide-react';

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

/* Semis de fleurs Monumia en filigrane — réservé aux fonds bleus */
function Tracery({
  color,
  opacity = 0.035,
  size = 200,
  className = '',
}: {
  color: string;
  opacity?: number;
  size?: number;
  className?: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      style={{
        backgroundColor: color,
        opacity,
        WebkitMaskImage: LOGO_URL,
        maskImage: LOGO_URL,
        /* `round repeat` = round en X, repeat en Y. En X, les tuiles sont
           ajustées pour qu'un nombre entier de fleurs tienne sur la largeur :
           aucune fleur coupée sur les côtés. En Y, taille figée et ancrée en
           haut : la hauteur d'un bloc peut changer (ex. changement d'onglet de
           la démo) sans étirer les quadrilobes. La largeur ne variant qu'au
           redimensionnement de la fenêtre, le motif reste stable à l'usage. */
        WebkitMaskRepeat: 'round repeat',
        maskRepeat: 'round repeat',
        WebkitMaskSize: `${size}px ${size}px`,
        maskSize: `${size}px ${size}px`,
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
  return <>{val.toLocaleString('fr-FR')}</>;
}

function goToApp() {
  window.location.href = APP_URL;
}

/* Parcours DÉCOUVERTE : le visiteur décrit son monument et obtient son
   diagnostic AVANT d'avoir un compte — le wizard monument de l'app est
   désormais public, et l'inscription n'arrive qu'à la fin. C'est la
   destination des CTA « Découvrir mes financements mobilisables », qui
   menaient jusqu'ici à la liste d'attente. */
function goToDecouverte() {
  window.location.href = `${APP_URL}/app/monuments/nouveau`;
}

/* Page d'inscription à la liste d'attente : route servie par le fallback SPA de
   nginx (sous BASE — '/lancement' en prod, '/landing/lancement' en beta). */
export const SIGNUP_PATH = `${BASE}lancement`;
function goToSignup() {
  window.location.href = SIGNUP_PATH;
}

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
  variant?: 'primary' | 'ghost' | 'white';
  onClick?: () => void;
  className?: string;
}) {
  const base =
    'group inline-flex items-center justify-center gap-2.5 rounded-full px-7 py-3.5 text-[15px] font-semibold transition-all duration-300';
  const styles: Record<string, CSSProperties> = {
    primary: { background: C.orange, color: '#fff' },
    ghost: { background: 'transparent', color: C.blue, border: `1.5px solid ${C.blue}40` },
    white: { background: '#fff', color: C.blue },
  };
  const hover: Record<string, string> = {
    primary: 'hover:shadow-[0_10px_30px_-8px_rgba(241,113,5,0.55)] hover:-translate-y-0.5',
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
}: {
  title: ReactNode;
  sub?: ReactNode;
  dark?: boolean;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <h2
        className="font-serif text-[clamp(1.9rem,3.4vw,2.4rem)] leading-[1.2] tracking-[-0.01em]"
        style={{ color: dark ? '#fff' : C.ink }}
      >
        {title}
      </h2>
      <div
        className="mx-auto mt-5 h-[3px] w-12 rounded-full"
        style={{ background: dark ? C.orangeVif : C.orange }}
      />
      {sub && (
        <p
          className="mx-auto mt-5 max-w-2xl text-[17px] font-medium leading-[1.65]"
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

function Header() {
  const [scrolled, setScrolled] = useState(false);
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
    { href: '#methode', label: 'Comment ça marche' },
    { href: '#tarifs', label: 'Tarifs' },
    { href: '#faq', label: 'Questions' },
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
        <a href="#" className="flex items-center gap-2.5" aria-label="Monumia, retour en haut de page">
          <Clover className="h-7 w-7" strokeWidth={10} style={{ color: C.orange }} />
          <span className="font-serif text-[1.35rem] font-bold tracking-[-0.01em]" style={{ color: C.blue }}>
            Monumia
          </span>
        </a>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Navigation principale">
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
          <button
            onClick={goToDecouverte}
            className="whitespace-nowrap rounded-full px-5 py-2.5 text-[14px] font-semibold text-white transition-all duration-300 hover:shadow-[0_8px_20px_-6px_rgba(241,113,5,0.55)]"
            style={{ background: C.orange }}
          >
            {/* Libellé court sous 640 px : l'intitulé complet ferait déborder l'en-tête */}
            <span className="sm:hidden">Découvrir</span>
            <span className="hidden sm:inline">Découvrir mes financements mobilisables</span>
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
   Héros — la promesse + le trésor
   ──────────────────────────────────────────── */

/* La carte d’estimation compacte : l’essentiel des chiffres, posé devant la photo */
function EstimationCard() {
  const { ref, inView } = useInView(0.3);
  return (
    <div
      ref={ref}
      className="rounded-2xl border p-5 shadow-[0_28px_60px_-22px_rgba(10,54,157,0.38)] sm:p-6"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11.5px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.blueLight }}>
          Votre estimation
        </span>
        <span
          className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
          style={{ background: C.paleBlue, color: C.blueLight }}
        >
          Exemple
        </span>
      </div>

      <h3 className="mt-2.5 font-serif text-[1.15rem] font-bold leading-snug" style={{ color: C.ink }}>
        Château de Paley
      </h3>
      <p className="text-[12.5px]" style={{ color: C.inkFaint }}>
        Restauration de la façade · Seine-et-Marne
      </p>

      <p className="mt-4 text-[11.5px] font-medium uppercase tracking-[0.1em]" style={{ color: C.inkFaint }}>
        Aides mobilisables estimées
      </p>
      <p className="mt-1.5 font-serif text-[1.6rem] font-bold leading-none" style={{ color: C.blue }}>
        {inView ? <CountUp to={420000} /> : '0'} €{' '}
        <span className="text-[1.05rem] font-normal" style={{ color: C.inkFaint }}>
          à
        </span>{' '}
        {inView ? <CountUp to={680000} duration={1600} /> : '0'} €
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
        12 aides identifiées · DRAC, Région, Fondation du patrimoine
      </p>
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden px-5 pb-24 pt-16 sm:pt-20 lg:px-8 lg:pb-28 lg:pt-20">
      <div
        className="pointer-events-none absolute -top-32 right-[-12%] h-[460px] w-[460px] rounded-full blur-[130px]"
        style={{ background: 'rgba(241, 113, 5, 0.1)' }}
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12">
        <div>

          <h1
            className="fade-up mt-6 font-serif text-[clamp(1.85rem,4.2vw,2.7rem)] leading-[1.13] tracking-[-0.015em]"
            style={{ color: C.ink, animationDelay: '0.15s' }}
          >
            Monumia <span style={{ color: C.blue }}>identifie </span>
            les financements pour{' '}
            <span style={{ color: C.orange }}>restaurer</span>,{' '}
            <span style={{ color: C.orange }}>ouvrir</span> et{' '}
            <span style={{ color: C.orange }}>animer</span> votre monument.
          </h1>

          <p
            className="fade-up mt-7 max-w-xl text-[17px] font-medium italic leading-[1.7] sm:text-[18px]"
            style={{ color: C.inkSoft, animationDelay: '0.3s' }}
          >
            « Au service de celles et ceux qui font vivre le patrimoine bâti. »
          </p>

          <div className="fade-up mt-9 flex flex-wrap items-center gap-4" style={{ animationDelay: '0.45s' }}>
            <CtaButton onClick={goToDecouverte}>Découvrir mes financements mobilisables</CtaButton>
            <a
              href="mailto:contact@monumia.fr"
              className="group inline-flex items-center gap-2.5 rounded-full py-2 pl-2 pr-6 text-[15px] font-semibold transition-all duration-300 hover:-translate-y-0.5 hover:border-[#0a369d] hover:shadow-[0_10px_28px_-14px_rgba(10,54,157,0.45)]"
              style={{ border: `1.5px solid ${C.blue}33`, color: C.blue, background: C.card }}
            >
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full"
                style={{ background: C.paleBlue }}
              >
                <Mail className="h-4 w-4 transition-transform duration-300 group-hover:-rotate-6" strokeWidth={1.8} />
              </span>
              Nous contacter
            </a>
          </div>
        </div>

        <div
          className="fade-up relative mx-auto mt-12 w-full max-w-[460px] lg:mt-0 lg:max-w-none"
          style={{ animationDelay: '0.4s' }}
        >
          {/* Trévarez sous son arche, pleine colonne : ce pour quoi l’on travaille */}
          <div
            className="overflow-hidden rounded-b-2xl rounded-t-[10rem] border shadow-[0_30px_70px_-32px_rgba(34,43,53,0.4)]"
            style={{ borderColor: C.border }}
          >
            <img
              src={`${BASE}img/paley.jpg`}
              alt="Le château de Trévarez, en Finistère, monument historique en cours de rénovation, au bout de son allée d’arbres"
              className="aspect-[4/5] w-full object-cover"
              style={{ objectPosition: '50% 0%' }}
            />
          </div>

          {/* Les chiffres, posés devant le monument */}
          <div className="relative z-10 mx-auto -mt-20 w-[92%] sm:absolute sm:-bottom-10 sm:-left-6 sm:mx-0 sm:mt-0 sm:w-[min(350px,76%)] lg:-left-10">
            <EstimationCard />
          </div>

          {/* Mini-carte d’alerte flottante : la veille incarnée */}
          <div
            className="absolute -bottom-5 -right-2 hidden w-[240px] items-start gap-3 rounded-xl border p-3.5 pl-5 shadow-[0_18px_40px_-16px_rgba(34,43,53,0.3)] [animation:floaty_7s_ease-in-out_infinite] sm:flex"
            style={{ background: C.card, borderColor: C.border }}
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: C.paleOrange }}>
              <BellRing className="h-4.5 w-4.5" style={{ color: C.orange }} strokeWidth={1.8} />
            </span>
            <span>
              <span className="block text-[11px] font-semibold uppercase tracking-[0.1em]" style={{ color: C.orange }}>
                Alerte ouverture
              </span>
              <span className="mt-0.5 block text-[12.5px] leading-snug" style={{ color: C.ink }}>
                La Fondation du patrimoine ouvre ses candidatures
              </span>
            </span>
          </div>
        </div>
      </div>
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

/* Scène 1 — trouver ses financements : questionnaire, puis résultats du moteur */
function SceneTrouver() {
  const rows: Array<[string, string]> = [
    ['Aide de l’État (DRAC) · restauration', '15 à 40 %'],
    ['Aide de la Région · patrimoine', 'jusqu’à 25 000 €'],
    ['Fondation du patrimoine', 'Réduction d’impôt'],
    ['Mécénat d’entreprise', 'Sur dossier'],
  ];
  return (
    <div className="relative h-full">
      {/* Écran 1 : le questionnaire de qualification */}
      <div className="absolute inset-0 flex flex-col" style={{ animation: 'screen-out 0.45s 5.8s ease forwards' }}>
        <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '0.1s' }}>
          <span className="text-[11.5px] font-semibold uppercase tracking-[0.16em]" style={{ color: C.orange }}>
            Question 5 <span style={{ color: C.inkFaint }}>sur 12</span>
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
          Quelles entités, autour du monument, pourraient déposer une demande d’aide ?
        </h4>
        <p
          className="demo-pop mt-3 flex gap-2 rounded-lg border-l-2 bg-white p-3 text-[12.5px] leading-snug"
          style={{ borderColor: C.blueLight, color: C.inkSoft, animationDelay: '0.7s' }}
        >
          <Info className="mt-[2px] h-3.5 w-3.5 shrink-0" style={{ color: C.blue }} strokeWidth={2} />
          <span>Le porteur n’est pas forcément le propriétaire du monument.</span>
        </p>
        <div className="mt-3.5 flex flex-wrap gap-2">
          <DemoChip appear={1.1}>Particulier (personne physique)</DemoChip>
          <DemoChip appear={1.25}>SCI</DemoChip>
          <DemoChip appear={1.4} select={2.4} demoId="chip-association">
            Association loi 1901
          </DemoChip>
        </div>

        <div className="demo-pop mt-6" style={{ animationDelay: '3s' }}>
          <h4 className="font-serif text-[1.1rem] font-bold leading-snug sm:text-[1.2rem]" style={{ color: C.ink }}>
            Les travaux portent-ils sur les parties protégées du monument (celles visées par le
            classement ou l’inscription) ?
          </h4>
          <div className="mt-3 flex flex-wrap gap-2">
            <DemoChip appear={3.3} select={4.5} demoId="chip-parties-protegees">
              Oui
            </DemoChip>
            <DemoChip appear={3.45}>Non</DemoChip>
          </div>
        </div>

        <div
          className="demo-pop mt-auto flex items-center gap-2.5 rounded-xl border bg-white p-3"
          style={{ borderColor: C.border, animationDelay: '5s' }}
        >
          <Sparkles className="h-4 w-4 shrink-0" style={{ color: C.orange }} strokeWidth={1.8} />
          <span className="text-[12.5px]" style={{ color: C.inkSoft }}>
            Monumia cherche toutes les aides pour votre projet…
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
            11 aides correspondent à votre projet
          </span>
          <span
            className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
            style={{ background: C.paleBlue, color: C.blueLight }}
          >
            Exemple
          </span>
        </div>

        <div className="mt-4 space-y-2.5">
          {rows.map(([name, amount], i) => (
            <div
              key={name}
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
                {name}
              </span>
              <span className="shrink-0 text-[12px] font-semibold" style={{ color: C.inkSoft }}>
                {amount}
              </span>
            </div>
          ))}
        </div>

        <div className="demo-pop mt-4" style={{ animationDelay: '7.9s' }}>
          <div className="flex items-center justify-between text-[12px]">
            <span className="font-medium" style={{ color: C.inkSoft }}>
              Vos chances d’obtenir ces aides
            </span>
            <span className="font-semibold" style={{ color: C.orange }}>
              élevées
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
            Aides estimées
          </span>
          <span className="font-serif text-[1.2rem] font-bold leading-none" style={{ color: C.orange }}>
            <CountUp to={92000} delay={demoMs(8700)} duration={demoMs(1300)} /> –{' '}
            <CountUp to={140000} delay={demoMs(8700)} duration={demoMs(1700)} /> €
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
              Fiche de l’aide
            </span>
          </div>
          <ul className="mt-2 space-y-1 text-[11.5px] leading-snug" style={{ color: C.inkSoft }}>
            <li>Conditions et montants expliqués</li>
            <li>La personne à contacter</li>
            <li>La liste des 12 documents à fournir</li>
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
  const items: Array<[string, string]> = [
    ['Fondation du patrimoine · les candidatures ouvrent', '15 mars'],
    ['Aide de l’État · dernier jour pour déposer', '2 avril'],
    ['Région · nouvelle aide pour le patrimoine', '30 juin'],
  ];
  return (
    <div className="relative flex h-full flex-col">
      <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '0.1s' }}>
        <span className="font-serif text-[1.05rem] font-bold" style={{ color: C.ink }}>
          Vos dates à retenir
        </span>
        <span
          className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
          style={{ background: C.paleBlue, color: C.blueLight }}
        >
          Exemple
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
        Alerte activée — vous serez prévenu à temps
      </p>

      <div
        className="demo-pop mt-4 flex items-start gap-2.5 rounded-xl p-3.5 text-[12.5px] leading-snug"
        style={{ background: C.paleOrange, color: C.ink, animationDelay: '5.2s' }}
      >
        <Radar className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.orange }} strokeWidth={1.8} />
        Notre conseil : isoler votre manoir débloquerait de nouvelles aides de la Région.
      </div>

      <div
        className="toast-in mt-auto flex items-start gap-2.5 rounded-xl border bg-white p-3 shadow-[0_12px_28px_-14px_rgba(34,43,53,0.35)]"
        style={{ borderColor: C.border, animationDelay: '7.2s' }}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: C.paleOrange }}>
          <BellRing className="h-4 w-4" style={{ color: C.orange }} strokeWidth={1.8} />
        </span>
        <span>
          <span className="block text-[10.5px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orange }}>
            Alerte Monumia
          </span>
          <span className="mt-0.5 block text-[12.5px] leading-snug" style={{ color: C.ink }}>
            Nouvelle aide pour votre manoir
          </span>
        </span>
        <span
          className="ml-auto flex shrink-0 items-center gap-1.5 self-center rounded-full px-2.5 py-1 text-[10.5px] font-medium"
          style={{ background: C.paleBlue, color: C.blue }}
        >
          <HeartHandshake className="h-3 w-3" strokeWidth={2} />
          Mécénat
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
  /* Tous les projets en cours (écran 1). Le premier est celui qu'on ouvre. */
  const enCours: Array<[string, string, string]> = [
    ['Restauration de la toiture', 'Dossier en préparation', '70%'],
    ['Vitraux de la chapelle', 'Recherche d’aides en cours', '40%'],
    ['Mise aux normes électriques', 'À démarrer', '15%'],
  ];
  /* Les pièces du dossier (écran 2). `at` = instant où la coche apparaît. */
  const pieces: Array<[string, number]> = [
    ['Devis des artisans', 4.9],
    ['Photos de la toiture', 5.4],
    ['Plan de financement', 7.45],
    ['Avis de l’Architecte des Bâtiments de France', 8.75],
  ];
  return (
    <div className="relative h-full">
      {/* Écran 1 : le tableau de bord de tous les projets en cours */}
      <div className="absolute inset-0 flex flex-col" style={{ animation: 'screen-out 0.45s 3.6s ease forwards' }}>
        <div className="demo-pop flex items-center justify-between" style={{ animationDelay: '0.1s' }}>
          <span className="font-serif text-[1.05rem] font-bold" style={{ color: C.ink }}>
            Vos projets en cours
          </span>
          <span
            className="rounded-full px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
            style={{ background: C.paleBlue, color: C.blueLight }}
          >
            Exemple
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
                Restauration de la toiture
              </span>
              <span className="block truncate text-[11.5px]" style={{ color: C.inkFaint }}>
                Documents du projet · partagés avec votre architecte
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
          Télécharger le dossier complet
        </div>

        <div
          className="toast-in mt-3 flex items-center gap-2.5 rounded-xl border bg-white p-2.5"
          style={{ borderColor: 'rgba(241,113,5,0.4)', animationDelay: '11.05s' }}
        >
          <CheckCircle2 className="h-4.5 w-4.5 shrink-0" style={{ color: C.orange }} strokeWidth={2} />
          <span className="text-[12.5px] leading-snug" style={{ color: C.ink }}>
            Dossier complet, prêt à envoyer
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

type Feature = [string, string];

const CATEGORIES: Array<{
  key: string;
  tab: string;
  icon: typeof Search;
  title: string;
  sub: string;
  features: Feature[];
  scene: () => ReactNode;
  duration: number;
}> = [
  {
    key: 'trouver',
    tab: 'Trouver vos financements',
    icon: Search,
    title: 'Trouvez tous vos financements',
    sub: 'Le premier moteur de recherche dédié au financement du patrimoine.',
    duration: SCENE_TROUVER_DURATION,
    features: [
      [
        'Un questionnaire simple',
        'Quelques questions sur votre lieu et votre projet. Plus vos réponses sont précises, plus les résultats le sont.',
      ],
      [
        'Un moteur de recherche d’aides',
        'Vos réponses sont croisées avec l’ensemble des financements existants, pour ne remonter que les aides auxquelles vous êtes réellement éligible.',
      ],
      [
        'Une estimation de vos aides',
        'Une fourchette de ce que vous pouvez obtenir et de votre niveau d’éligibilité, évaluée prudemment.',
      ],
      [
        'Une fiche claire pour chaque aide',
        'Conditions, montants, documents à fournir et personne à contacter : le mode d’emploi de chaque financement.',
      ],
    ],
    scene: SceneTrouver,
  },
  {
    key: 'dossiers',
    tab: 'Monter vos dossiers',
    icon: FolderOpen,
    title: 'Montez et pilotez vos dossiers',
    sub: 'De la première pièce au dossier déposé, sans rien oublier.',
    features: [
      [
        'Tous vos documents au même endroit',
        'Devis, photos, plans : tout est rangé, classé et partageable. Invitez votre architecte ou vos artisans à y travailler avec vous.',
      ],
      [
        'La liste exacte des documents à fournir',
        'Pour chaque aide, Monumia vous donne la liste précise des pièces demandées. Une fois tout réuni, téléchargez le dossier complet, prêt à envoyer.',
      ],
      [
        'Le suivi de chaque demande',
        'Suivez l’état de chaque demande, de « à préparer » à « accordé ». Vous savez toujours où vous en êtes.',
      ],
      [
        'Tous vos projets d’un seul regard',
        'Une vue d’ensemble de vos projets et de leur avancement. Menez plusieurs restaurations de front sans rien perdre de vue.',
      ],
    ],
    scene: SceneDossiers,
    duration: SCENE_DOSSIERS_DURATION,
  },
  {
    key: 'veille',
    tab: 'Ne rien rater',
    icon: BellRing,
    title: 'Ne ratez plus jamais une opportunité',
    sub: 'Une veille permanente sur tous les financements de votre patrimoine.',
    features: [
      [
        'Des alertes avant chaque échéance',
        'Monumia vous prévient à l’approche de chaque date limite qui vous concerne, à temps pour déposer.',
      ],
      [
        'Une veille sur vos financements',
        'Au-delà de vos projets en cours, Monumia identifie en continu les aides auxquelles votre lieu donne droit.',
      ],
      [
        'Les financements liés à vos travaux',
        'Pour chaque projet, Monumia vous indique les aides associées, y compris celles que vous ne connaissez pas encore.',
      ],
      [
        'Toutes vos échéances réunies',
        'Vos dates clés rassemblées dans un seul calendrier, visibles d’un coup d’œil.',
      ],
      [
        'L’annuaire des fondations et mécènes',
        'La fiche complète de chaque fondation : dates, modalités, contacts.',
      ],
    ],
    scene: SceneVeille,
    duration: DEMO_DURATION,
  },
];

/* L’arête haute et basse de la section « L’application » : un filet orange qui
   s’éteint vers les bords, pour que la limite ne coupe pas la page en deux. */
const ARETE =
  'linear-gradient(to right, rgba(241,113,5,0) 0%, rgba(241,113,5,0.65) 28%, rgba(241,113,5,0.65) 72%, rgba(241,113,5,0) 100%)';

function Demo() {
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
      <Tracery color="#ffffff" opacity={0.03} size={720} />

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
          <SectionTitle dark title="Trois usages en un seul outil" />
        </Reveal>

        {/* Les trois missions, en onglets */}
        <Reveal delay={120}>
          {/* Couche de scroll séparée : overflow-x ne clipe plus les ombres des boutons */}
          <div className="-mx-5 mt-12 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:mx-0">
          <div
            role="tablist"
            aria-label="Les trois missions de Monumia"
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
                  {c.tab}
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
                {cat.title}
              </h3>
              <p className="mt-3 text-[16px] font-medium leading-[1.6] text-white/75">
                {cat.sub}
              </p>
              <ul className="mt-7 space-y-4">
                {cat.features.map(([name, desc]) => (
                  <li key={name} className="flex items-start gap-3">
                    <span
                      className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full"
                      style={{ background: 'rgba(252,137,5,0.22)' }}
                    >
                      <Check className="h-3 w-3" style={{ color: C.orangeVif }} strokeWidth={3} />
                    </span>
                    <span>
                      <span className="block text-[14.5px] font-semibold leading-snug text-white">
                        {name}
                      </span>
                      <span className="mt-0.5 block text-[13.5px] leading-[1.6] text-white/75">
                        {desc}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
              <CtaButton variant="white" onClick={goToDecouverte} className="mt-9">
                Découvrir mes financements mobilisables
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
   L’équipe — trois cadres rectangulaires qui
   s’éclairent au passage.
   Règle du survol : rien ne se déplace sous le
   curseur (lumière, filtres et couleurs seulement),
   la zone de hover reste parfaitement stable.
   ──────────────────────────────────────────── */

const TEAM: Array<{
  name: string;
  img: string;
  alt: string;
  desc: string;
  lift: string;
  factor: number;
  /* Recadrage propre au portrait : les sources sont carrées, le cadre est en 9/10.
     Un `scale` remonte les plans large à la même échelle de visage que les autres. */
  imgStyle?: CSSProperties;
}> = [
  {
    name: 'Félix OLLIVIER',
    img: `${BASE}img/team-felix.jpg`,
    alt: 'Portrait de Félix, cofondateur de Monumia',
    desc: 'Co-fondateur, chargé de la conception et du développement de la plateforme.',
    lift: 'md:mt-0',
    factor: 0.025,
  },
  {
    name: 'Paul VACHERET',
    img: `${BASE}img/team-paul.jpg`,
    alt: 'Portrait de Paul, cofondateur de Monumia',
    desc: 'Co-fondateur, chargé de la vision et du développement commercial.',
    lift: 'md:mt-0',
    factor: 0.025,
  },
  {
    name: 'Ismaël MURAT EL HAKIM',
    img: `${BASE}img/team-ismael.jpg`,
    alt: 'Portrait d’Ismaël, propriétaire gestionnaire du château de Paley',
    desc: 'Associé, propriétaire gestionnaire du château de Paley.',
    lift: 'md:mt-0',
    factor: 0.025,
    /* Plan large et sujet décentré à gauche : `objectPosition` colle la fenêtre
       sur le bord gauche de la source, `transformOrigin` la resserre autour de
       lui, `scale` remonte son visage à l’échelle des deux autres portraits. */
    imgStyle: {
      objectPosition: '0% 50%',
      transform: 'scale(1.42)',
      transformOrigin: '25% 32%',
    },
  },
];

function Team() {
  return (
    <section id="equipe" className="scroll-mt-20 px-5 py-20 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-5xl">
        <Reveal>
          <SectionTitle
            title="Les visages derrière Monumia"
            sub="Notre conviction : le patrimoine mérite des outils à la hauteur de son histoire et de ceux qui s'y engagent."
          />
        </Reveal>

        <div className="mx-auto mt-14 grid max-w-2xl gap-14 md:max-w-4xl md:grid-cols-3 md:gap-8">
          {TEAM.map((m, i) => (
            <ParallaxItem key={m.name} factor={m.factor}>
              <Reveal delay={i * 130}>
                <figure className={`group relative mx-auto max-w-[280px] ${m.lift}`}>
                  {/* Le cadre : pierre crème, portrait en rectangle adouci */}
                  <div
                    className="relative rounded-2xl border p-3 shadow-[0_26px_50px_-30px_rgba(34,43,53,0.45)] transition-shadow duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:shadow-[0_36px_70px_-30px_rgba(241,113,5,0.4)]"
                    style={{ background: C.card, borderColor: C.border }}
                  >
                    <div className="relative overflow-hidden rounded-xl">
                      <img
                        src={m.img}
                        alt={m.alt}
                        loading="lazy"
                        className="aspect-[9/10] w-full object-cover"
                        style={m.imgStyle}
                      />
                      {/* La lueur de bougie qui monte du seuil */}
                      <span
                        aria-hidden="true"
                        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-[1100ms] ease-out group-hover:opacity-100"
                        style={{
                          background:
                            'radial-gradient(120% 78% at 50% 102%, rgba(252,137,5,0.3), rgba(252,137,5,0.1) 45%, rgba(252,137,5,0) 72%)',
                        }}
                      />
                    </div>

                    {/* Le nom gravé sur le socle, sous le portrait */}
                    <figcaption
                      className="mt-3.5 text-center font-serif text-[15px] font-bold leading-snug"
                      style={{ color: C.blue }}
                    >
                      {m.name}
                    </figcaption>
                  </div>

                  {/* Le cartel, comme au musée */}
                  <div className="mt-6 text-center">
                    <p
                      className="mx-auto max-w-[260px] text-[13.5px] italic leading-[1.6]"
                      style={{ color: C.inkSoft }}
                    >
                      {m.desc}
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

function Pricing() {
  return (
    <section
      id="tarifs"
      className="scroll-mt-20 border-y px-5 py-20 lg:px-8 lg:py-24"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionTitle
            title="Une formule pour chaque étape de votre projet"
            sub="Des offres adaptées à différents cas d’usage."
          />
        </Reveal>

        <div className="mt-14 grid items-stretch gap-6 lg:grid-cols-3">
          {/* Découverte */}
          <Reveal>
            <div
              className="flex h-full flex-col rounded-2xl border p-8 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_24px_50px_-30px_rgba(0,0,0,0.25)]"
              style={{ background: C.cream, borderColor: C.border }}
            >
              <h3 className="font-serif text-[1.3rem] font-bold" style={{ color: C.ink }}>
                Découverte
              </h3>
              {/* min-h partagée par les trois cartes : les descriptions n'ont pas la même
                  longueur, on réserve la hauteur de la plus longue pour aligner les prix. */}
              <p className="mt-1 text-[14px] leading-relaxed lg:min-h-[8.75rem]" style={{ color: C.inkFaint }}>
                Vous répondez à quelques questions sur votre monument. Nous croisons vos réponses
                avec notre base de près de 250 dispositifs pour identifier ceux qui correspondent
                à votre situation.
              </p>
              <p className="mt-6 font-serif text-[1.6rem] font-bold leading-none" style={{ color: C.blue }}>
                Gratuit
              </p>
              <p className="mt-1.5 text-[13px]" style={{ color: C.inkFaint }}>
                pour toujours
              </p>
              <p className="mt-7 text-[13px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.blue }}>
                Cette offre comprend :
              </p>
              <ul className="mt-3 flex-1 space-y-3">
                {[
                  '1 monument',
                  '2 ouvertures de projets',
                  'L’ensemble des informations sur chaque dispositif : critères, dates d’ouverture et de clôture, documents à fournir, contact, page officielle, fiche informative',
                  'Cloud documentaire : stockez et classez vos documents selon leur nature (relevés, plans, cadastre, devis…)',
                  'Aide à la constitution de vos dossiers de demande : checklist des pièces à fournir, que vous complétez directement depuis votre cloud ou par téléversement, puis export du dossier une fois constitué',
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14.5px] leading-snug" style={{ color: C.inkSoft }}>
                    <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.blueLight }} strokeWidth={2.2} />
                    {f}
                  </li>
                ))}
              </ul>
              <CtaButton variant="ghost" onClick={goToSignup} className="mt-8 w-full">
                Découvrir mes dispositifs
              </CtaButton>
            </div>
          </Reveal>

          {/* Veille */}
          <Reveal delay={120}>
            <div
              className="relative flex h-full flex-col rounded-2xl border-[1.5px] p-8 shadow-[0_24px_60px_-28px_rgba(241,113,5,0.45)] transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_34px_72px_-26px_rgba(241,113,5,0.6)]"
              style={{ background: '#fff', borderColor: C.orange }}
            >
              <span
                className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-4 py-1.5 text-[12px] font-semibold uppercase tracking-[0.08em] text-white"
                style={{ background: C.orange }}
              >
                Le plus complet
              </span>
              <h3 className="font-serif text-[1.3rem] font-bold" style={{ color: C.ink }}>
                Veille
              </h3>
              <p className="mt-1 text-[14px] leading-relaxed lg:min-h-[8.75rem]" style={{ color: C.inkFaint }}>
                Adapté aux monuments qui développent un usage d’ouverture et d’animation : visites,
                événements, hébergement, tournages…
              </p>
              <p className="mt-6 font-serif text-[1.6rem] font-bold leading-none" style={{ color: C.blue }}>
                Abonnement
              </p>
              <p className="mt-1.5 text-[13px]" style={{ color: C.inkFaint }}>
                tous vos projets, toute l’année
              </p>
              <p className="mt-7 text-[13px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orange }}>
                Toutes les fonctionnalités de Découverte, plus :
              </p>
              <ul className="mt-3 flex-1 space-y-3">
                {[
                  'Ouvertures de projets illimitées',
                  'Veille automatique par IA, qui vous alerte sur les dates butoirs qui approchent et sur les nouveaux dispositifs auxquels vous devenez éligible en cours d’année',
                  'Tableau de bord et échéancier pour suivre et piloter vos projets',
                  'Invitation de collaborateurs sur l’un de vos projets : professionnel du secteur, architecte, assistant',
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14.5px] leading-snug" style={{ color: C.inkSoft }}>
                    <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.orange }} strokeWidth={2.2} />
                    {f}
                  </li>
                ))}
              </ul>
              <CtaButton onClick={goToSignup} className="mt-8 w-full">Activer la veille</CtaButton>
            </div>
          </Reveal>

          {/* Multi-monuments */}
          <Reveal delay={240}>
            <div
              className="relative flex h-full flex-col overflow-hidden rounded-2xl p-8 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_30px_66px_-28px_rgba(0,0,0,0.5)]"
              style={{ background: C.blue }}
            >
              <Tracery color="#ffffff" opacity={0.015} size={160} />
              <div className="relative flex h-full flex-col">
                <h3 className="font-serif text-[1.3rem] font-bold text-white">Multi-monuments</h3>
                <p className="mt-1 text-[14px] leading-relaxed text-white/60 lg:min-h-[8.75rem]">
                  Adapté aux collectivités, associations, propriétaires et gestionnaires de
                  plusieurs monuments.
                </p>
                <p className="mt-6 font-serif text-[1.6rem] font-bold leading-none text-white">
                  Sur mesure
                </p>
                <p className="mt-1.5 text-[13px] text-white/60">selon la taille de votre parc</p>
                <p className="mt-7 text-[13px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orangeVif }}>
                  Toutes les fonctionnalités de Veille, plus :
                </p>
                <ul className="mt-3 flex-1 space-y-3">
                  {[
                    'Gestion de plusieurs monuments en parallèle',
                    'Tableau de bord de gestion multi-monuments (avec veille)',
                  ].map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-[14.5px] leading-snug text-white/80">
                      <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.orangeVif }} strokeWidth={2.2} />
                      {f}
                    </li>
                  ))}
                </ul>
                <CtaButton variant="white" onClick={goToContact} className="mt-8 w-full">
                  Nous contacter
                </CtaButton>
              </div>
            </div>
          </Reveal>
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

function Faq() {
  const items = [
    {
      q: 'À qui s’adresse Monumia ?',
      a: 'À tous ceux qui ont un lieu à entretenir ou à faire vivre : propriétaires privés d’un château, d’un manoir, d’un moulin ou d’une maison ancienne, associations, fondations, communes et collectivités.',
    },
    {
      q: 'Mon lieu n’est ni classé, ni inscrit. Ai-je quand même droit à des aides ?',
      a: 'Très souvent, oui. Les Monuments historiques ne sont qu’une partie du paysage : les collectivités et les fondations soutiennent aussi le patrimoine non protégé, comme les églises rurales, les moulins, les lavoirs ou les maisons de caractère. Le questionnaire tient compte de la situation exacte de votre lieu.',
    },
    {
      q: 'Quels types de financements trouvez-vous ?',
      a: 'Les aides publiques (État et DRAC, régions, départements, communes), les fondations et le mécénat d’entreprise (Fondation du patrimoine, Dassault, Crédit Agricole, French Heritage Society…), ainsi que certains dispositifs européens.',
    },
    {
      q: 'Je ne suis pas à l’aise avec l’informatique. Est-ce pour moi ?',
      a: 'C’est précisément pour vous que Monumia est conçu. Les questions sont posées en français courant, chaque terme technique est expliqué d’un simple survol, et le parcours avance pas à pas. Et si vous bloquez, une vraie personne vous répond par e-mail.',
    },
    {
      q: 'Monumia dépose-t-il les demandes à ma place ?',
      a: 'Non, et c’est un choix. Monumia identifie les aides, vous explique les règles, rassemble vos pièces et prépare un dossier complet, prêt à transmettre. Vous restez maître de vos demandes ; nous vous épargnons les dizaines d’heures de recherche et de préparation.',
    },
    {
      q: 'Combien ça coûte ?',
      a: 'L’offre Découverte est gratuite, sans carte bancaire : un monument, deux projets, le détail de chaque dispositif, le cloud documentaire et l’aide au montage des dossiers. L’offre Veille ajoute les projets illimités, la veille automatique, le tableau de bord et les alertes. Et si vous gérez plusieurs monuments, l’offre Multi-monuments les réunit dans un seul espace.',
    },
    {
      q: 'D’où viennent vos informations ?',
      a: 'Notre base est construite à partir des publications officielles des financeurs (administrations, collectivités, fondations) et tenue à jour en continu. Chaque fiche indique ses sources et les contacts utiles.',
    },
  ];
  return (
    <section id="faq" className="scroll-mt-20 px-5 py-20 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-3xl">
        <Reveal>
          <SectionTitle
            title="Vos questions, nos réponses"
            sub={
              <>
                Pour toutes vos questions supplémentaires, merci de nous contacter :{' '}
                <a
                  href="mailto:contact@monumia.fr"
                  className="underline underline-offset-4 transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.orange }}
                >
                  contact@monumia.fr
                </a>
              </>
            }
          />
        </Reveal>
        <div className="mt-12 space-y-4">
          {items.map((item, i) => (
            <Reveal key={item.q} delay={i * 60}>
              <FaqItem question={item.q} answer={item.a} defaultOpen={i === 0} />
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
  return (
    <section className="px-5 pb-20 lg:px-8 lg:pb-24">
      <Reveal>
        <div
          className="relative mx-auto max-w-4xl overflow-hidden rounded-3xl px-7 py-16 text-center shadow-[0_30px_70px_-35px_rgba(10,54,157,0.55)] sm:px-16 sm:py-20"
          style={{ background: C.blue }}
        >
          <Tracery color="#ffffff" opacity={0.015} size={180} />

          <div className="relative">
            <h2 className="mx-auto max-w-2xl font-serif text-[clamp(1.9rem,3.6vw,2.5rem)] leading-[1.2] text-white">
              Nous trouvons les financements. Vous faites vivre votre monument.
            </h2>
            <p className="mx-auto mt-5 max-w-md text-[16px] leading-[1.7] text-white/75">
              Venez découvrir les dispositifs disponibles pour votre monument. 
            </p>
            <div className="mt-9">
              <CtaButton onClick={goToDecouverte}>Découvrir mes financements mobilisables</CtaButton>
            </div>
            <p className="mt-5 text-[13px] uppercase tracking-[0.12em] text-white/60">
              Gratuit · Sans engagement
            </p>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
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
            <p className="mt-4 font-serif text-[15px] italic" style={{ color: C.inkSoft }}>
              « Au service de celles et ceux qui font vivre le patrimoine bâti»
            </p>
            <p className="mt-3 max-w-xs text-[14px] leading-[1.7]" style={{ color: C.inkFaint }}>
              Des outils simples pour trouver les financements de votre patrimoine et le faire
              vivre. Conçu en France.
            </p>
          </div>

          <nav aria-label="Plan du site">
            <p className="text-[12px] font-semibold uppercase tracking-[0.14em]" style={{ color: C.inkFaint }}>
              Découvrir
            </p>
            <ul className="mt-4 space-y-2.5">
              {[
                ['#methode', 'Comment ça marche'],
                ['#equipe', 'L’équipe'],
                ['#tarifs', 'Tarifs'],
                ['#faq', 'Questions fréquentes'],
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
              Contact
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
                  Mentions légales
                </a>
              </li>
              <li>
                <a
                  href={`${BASE}cgu`}
                  className="text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.inkSoft }}
                >
                  Conditions générales d'utilisation
                </a>
              </li>
              <li>
                <a
                  href={`${BASE}confidentialite`}
                  className="text-[14px] transition-colors duration-200 hover:text-[#0a369d]"
                  style={{ color: C.inkSoft }}
                >
                  Politique de confidentialité
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
            © {new Date().getFullYear()} Monumia. Tous droits réservés.
          </p>
          <p className="text-[12.5px]" style={{ color: C.inkFaint }}>
            Photo du château de Paley :{' '}
            <a
              href="https://www.fondation-patrimoine.org/les-projets/chateau-de-paley/105079"
              target="_blank"
              rel="noopener noreferrer"
              className="underline transition-colors duration-200 hover:text-[#0a369d]"
            >
              Fondation Patrimoine
            </a>
            {', '}
            <a
              href="https://creativecommons.org/licenses/by-sa/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline transition-colors duration-200 hover:text-[#0a369d]"
            >
              CC BY-SA 4.0
            </a>
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
  return (
    <div className="font-sans" style={{ background: C.cream, color: C.ink }}>
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold"
        style={{ color: C.blue }}
      >
        Aller au contenu
      </a>
      <Header />
      <main id="contenu">
        <Hero />
        <Demo />
        <Team />
        <Pricing />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
