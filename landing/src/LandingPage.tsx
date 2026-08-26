import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import {
  ArrowDown,
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
  Lock,
  Mail,
  Radar,
  Search,
  Sparkles,
  TrendingUp,
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

function Kicker({
  children,
  color = C.orange,
  align = 'center',
}: {
  children: ReactNode;
  color?: string;
  align?: 'center' | 'left';
}) {
  return (
    <div className={`flex items-center gap-3 ${align === 'center' ? 'justify-center' : ''}`}>
      <span className="h-px w-7" style={{ background: color, opacity: 0.65 }} />
      <span className="text-[12.5px] font-semibold uppercase tracking-[0.18em]" style={{ color }}>
        {children}
      </span>
      {align === 'center' && <span className="h-px w-7" style={{ background: color, opacity: 0.65 }} />}
    </div>
  );
}

function goToApp() {
  window.location.href = APP_URL;
}

/* Page d'inscription à la liste d'attente : route servie par le fallback SPA de
   nginx (sous BASE — '/lancement' en prod, '/landing/lancement' en beta). */
export const SIGNUP_PATH = `${BASE}lancement`;
function goToSignup() {
  window.location.href = SIGNUP_PATH;
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

/* Titre de section : kicker, titre serif, filet orange */
function SectionTitle({
  kicker,
  title,
  sub,
  dark = false,
}: {
  kicker: string;
  title: ReactNode;
  sub?: ReactNode;
  dark?: boolean;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <Kicker color={dark ? C.orangeVif : C.orange}>{kicker}</Kicker>
      <h2
        className="mt-5 font-serif text-[clamp(1.9rem,3.4vw,2.4rem)] leading-[1.2] tracking-[-0.01em]"
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
            onClick={goToSignup}
            className="rounded-full px-5 py-2.5 text-[14px] font-semibold text-white transition-all duration-300 hover:shadow-[0_8px_20px_-6px_rgba(241,113,5,0.55)]"
            style={{ background: C.orange }}
          >
            Me tenir informé
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
        Château de Trévarez
      </h3>
      <p className="text-[12.5px]" style={{ color: C.inkFaint }}>
        Restauration des toitures · Finistère
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
      <div className="mt-3 flex items-center gap-1.5">
        <TrendingUp className="h-3.5 w-3.5" style={{ color: C.orange }} strokeWidth={2} />
        <span className="text-[12.5px] font-semibold" style={{ color: C.orange }}>
          Vos chances : élevées
        </span>
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
    <section className="relative overflow-hidden px-5 pb-24 pt-28 sm:pt-32 lg:px-8 lg:pb-28 lg:pt-32">
      <div
        className="pointer-events-none absolute -top-32 right-[-12%] h-[460px] w-[460px] rounded-full blur-[130px]"
        style={{ background: 'rgba(241, 113, 5, 0.1)' }}
      />

      <div className="relative mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12">
        <div>
          <div className="fade-up" style={{ animationDelay: '0.05s' }}>
            <span
              className="text-[12.5px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: C.orange }}
            >
              Lancement en Septembre 2026
            </span>
          </div>

          <h1
            className="fade-up mt-6 text-center font-serif text-[clamp(1.85rem,4.2vw,2.7rem)] leading-[1.13] tracking-[-0.015em]"
            style={{ color: C.ink, animationDelay: '0.15s' }}
          >
           
            <span className="block">Au service de celles et ceux qui</span> 
              <span className="relative inline-block whitespace-nowrap" style={{ color: C.blue }}>
                font vivre 
                <svg
                  viewBox="0 0 230 12"
                  className="absolute -bottom-1.5 left-0 w-full"
                  aria-hidden="true"
                  preserveAspectRatio="none"
                >
                  <path
                    d="M4 8.5 C 60 2.5, 160 2.5, 226 7"
                    fill="none"
                    stroke={C.orange}
                    strokeWidth="4"
                    strokeLinecap="round"
                    style={{
                      strokeDasharray: 240,
                      strokeDashoffset: 240,
                      animation: 'draw-stroke 1s 1.3s ease forwards',
                    }}
                  />
                </svg>
              </span>{' '}
             le patrimoine bâti
          </h1>

          <p
            className="fade-up mt-7 max-w-xl text-[17px] font-medium leading-[1.7] sm:text-[18px]"
            style={{ color: C.inkSoft, animationDelay: '0.3s' }}
          >
            Monumia facilite l’identification et la qualification de l’ensemble des financements
            mobilisables pour les projets de restauration, d’ouverture et d’animation d’un monument.
          </p>

          <div className="fade-up mt-9 flex flex-wrap items-center gap-4" style={{ animationDelay: '0.45s' }}>
            <CtaButton onClick={goToSignup}>Me tenir informé du lancement</CtaButton>
            <a
              href="#methode"
              className="group inline-flex items-center gap-2 px-2 py-3 text-[15px] font-semibold transition-colors duration-200 hover:text-[#0a369d]"
              style={{ color: C.inkSoft }}
            >
              Voir Monumia en action
              <ArrowDown className="h-4 w-4 transition-transform duration-300 group-hover:translate-y-0.5" />
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
              src={`${BASE}img/trevarez-hero.jpg`}
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
          <span className="text-[11.5px] font-semibold uppercase tracking-[0.1em]" style={{ color: C.inkFaint }}>
            Votre projet · Question 5 sur 12
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
          Votre bâtiment est-il classé ou inscrit aux Monuments historiques ?
        </h4>
        <p
          className="demo-pop mt-3 rounded-lg border-l-2 bg-white p-3 text-[12.5px] italic leading-relaxed"
          style={{ borderColor: C.orange, color: C.inkSoft, animationDelay: '0.7s' }}
        >
          Pas sûr de la réponse ? Choisissez « je ne sais pas » : nous vérifions pour vous.
        </p>
        <div className="mt-3.5 flex flex-wrap gap-2">
          <DemoChip appear={1.1}>Oui</DemoChip>
          <DemoChip appear={1.25}>Non</DemoChip>
          <DemoChip appear={1.4} select={2.4} demoId="chip-sais-pas">
            Je ne sais pas
          </DemoChip>
        </div>

        <div className="demo-pop mt-6" style={{ animationDelay: '3s' }}>
          <h4 className="font-serif text-[1.1rem] font-bold leading-snug sm:text-[1.2rem]" style={{ color: C.ink }}>
            Que souhaitez-vous faire ?
          </h4>
          <div className="mt-3 flex flex-wrap gap-2">
            <DemoChip appear={3.3} select={4.5} demoId="chip-toiture">
              Restaurer la toiture
            </DemoChip>
            <DemoChip appear={3.45}>Refaire la façade</DemoChip>
            <DemoChip appear={3.6}>Autre projet</DemoChip>
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
            <CountUp to={92000} delay={8700} /> – <CountUp to={140000} delay={8700} duration={1700} /> €
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
          { at: 2.15, target: 'chip-sais-pas', click: true },
          { at: 4.3, target: 'chip-toiture', click: true },
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
];

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
    const t = setTimeout(() => setCycle((c) => c + 1), CATEGORIES[active].duration);
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
  const finale = useInView(0.3);

  return (
    <section
      id="methode"
      ref={ref}
      className="relative scroll-mt-20 overflow-hidden"
      style={{ background: C.blue }}
    >
      <Tracery color="#ffffff" opacity={0.03} size={220} />
      <div className="relative z-10 mx-auto max-w-6xl px-5 pt-20 lg:px-8 lg:pt-24">
        <Reveal>
          <SectionTitle
            dark
            kicker="L’application"
            title="Tout ce que Monumia fait pour votre patrimoine"
            sub="Trois missions, un seul outil. Choisissez un onglet : l’application déroule un exemple sous vos yeux, comme si vous y étiez."
          />
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
              <CtaButton variant="white" onClick={goToSignup} className="mt-9">
                Me tenir informé du lancement
              </CtaButton>
            </div>

            {/* L’écran de l’application, posé sur un panneau teinté */}
            <div className="rounded-[2rem] p-3 sm:p-6 lg:p-8" style={{ background: C.paleOrange }}>
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
                    <div key={`${active}-${cycle}`} className="h-full">
                      <Scene />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </div>

      {/* L'arrivée : la frise des bâtiments, au sol */}
      <div ref={finale.ref} className="relative mt-16 h-[230px] sm:h-[270px] lg:mt-20">
        <ParallaxLandscape lit={finale.inView} />
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────
   La frise de patrimoine — décor de la section « L’application »
   ──────────────────────────────────────────── */

/* La frise de patrimoine dessinée à la main ferme la section #methode : elle
   défile en parallaxe sur plusieurs plans à vitesses distinctes (les plus
   proches plus vite, le soleil à contre-sens) ; les monuments-repères
   s'embrasent à l'heure dorée quand la section arrive. Tout est piloté en
   transform (GPU) ; ParallaxItem se met au repos pour les visiteurs qui
   préfèrent réduire les animations. */

const FRIEZE_FRONT_W = 3700;
const FRIEZE_MID_W = 3000;
const FRIEZE_FAR_TILE = 1300;
/* Abscisses des quatre monuments-repères dans la frise de premier plan */
const LANDMARK_X = [642, 1311, 1980, 2649];

/* Premier plan crème (3700×150) : village, château fort, moulin à vent,
   église au clocher ajouré (sa cloche pend dans l’ouverture), halle aux
   piliers, puis le village qui s’éloigne. Le sol est la bande y134-150. */
const FRIEZE_FRONT =
  'M0 134 H3700 V150 H0 Z ' +
  'M40 150 C40 122 50 108 70 108 C90 108 100 122 100 150 Z ' +
  'M120 150 V112 L150 94 L180 112 V150 Z M190 150 V120 L216 104 L242 120 V150 Z ' +
  'M250 150 V126 H330 V150 Z ' +
  'M350 150 C350 126 360 114 378 114 C396 114 406 126 406 150 Z ' +
  'M452 150 V60 H500 V150 Z M444 62 H508 L476 16 Z M474 16 V6 H478 V16 Z M478 6 L496 10 L478 14 Z ' +
  'M500 150 V84 h14 v-10 h14 v10 h16 v-10 h14 v10 h16 v-10 h14 v10 h12 V150 Z ' +
  'M598 84 H666 V104 Q632 124 598 104 Z ' +
  'M664 150 V84 h12 v-10 h14 v10 h16 v-10 h14 v10 h16 v-10 h14 v10 h12 V150 Z ' +
  'M762 150 V56 h12 v-10 h12 v10 h12 v-10 h12 v10 h12 v-10 h12 v10 h8 V150 Z ' +
  'M842 150 V126 H922 V150 Z ' +
  'M940 150 C940 124 950 110 970 110 C990 110 1000 124 1000 150 Z ' +
  'M1030 150 V114 L1066 96 L1102 114 V150 Z M1086 107 V88 H1096 V107 Z ' +
  'M1130 150 C1130 130 1138 120 1152 120 C1166 120 1174 130 1174 150 Z ' +
  'M1221 150 Q1311 122 1401 150 Z ' +
  'M1273 150 L1283 64 H1339 L1349 150 Z ' +
  'M1267 66 C1267 48 1285 40 1311 40 C1337 40 1355 48 1355 66 Z ' +
  'M1259 6 L1265 0 L1363 102 L1357 108 Z M1357 0 L1363 6 L1265 108 L1259 102 Z ' +
  'M1450 150 V128 H1486 V150 Z M1454 128 V112 H1460 V128 Z M1476 128 V112 H1482 V128 Z M1448 112 H1488 L1468 98 Z ' +
  'M1530 150 C1530 126 1540 112 1560 112 C1580 112 1590 126 1590 150 Z ' +
  'M1640 150 V92 H1684 V150 Z M1634 94 H1690 L1662 58 Z M1660 58 V48 H1664 V58 Z ' +
  'M1684 150 V128 H1770 V150 Z ' +
  'M1790 150 C1790 128 1800 116 1818 116 C1836 116 1846 128 1846 150 Z ' +
  'M1877 150 V104 H1987 V150 Z M1871 106 L1932 80 L1993 106 Z ' +
  'M1930 80 V66 H1934 V80 Z M1924 70 H1940 V74 H1924 Z ' +
  'M1987 150 V70 H2047 V150 Z ' +
  'M1987 70 V38 H1999 V70 Z M2035 70 V38 H2047 V70 Z ' +
  'M1983 38 H2051 V30 H1983 Z ' +
  'M1979 30 H2055 L2017 6 Z M2015 6 V0 H2019 V6 Z ' +
  'M2009 44 C2009 38 2025 38 2025 44 L2027 52 H2007 Z M2015 52 H2019 V56 H2015 Z ' +
  'M2110 150 V118 L2138 102 L2166 118 V150 Z ' +
  'M2200 150 C2200 124 2212 110 2232 110 C2252 110 2264 124 2264 150 Z ' +
  'M2310 150 V112 H2370 V150 Z M2304 114 L2340 92 L2376 114 Z M2332 92 V78 H2348 V92 Z M2328 78 H2352 L2340 64 Z ' +
  'M2370 150 V130 H2460 V150 Z ' +
  'M2512 100 L2649 56 L2786 100 L2786 110 H2512 Z ' +
  'M2642 56 V46 H2656 V56 Z M2638 46 H2660 L2649 36 Z ' +
  'M2526 150 V110 H2538 V150 Z M2584 150 V110 H2596 V150 Z M2643 150 V110 H2655 V150 Z M2702 150 V110 H2714 V150 Z M2760 150 V110 H2772 V150 Z ' +
  'M2820 150 V116 L2850 100 L2880 116 V150 Z ' +
  'M2920 150 C2920 124 2932 110 2952 110 C2972 110 2984 124 2984 150 Z ' +
  'M3040 150 V92 H3080 V150 Z M3034 94 H3086 L3060 60 Z ' +
  'M3080 150 V128 H3180 V150 Z ' +
  'M3240 150 V118 L3268 102 L3296 118 V150 Z M3310 150 V124 L3334 110 L3358 124 V150 Z ' +
  'M3420 150 C3420 126 3430 112 3450 112 C3470 112 3480 126 3480 150 Z ' +
  'M3560 150 C3560 132 3568 122 3582 122 C3596 122 3604 132 3604 150 Z ' +
  'M3650 150 V122 L3676 108 L3700 122 V150 Z';

/* Les mêmes monuments, isolés : surimprimés en teinte chaude quand leur
   halte est active, comme frappés par la lumière du soir. */
const LIT_LANDMARKS = [
  'M452 150 V60 H500 V150 Z M444 62 H508 L476 16 Z M474 16 V6 H478 V16 Z M478 6 L496 10 L478 14 Z ' +
    'M500 150 V84 h14 v-10 h14 v10 h16 v-10 h14 v10 h16 v-10 h14 v10 h12 V150 Z ' +
    'M598 84 H666 V104 Q632 124 598 104 Z ' +
    'M664 150 V84 h12 v-10 h14 v10 h16 v-10 h14 v10 h16 v-10 h14 v10 h12 V150 Z ' +
    'M762 150 V56 h12 v-10 h12 v10 h12 v-10 h12 v10 h12 v-10 h12 v10 h8 V150 Z',
  'M1273 150 L1283 64 H1339 L1349 150 Z ' +
    'M1267 66 C1267 48 1285 40 1311 40 C1337 40 1355 48 1355 66 Z ' +
    'M1259 6 L1265 0 L1363 102 L1357 108 Z M1357 0 L1363 6 L1265 108 L1259 102 Z',
  'M1877 150 V104 H1987 V150 Z M1871 106 L1932 80 L1993 106 Z ' +
    'M1930 80 V66 H1934 V80 Z M1924 70 H1940 V74 H1924 Z ' +
    'M1987 150 V70 H2047 V150 Z M1987 70 V38 H1999 V70 Z M2035 70 V38 H2047 V70 Z ' +
    'M1983 38 H2051 V30 H1983 Z M1979 30 H2055 L2017 6 Z M2015 6 V0 H2019 V6 Z ' +
    'M2009 44 C2009 38 2025 38 2025 44 L2027 52 H2007 Z M2015 52 H2019 V56 H2015 Z',
  'M2512 100 L2649 56 L2786 100 L2786 110 H2512 Z ' +
    'M2642 56 V46 H2656 V56 Z M2638 46 H2660 L2649 36 Z ' +
    'M2526 150 V110 H2538 V150 Z M2584 150 V110 H2596 V150 Z M2643 150 V110 H2655 V150 Z ' +
    'M2702 150 V110 H2714 V150 Z M2760 150 V110 H2772 V150 Z',
];

/* Plan moyen (3000×190) : fort, cathédrale, donjon, abbaye, grand château
   et masses de forêt, dans l’ombre du soir. */
const FRIEZE_MID =
  'M0 190 V158 C200 152 400 150 600 154 C800 158 1000 160 1200 156 C1400 152 1600 154 1800 158 C2000 162 2200 158 2400 154 C2600 150 2800 154 3000 158 V190 Z ' +
  'M300 190 V84 H344 V190 Z M293 86 H351 L322 48 Z ' +
  'M344 190 V120 H470 V190 Z ' +
  'M470 190 V96 H510 V190 Z M464 98 H516 L490 62 Z ' +
  'M620 190 C620 150 640 130 680 130 C720 130 740 150 740 190 Z ' +
  'M730 190 C730 162 744 148 770 148 C796 148 810 162 810 190 Z ' +
  'M940 190 V64 H982 V190 Z M934 66 H988 L961 38 Z ' +
  'M982 190 V104 H1090 V190 Z M976 106 L1036 80 L1096 106 Z ' +
  'M1090 190 V64 H1132 V190 Z M1084 66 H1138 L1111 38 Z ' +
  'M1250 190 C1250 154 1268 136 1304 136 C1340 136 1358 154 1358 190 Z ' +
  'M1510 190 V92 h10 v-12 h12 v12 h14 v-12 h12 v12 h14 v-12 h12 v12 h10 V190 Z ' +
  'M1594 190 V120 H1620 V190 Z ' +
  'M1840 190 V120 H2010 V190 Z M1834 122 L1925 88 L2016 122 Z ' +
  'M2010 190 V100 H2040 V190 Z M2005 102 H2045 L2025 76 Z ' +
  'M2150 190 C2150 156 2166 140 2198 140 C2230 140 2246 156 2246 190 Z ' +
  'M2440 190 V80 H2486 V190 Z M2433 82 H2493 L2463 44 Z ' +
  'M2486 190 V112 H2600 V190 Z M2479 114 L2543 86 L2607 114 Z ' +
  'M2600 190 V92 H2642 V190 Z M2594 94 H2648 L2621 58 Z ' +
  'M2780 190 C2780 158 2794 144 2820 144 C2846 144 2860 158 2860 190 Z';

/* Lointain (tuile 1300×110, répétée) : collines voilées, fort perché,
   flèche dans la brume. */
const FRIEZE_FAR =
  'M0 110 V72 C160 60 300 56 460 64 C620 72 700 76 860 70 C1020 64 1160 62 1300 72 V110 Z ' +
  'M480 64 V40 H500 V64 Z M476 42 H504 L490 26 Z M500 62 V50 H540 V62 Z ' +
  'M1040 60 V34 H1052 V60 Z M1036 36 H1056 L1046 18 Z';

/* Le paysage de patrimoine : un premier plan crème qui glisse en douceur au
   défilement (toujours au sol, prolongé d'un bloc crème pour ne jamais
   décoller), devant des plans fixes — donc rien ne flotte. Les
   monuments-repères s'embrasent à l'heure dorée quand la section arrive. */
function ParallaxLandscape({ lit }: { lit: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute inset-x-0 bottom-0 h-[170px]"
        style={{ background: 'linear-gradient(to top, rgba(92,149,255,0.2), rgba(92,149,255,0))' }}
      />

      {/* Plan lointain : collines en brume (fixe) */}
      <div className="absolute bottom-[34px] left-[calc(50%-720px)] sm:bottom-[40px] sm:left-[calc(50%-1300px)]">
        <svg width={FRIEZE_FAR_TILE * 3} height="110" viewBox={`0 0 ${FRIEZE_FAR_TILE * 3} 110`} aria-hidden="true">
          <path d={FRIEZE_FAR} fill="rgba(255,255,255,0.09)" />
          <path d={FRIEZE_FAR} fill="rgba(255,255,255,0.09)" transform={`translate(${FRIEZE_FAR_TILE} 0)`} />
          <path d={FRIEZE_FAR} fill="rgba(255,255,255,0.09)" transform={`translate(${FRIEZE_FAR_TILE * 2} 0)`} />
        </svg>
      </div>

      {/* Plan moyen : grands monuments dans l'ombre (fixe, ancré derrière) */}
      <div className="absolute bottom-[-6px] left-[calc(50%-600px)] sm:left-[calc(50%-1180px)]">
        <svg width={FRIEZE_MID_W} height="190" viewBox={`0 0 ${FRIEZE_MID_W} 190`} aria-hidden="true">
          <path d={FRIEZE_MID} fill="#072a72" />
        </svg>
      </div>

      {/* Premier plan : la frise crème, au sol, qui glisse doucement */}
      <ParallaxItem factor={0.07} className="absolute bottom-0 left-[calc(50%-680px)] sm:left-[calc(50%-1311px)]">
        <div className="relative">
          {LANDMARK_X.map((x, i) => (
            <div
              key={x}
              className="absolute bottom-0 transition-opacity duration-[1000ms]"
              style={{ left: x, opacity: lit ? 1 : 0, transitionDelay: `${i * 140}ms` }}
            >
              <div
                className="absolute -translate-x-1/2 rounded-full blur-3xl"
                style={{ bottom: -24, width: 320, height: 170, background: 'radial-gradient(closest-side, rgba(252,137,5,0.38), rgba(252,137,5,0))' }}
              />
              <div
                className="absolute -translate-x-1/2 rounded-full blur-xl"
                style={{ bottom: 8, width: 170, height: 100, background: 'radial-gradient(closest-side, rgba(253,176,74,0.5), rgba(252,137,5,0))' }}
              />
            </div>
          ))}
          <svg width={FRIEZE_FRONT_W} height="150" viewBox={`0 0 ${FRIEZE_FRONT_W} 150`} className="relative block" aria-hidden="true">
            <path d={FRIEZE_FRONT} fill={C.card} />
            {LIT_LANDMARKS.map((d, i) => (
              <path
                key={i}
                d={d}
                fill="#fcd9a0"
                className="transition-opacity duration-[1000ms]"
                style={{ opacity: lit ? 1 : 0, transitionDelay: `${i * 140}ms` }}
              />
            ))}
          </svg>
          {/* Sol crème prolongé vers le bas (hors champ) */}
          <div className="absolute left-0 top-full h-[320px]" style={{ width: FRIEZE_FRONT_W, background: C.card }} />
        </div>
      </ParallaxItem>
    </div>
  );
}

/* ────────────────────────────────────────────
   L’équipe — une arcade de cloître : trois niches
   en plein cintre qui s’éclairent au passage.
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
}> = [
  {
    name: 'Paul',
    img: `${BASE}img/team-paul.jpg`,
    alt: 'Portrait de Paul, cofondateur de Monumia',
    desc: 'Chargé de la vision et du développement commercial.',
    lift: 'md:mt-0',
    factor: 0.025,
  },
  {
    name: 'Félix',
    img: `${BASE}img/team-felix.jpg`,
    alt: 'Portrait de Félix, cofondateur de Monumia',
    desc: 'Chargé de la conception et du développement de la plateforme.',
    lift: 'md:mt-0',
    factor: 0.025,
  },
];

function Team() {
  return (
    <section id="equipe" className="scroll-mt-20 px-5 py-20 lg:px-8 lg:py-24">
      <div className="mx-auto max-w-5xl">
        <Reveal>
          <SectionTitle
            kicker="L’équipe"
            title="Les visages derrière Monumia"
            sub="Notre conviction : le patrimoine mérite des outils à la hauteur de son histoire et de ceux qui le font vivre."
          />
        </Reveal>

        <div className="mx-auto mt-14 grid max-w-2xl gap-14 md:grid-cols-2 md:gap-10">
          {TEAM.map((m, i) => (
            <ParallaxItem key={m.name} factor={m.factor}>
              <Reveal delay={i * 130}>
                <figure className={`group relative mx-auto max-w-[280px] ${m.lift}`}>
                  {/* La niche en plein cintre : pierre crème, filet orange, portrait dans l’ouverture */}
                  <div
                    className="relative rounded-t-[9999px] border p-3 shadow-[0_26px_50px_-30px_rgba(34,43,53,0.45)] transition-shadow duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:shadow-[0_36px_70px_-30px_rgba(241,113,5,0.4)]"
                    style={{ background: C.card, borderColor: C.border }}
                  >
                    {/* La clé de voûte, qui s’embrase au passage */}
                    <span
                      aria-hidden="true"
                      className="absolute left-1/2 top-[-7px] z-10 h-3.5 w-3.5 -translate-x-1/2 rotate-45 border transition-colors duration-[700ms] ease-out [background:#fdf9f0] [border-color:#ece3d2] group-hover:[background:#f17105] group-hover:[border-color:#f17105]"
                    />

                    <div className="rounded-t-[9999px] border-[1.5px] p-[3px] transition-colors duration-[900ms] ease-out [border-color:rgba(241,113,5,0.4)] group-hover:[border-color:#f17105]">
                      <div className="relative overflow-hidden rounded-t-[9999px]">
                        <img
                          src={m.img}
                          alt={m.alt}
                          loading="lazy"
                          className="aspect-[3/4.4] w-full object-cover transition-[scale] duration-[1100ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:scale-[1.04]"
                        />
                        {/* L’ombre de l’intrados : la niche a de la profondeur */}
                        <span
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-0 rounded-t-[9999px]"
                          style={{
                            boxShadow:
                              'inset 0 24px 32px -20px rgba(34,43,53,0.42), inset 0 -16px 24px -18px rgba(34,43,53,0.3)',
                          }}
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
                    </div>

                    {/* La plaque gravée sur le socle, sous le portrait */}
                    <figcaption
                      className="mx-auto mt-3 w-fit whitespace-nowrap rounded-[5px] border px-4 py-1 font-serif text-[14px] font-bold transition-[border-color,box-shadow] duration-[700ms] ease-out group-hover:shadow-[0_10px_18px_-10px_rgba(241,113,5,0.5)] group-hover:[border-color:#f17105]"
                      style={{ background: C.paleOrange, borderColor: 'rgba(241,113,5,0.45)', color: C.ink }}
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
   Tarifs — trois portes, aucune surprise
   ──────────────────────────────────────────── */

function Pricing() {
  return (
    <section
      id="tarifs"
      className="scroll-mt-20 border-b px-5 py-20 lg:px-8 lg:py-24"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionTitle
            kicker="Tarifs"
            title="Commencez gratuitement, payez quand vous êtes prêt"
            sub="L’estimation ne coûte rien. Le reste est à votre rythme : un dossier quand vous en avez un, un abonnement si vous ne voulez rien rater."
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
              <p className="mt-1 text-[14px]" style={{ color: C.inkFaint }}>
                Pour savoir ce que votre lieu peut espérer.
              </p>
              <p className="mt-6 font-serif text-[2.1rem] font-bold leading-none" style={{ color: C.blue }}>
                0 €
              </p>
              <p className="mt-1.5 text-[13px]" style={{ color: C.inkFaint }}>
                pour toujours
              </p>
              <ul className="mt-7 flex-1 space-y-3">
                {[
                  'Description guidée de votre lieu et de votre projet',
                  'Recherche parmi toutes les aides recensées',
                  'Estimation de vos aides',
                  'Vos chances d’obtenir ces aides',
                  'Termes expliqués et guides pratiques',
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14.5px] leading-snug" style={{ color: C.inkSoft }}>
                    <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.blueLight }} strokeWidth={2.2} />
                    {f}
                  </li>
                ))}
              </ul>
              <CtaButton variant="ghost" onClick={goToSignup} className="mt-8 w-full">
                Estimer mes aides
              </CtaButton>
            </div>
          </Reveal>

          {/* Dossier */}
          <Reveal delay={120}>
            <div
              className="relative flex h-full flex-col rounded-2xl border-[1.5px] p-8 shadow-[0_24px_60px_-28px_rgba(241,113,5,0.45)] transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_34px_72px_-26px_rgba(241,113,5,0.6)]"
              style={{ background: '#fff', borderColor: C.orange }}
            >
              <span
                className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-4 py-1.5 text-[12px] font-semibold uppercase tracking-[0.08em] text-white"
                style={{ background: C.orange }}
              >
                Pour votre projet
              </span>
              <h3 className="font-serif text-[1.3rem] font-bold" style={{ color: C.ink }}>
                Dossier
              </h3>
              <p className="mt-1 text-[14px]" style={{ color: C.inkFaint }}>
                Pour monter un projet solide, facilement.
              </p>
              <p className="mt-6 font-serif text-[1.6rem] font-bold leading-none" style={{ color: C.blue }}>
                Paiement unique
              </p>
              <p className="mt-1.5 text-[13px]" style={{ color: C.inkFaint }}>
                par projet, sans abonnement
              </p>
              <p className="mt-7 text-[13px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orange }}>
                Tout Découverte, plus :
              </p>
              <ul className="mt-3 flex-1 space-y-3">
                {[
                  'Le détail de chaque aide : critères, montants, contacts',
                  'Les dates clés de votre projet à ne pas manquer',
                  'Un espace en ligne pour ranger vos pièces',
                  'La checklist des pièces demandées par les financeurs',
                  'Le téléchargement du dossier complet, prêt à transmettre',
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14.5px] leading-snug" style={{ color: C.inkSoft }}>
                    <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.orange }} strokeWidth={2.2} />
                    {f}
                  </li>
                ))}
              </ul>
              <CtaButton onClick={goToSignup} className="mt-8 w-full">Monter mon dossier</CtaButton>
            </div>
          </Reveal>

          {/* Abonnement */}
          <Reveal delay={240}>
            <div
              className="relative flex h-full flex-col overflow-hidden rounded-2xl p-8 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_30px_66px_-28px_rgba(0,0,0,0.5)]"
              style={{ background: C.blue }}
            >
              <Tracery color="#ffffff" opacity={0.03} size={160} />
              <span
                className="absolute right-6 top-6 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-white"
                style={{ background: C.orangeVif }}
              >
                Le plus complet
              </span>
              <div className="relative">
                <h3 className="font-serif text-[1.3rem] font-bold text-white">Abonnement</h3>
                <p className="mt-1 text-[14px] text-white/60">
                  Pour piloter votre patrimoine dans la durée.
                </p>
                <p className="mt-6 font-serif text-[1.6rem] font-bold leading-none text-white">
                  Mensuel
                </p>
                <p className="mt-1.5 text-[13px] text-white/60">tous vos projets, toute l’année</p>
                <p className="mt-7 text-[13px] font-semibold uppercase tracking-[0.08em]" style={{ color: C.orangeVif }}>
                  Tout Dossier, plus :
                </p>
                <ul className="mt-3 space-y-3">
                  {[
                    'La veille et les alertes : nouvelles aides, ouvertures de fondations',
                    'Les suggestions de projets que votre lieu pourrait financer',
                    'Le suivi d’avancement de chaque demande',
                    'La recherche libre des mécènes et fondations',
                    'Un espace partagé avec votre architecte ou vos artisans',
                  ].map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-[14.5px] leading-snug text-white/80">
                      <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.orangeVif }} strokeWidth={2.2} />
                      {f}
                    </li>
                  ))}
                </ul>
                <CtaButton variant="white" onClick={goToSignup} className="mt-8 w-full">
                  Choisir l’abonnement
                </CtaButton>
              </div>
            </div>
          </Reveal>
        </div>

        <Reveal delay={300}>
          <p className="mt-10 text-center text-[13.5px]" style={{ color: C.inkFaint }}>
            Les tarifs définitifs seront annoncés au lancement. L’estimation reste gratuite, sans
            carte bancaire.
          </p>
        </Reveal>
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
      a: 'À tous ceux qui ont un lieu à entretenir ou à faire vivre : propriétaires privés d’un château, d’un manoir, d’un moulin ou d’une maison ancienne, associations, fondations, communes et collectivités. Si votre lieu a une histoire, Monumia peut chercher les aides qui lui correspondent.',
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
      a: 'L’estimation est gratuite, sans carte bancaire. Pour aller au bout d’un projet, le Dossier s’achète une seule fois. Et si vous gérez votre lieu dans la durée, l’abonnement ajoute la veille, les alertes et le suivi de tous vos projets.',
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
            kicker="Questions fréquentes"
            title="Vos questions, nos réponses"
            sub="Et s’il en reste une, écrivez-nous : une vraie personne vous répondra."
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
          <Tracery color="#ffffff" opacity={0.03} size={180} />
          <Clover
            className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 opacity-[0.07] [animation:spin-slow_90s_linear_infinite]"
            strokeWidth={4}
            style={{ color: C.orange }}
          />
          <Clover
            className="pointer-events-none absolute -bottom-20 -left-16 h-48 w-48 opacity-[0.06]"
            strokeWidth={4}
            style={{ color: C.blueLight }}
          />

          <div className="relative">
            <h2 className="mx-auto max-w-2xl font-serif text-[clamp(1.9rem,3.6vw,2.5rem)] leading-[1.2] text-white">
              Et si votre monument pouvait être financé bien au-delà de ce que vous imaginez ?
            </h2>
            <p className="mx-auto mt-5 max-w-md text-[16px] leading-[1.7] text-white/75">
              Décrivez votre lieu, découvrez votre estimation. C’est gratuit, et cela ne prend que
              quelques minutes.
            </p>
            <div className="mt-9">
              <CtaButton onClick={goToSignup}>Me tenir informé du lancement</CtaButton>
            </div>
            <p className="mt-5 text-[13px] uppercase tracking-[0.12em] text-white/60">
              Sans carte bancaire · Sans engagement
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
            Photo du château de Trévarez :{' '}
            <a
              href="https://commons.wikimedia.org/wiki/File:Ch%C3%A2teau_de_Tr%C3%A9varez_aile_Ouest,_Saint-Goazec_(29).jpg"
              target="_blank"
              rel="noopener noreferrer"
              className="underline transition-colors duration-200 hover:text-[#0a369d]"
            >
              DomFelga
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
        <Pricing />
        <Team />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
