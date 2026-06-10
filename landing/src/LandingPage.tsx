import { useState, useEffect, useRef, type ReactNode } from 'react';
import {
  Search,
  FileCheck,
  Euro,
  ArrowRight,
  Building2,
  Users,
  HardHat,
  TrendingUp,
  Landmark,
  Clock,
  Shield,
  CheckCircle2,
  ArrowUpRight,
  ChevronDown,
  Minus,
} from 'lucide-react';

const APP_URL = import.meta.env.VITE_APP_URL || 'https://app.monumia.fr';

/* ────────────────────────────────────────────
   Colors — brand palette
   ──────────────────────────────────────────── */

const C = {
  bg:          '#F8F7F4',   // warm parchment white
  bgAlt:       '#FFFFFF',   // pure white for alternating sections
  text:        '#1B1E2E',   // deep navy foreground
  textMuted:   '#5C6178',   // secondary text
  textLight:   '#8E92A4',   // tertiary / labels
  royal:       '#1A237E',   // royal blue — primary brand
  royalLight:  '#3949AB',   // lighter royal blue
  royalPale:   '#E8EAF6',   // very pale royal tint
  terra:       '#C75B3A',   // terracotta — accent brand
  terraPale:   '#FBF0EC',   // very pale terracotta tint
  border:      '#E4E2DC',   // warm neutral border
} as const;

/* ────────────────────────────────────────────
   Utilities
   ──────────────────────────────────────────── */

function useInView(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setInView(true); obs.disconnect(); } },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

function Reveal({ children, className = '', delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const { ref, inView } = useInView(0.08);
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (inView) { const t = setTimeout(() => setShow(true), delay); return () => clearTimeout(t); }
  }, [inView, delay]);
  return (
    <div
      ref={ref}
      className={`transition-all duration-[1100ms] ease-[cubic-bezier(0.22,1,0.36,1)] ${show ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'} ${className}`}
    >
      {children}
    </div>
  );
}

function Counter({ to, suffix = '' }: { to: number; suffix?: string }) {
  const { ref, inView } = useInView(0.3);
  const [val, setVal] = useState(0);
  const done = useRef(false);
  useEffect(() => {
    if (!inView || done.current) return;
    done.current = true;
    let cur = 0;
    const step = to / 60;
    const id = setInterval(() => {
      cur += step;
      if (cur >= to) { setVal(to); clearInterval(id); } else setVal(Math.floor(cur));
    }, 35);
    return () => clearInterval(id);
  }, [inView, to]);
  return <span ref={ref}>{val.toLocaleString('fr-FR')}{suffix}</span>;
}

function MarqueeRow({ reverse = false }: { reverse?: boolean }) {
  const items = [
    'Cathédrales', 'Châteaux', 'Manoirs', 'Abbatiales', 'Bastides', 'Chapelles',
    'Forteresses', 'Hôtels particuliers', 'Cloîtres', 'Remparts', 'Donjons', 'Prieurés',
  ];
  const doubled = [...items, ...items];
  return (
    <div className="overflow-hidden whitespace-nowrap select-none" style={{ color: C.royal }}>
      <div
        className={`inline-flex gap-10 text-[10rem] lg:text-[12rem] font-light tracking-tight leading-none opacity-[0.035] ${reverse ? 'animate-marquee-reverse' : 'animate-marquee'}`}
        style={{ fontFamily: "'Cormorant Garamond', serif" }}
      >
        {doubled.map((t, i) => (
          <span key={i} className="inline-flex items-center gap-10">
            {t}
            <span className="text-[3rem] opacity-30">◆</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function goToApp() {
  window.location.href = `${APP_URL}/login`;
}

/* ────────────────────────────────────────────
   Landing Page
   ──────────────────────────────────────────── */

export function LandingPage() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', fn, { passive: true });
    return () => window.removeEventListener('scroll', fn);
  }, []);

  return (
    <div className="min-h-screen antialiased overflow-x-hidden" style={{ background: C.bg, color: C.text }}>

      {/* SUBTLE GRAIN TEXTURE */}
      <div
        className="pointer-events-none fixed inset-0 z-[100] opacity-[0.018]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          backgroundSize: '128px 128px',
        }}
      />

      {/* NAV */}
      <header
        className={`fixed inset-x-0 top-0 z-50 transition-all duration-500 ${
          scrolled
            ? 'bg-[#F8F7F4]/80 backdrop-blur-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] border-b'
            : ''
        }`}
        style={{ borderColor: scrolled ? C.border : 'transparent' }}
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 lg:px-10 py-5">
          <div className="flex items-center gap-3">
            <img src="/patrys.png" alt="Patrys" className="h-7" />
            <span
              className="text-[1.45rem] font-light tracking-[-0.01em]"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: C.royal }}
            >
              Patrys
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-10 text-[13px] font-medium uppercase tracking-[0.12em]" style={{ color: C.textLight }}>
            <a href="#fonctionnalites" className="transition-colors duration-300 hover:text-[#1A237E]">Fonctionnalités</a>
            <a href="#methode" className="transition-colors duration-300 hover:text-[#1A237E]">Méthode</a>
            <a href="#pour-qui" className="transition-colors duration-300 hover:text-[#1A237E]">Pour qui</a>
          </nav>

          <button
            onClick={goToApp}
            className="group flex items-center gap-2 rounded-full px-6 py-2.5 text-[13px] font-semibold text-white transition-all duration-300 hover:shadow-lg"
            style={{ background: C.royal }}
          >
            Commencer
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </button>
        </div>
      </header>

      {/* HERO */}
      <section className="relative flex min-h-[100svh] flex-col justify-end px-6 lg:px-10 pt-20 pb-20 overflow-hidden">
        {/* Background decoration */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute top-[15%] right-[-8%] h-[60vh] w-[50vw] rounded-full blur-[140px]" style={{ background: `${C.royalPale}` }} />
          <div className="absolute bottom-[10%] left-[-5%] h-[40vh] w-[35vw] rounded-full blur-[120px]" style={{ background: `${C.terraPale}` }} />
          {/* subtle horizontal rules */}
          <div className="absolute inset-0 opacity-[0.035]" style={{
            backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 119px, ${C.border} 119px, ${C.border} 120px)`,
          }} />
        </div>

        {/* marquee background */}
        <div className="absolute top-[16vh] left-0 right-0 space-y-6 pointer-events-none">
          <MarqueeRow />
          <MarqueeRow reverse />
        </div>

        <div className="relative z-10 mx-auto w-full max-w-7xl">
          <Reveal>
            <div className="flex items-center gap-3 mb-8">
              <span className="h-px w-12" style={{ background: C.terra }} />
              <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>
                Patrimoine historique français
              </span>
            </div>
          </Reveal>

          <Reveal delay={120}>
            <h1
              className="max-w-5xl text-[clamp(3.2rem,8vw,7.5rem)] font-light leading-[0.93] tracking-[-0.025em]"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
            >
              Trouvez{' '}
              <em className="italic" style={{ color: C.royal }}>toutes les aides</em>
              <br />
              pour restaurer
              <br />
              votre <em className="italic" style={{ color: C.terra }}>patrimoine</em>
            </h1>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-12 flex flex-col sm:flex-row items-start gap-12 sm:items-end justify-between">
              <p className="max-w-lg text-[17px] leading-[1.75]" style={{ color: C.textMuted }}>
                Patrys identifie les subventions, déductions fiscales et dispositifs de mécénat
                auxquels vos monuments sont éligibles — puis vous aide à monter vos dossiers à l'aide de l'IA.
              </p>

              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5 shrink-0">
                <button
                  onClick={goToApp}
                  className="group relative inline-flex items-center gap-3 px-8 py-4 text-[14px] font-semibold uppercase tracking-[0.08em] text-white transition-all duration-400 hover:shadow-xl"
                  style={{ background: C.royal }}
                >
                  Lancer mon diagnostic
                  <ArrowRight className="h-4 w-4 transition-transform duration-400 group-hover:translate-x-1" />
                </button>
                <a
                  href="#methode"
                  className="text-[14px] font-medium transition-colors duration-300 hover:opacity-70"
                  style={{ color: C.terra }}
                >
                  Comment ça marche ?
                </a>
              </div>
            </div>
          </Reveal>

          <Reveal delay={350}>
            <div className="mt-10 flex flex-wrap items-center gap-8 text-[14px] font-medium" style={{ color: C.textLight }}>
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" style={{ color: C.terra }} />Recherche d'aide gratuite
              </span>
              <span className="flex items-center gap-2">
                <Shield className="h-4 w-4" style={{ color: C.royal }} />Données sécurisées
              </span>
              <span className="flex items-center gap-2">
                <Clock className="h-4 w-4" style={{ color: C.terra }} />Résultat en 2 minutes
              </span>
            </div>
          </Reveal>
        </div>

        {/* scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-pulse" style={{ color: C.textLight }}>
          <ChevronDown className="h-5 w-5 opacity-40" />
        </div>
      </section>

      {/* CHIFFRES */}
      <section className="relative py-24 px-6 lg:px-10" style={{ background: C.bgAlt }}>
        <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(to right, transparent, ${C.border}, transparent)` }} />
        <div className="mx-auto max-w-7xl">
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-y-14 gap-x-8">
            {([
              { n: 440000, s: '', label: 'Monuments en France' },
              { n: 150, s: '+', label: 'Aides référencées' },
              { n: 13, s: '', label: 'Régions couvertes' },
            ] as const).map((d, i) => (
              <Reveal key={d.label} delay={i * 100}>
                <div className="group">
                  <div
                    className="text-[clamp(2.8rem,5vw,4.5rem)] font-light tracking-[-0.02em]"
                    style={{ fontFamily: "'Cormorant Garamond', serif", color: C.royal }}
                  >
                    <Counter to={d.n} suffix={d.s} />
                  </div>
                  <div className="mt-3 flex items-center gap-3">
                    <span className="h-px w-6 transition-all duration-700 group-hover:w-12" style={{ background: C.terra }} />
                    <span className="text-[13px] font-semibold uppercase tracking-[0.15em]" style={{ color: C.textLight }}>{d.label}</span>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
        <div className="absolute inset-x-0 bottom-0 h-px" style={{ background: `linear-gradient(to right, transparent, ${C.border}, transparent)` }} />
      </section>

      {/* FONCTIONNALITES */}
      <section id="fonctionnalites" className="py-32 px-6 lg:px-10" style={{ background: C.bg }}>
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8 mb-20">
            <Reveal>
              <div>
                <div className="flex items-center gap-3 mb-5">
                  <span className="h-px w-12" style={{ background: C.terra }} />
                  <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>Fonctionnalités</span>
                </div>
                <h2
                  className="max-w-lg text-[clamp(2.2rem,4vw,3.8rem)] font-light leading-[1.1] tracking-[-0.02em]"
                  style={{ fontFamily: "'Cormorant Garamond', serif" }}
                >
                  Tout pour financer<br />
                  <em className="italic" style={{ color: C.terra }}>vos travaux</em>
                </h2>
              </div>
            </Reveal>
            <Reveal delay={120}>
              <p className="max-w-md text-[16px] leading-[1.8] lg:text-right" style={{ color: C.textMuted }}>
                De l'identification des aides à la constitution de vos dossiers, Patrys vous accompagne à chaque étape.
              </p>
            </Reveal>
          </div>

          <div className="grid gap-px sm:grid-cols-2 lg:grid-cols-3 rounded-lg overflow-hidden" style={{ background: C.border }}>
            {([
              { icon: Landmark, title: 'Fiche monument', desc: 'Centralisez toutes les données de votre bien : protection, état, travaux prévus, photos.', num: '01' },
              { icon: Building2, title: 'Base Patrys', desc: 'Les informations de votre monument pré-remplies avec les données officielles du Ministère de la Culture.', num: '02' },
              { icon: Search, title: 'Diagnostic intelligent', desc: "Croisez les caractéristiques de votre monument avec l'ensemble des dispositifs d'aide — DRAC, régions, fondations, fiscal.", num: '03' },
              { icon: Euro, title: "Catalogue d'aides complet", desc: 'Plus de 150 dispositifs agrégés : subventions, prêts, déductions fiscales, mécénat, labels patrimoniaux.', num: '04' },
              { icon: FileCheck, title: 'Gestion de dossiers', desc: "Constituez vos demandes pas à pas : checklists, pièces jointes, jalons — avec l'IA pour vous aider à rédiger.", num: '05' },
              { icon: TrendingUp, title: 'Tableaux de bord', desc: "Suivez l'avancement de vos dossiers, les échéances et le montant total de vos financements.", num: '06' },
            ] as const).map((f, i) => (
              <Reveal key={f.title} delay={i * 70}>
                <div className="group relative h-full p-8 lg:p-10 transition-all duration-500" style={{ background: C.bgAlt }}>
                  <div className="flex items-start justify-between mb-8">
                    <span className="text-[13px] font-semibold tracking-[0.15em]" style={{ color: C.textLight }}>{f.num}</span>
                    <div
                      className="flex h-11 w-11 items-center justify-center rounded-full border transition-all duration-500 group-hover:scale-105"
                      style={{ borderColor: `${C.royal}20`, color: C.royal }}
                    >
                      <f.icon className="h-[17px] w-[17px]" />
                    </div>
                  </div>
                  <h3
                    className="text-[20px] font-normal mb-3"
                    style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
                  >
                    {f.title}
                  </h3>
                  <p className="text-[15px] leading-[1.75]" style={{ color: C.textMuted }}>{f.desc}</p>
                  {/* hover accent line */}
                  <div
                    className="absolute bottom-0 left-8 right-8 h-[2px] scale-x-0 group-hover:scale-x-100 transition-transform duration-700 origin-left"
                    style={{ background: C.terra }}
                  />
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* METHODE — pipeline en 4 étapes */}
      <section id="methode" className="py-32 px-6 lg:px-10 relative" style={{ background: C.bgAlt }}>
        <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(to right, transparent, ${C.border}, transparent)` }} />

        <div className="mx-auto max-w-7xl">
          <Reveal>
            <div className="flex items-center gap-3 mb-5">
              <span className="h-px w-12" style={{ background: C.terra }} />
              <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>Méthode</span>
            </div>
            <h2
              className="max-w-xl text-[clamp(2.2rem,4vw,3.8rem)] font-light leading-[1.1] tracking-[-0.02em] mb-20"
              style={{ fontFamily: "'Cormorant Garamond', serif" }}
            >
              4 étapes vers votre{' '}
              <em className="italic" style={{ color: C.terra }}>financement</em>
            </h2>
          </Reveal>

          <div className="grid gap-6 lg:grid-cols-4">
            {([
              {
                icon: Landmark,
                title: 'Trouvez votre monument',
                desc: "Renseignez votre bien ou importez-le depuis la base de monuments. Localisation, protection, état : tout est centralisé.",
                num: '01',
                accent: C.royal,
                accentPale: C.royalPale,
                details: ['Pré-remplissage administratif', 'Photos & documents', 'Données de protection'],
              },
              {
                icon: Search,
                title: 'Lancez le diagnostic',
                desc: "Notre moteur croise votre situation avec plus de 150 dispositifs — DRAC, régions, fondations, fiscal, mécénat — et identifie vos éligibilités.",
                num: '02',
                accent: C.terra,
                accentPale: C.terraPale,
                details: ['150+ dispositifs', 'Résultat en 2 minutes', 'National & régional'],
              },
              {
                icon: FileCheck,
                title: 'Constituez vos dossiers',
                desc: "Montez vos demandes de subvention pas à pas — et laissez l'IA vous aider à rédiger lettres de motivation, argumentaires et descriptions de projet.",
                num: '03',
                accent: C.royal,
                accentPale: C.royalPale,
                details: ['Rédaction assistée par IA', 'Checklists guidées', 'Pièces jointes'],
              },
              {
                icon: TrendingUp,
                title: 'Suivez vos financements',
                desc: "Pilotez l'avancement de tous vos dossiers, suivez les échéances et visualisez le montant total de vos financements obtenus.",
                num: '04',
                accent: C.terra,
                accentPale: C.terraPale,
                details: ['Vue consolidée', 'Échéances', 'Montants obtenus'],
              },
            ] as const).map((f, i) => (
              <Reveal key={f.title} delay={i * 100}>
                <div className="group relative flex flex-col h-full border p-8 lg:p-9 transition-all duration-500 hover:shadow-lg hover:shadow-black/[0.03]" style={{ borderColor: C.border, background: C.bgAlt }}>
                  {/* step number — large watermark */}
                  <span
                    className="absolute top-4 right-6 text-[5.5rem] font-light leading-none opacity-[0.04] pointer-events-none"
                    style={{ fontFamily: "'Cormorant Garamond', serif", color: f.accent }}
                  >
                    {f.num}
                  </span>

                  {/* icon */}
                  <div
                    className="flex h-12 w-12 items-center justify-center rounded-full mb-7 transition-all duration-500 group-hover:scale-105"
                    style={{ background: f.accentPale, color: f.accent }}
                  >
                    <f.icon className="h-[18px] w-[18px]" />
                  </div>

                  {/* step label */}
                  <span className="text-[11px] font-semibold uppercase tracking-[0.18em] mb-3" style={{ color: f.accent }}>
                    Étape {f.num}
                  </span>

                  <h3
                    className="text-[22px] font-normal mb-3"
                    style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
                  >
                    {f.title}
                  </h3>
                  <p className="flex-1 text-[14.5px] leading-[1.75] mb-8" style={{ color: C.textMuted }}>{f.desc}</p>

                  {/* detail tags */}
                  <ul className="space-y-2.5 border-t pt-6" style={{ borderColor: C.border }}>
                    {f.details.map((d) => (
                      <li key={d} className="flex items-center gap-2.5 text-[12px] font-medium uppercase tracking-[0.08em]" style={{ color: C.textLight }}>
                        <span className="h-1 w-1 rounded-full shrink-0" style={{ background: f.accent }} />
                        {d}
                      </li>
                    ))}
                  </ul>

                  {/* hover accent line */}
                  <div
                    className="absolute bottom-0 left-8 right-8 h-[2px] scale-x-0 group-hover:scale-x-100 transition-transform duration-700 origin-left"
                    style={{ background: f.accent }}
                  />

                  {/* connector arrow between cards on desktop */}
                  {i < 3 && (
                    <div
                      className="hidden lg:flex absolute -right-3.5 top-1/2 -translate-y-1/2 z-20 h-7 w-7 items-center justify-center rounded-full"
                      style={{ background: C.bgAlt, border: `1px solid ${C.border}` }}
                    >
                      <ArrowRight className="h-3 w-3" style={{ color: f.accent }} />
                    </div>
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* POUR QUI */}
      <section id="pour-qui" className="py-32 px-6 lg:px-10 relative" style={{ background: C.bg }}>
        <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(to right, transparent, ${C.border}, transparent)` }} />

        <div className="mx-auto max-w-7xl">
          <Reveal>
            <div className="flex items-center gap-3 mb-5">
              <span className="h-px w-12" style={{ background: C.terra }} />
              <span className="text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.terra }}>Pour qui</span>
            </div>
            <h2
              className="max-w-xl text-[clamp(2.2rem,4vw,3.8rem)] font-light leading-[1.1] tracking-[-0.02em] mb-20"
              style={{ fontFamily: "'Cormorant Garamond', serif" }}
            >
              Tous les acteurs du{' '}
              <em className="italic" style={{ color: C.terra }}>patrimoine</em>
            </h2>
          </Reveal>

          <div className="grid gap-6 lg:grid-cols-3">
            {([
              {
                icon: Building2,
                title: 'Communes',
                desc: "Identifiez les financements pour vos bâtiments publics. Pilotez la restauration de votre patrimoine communal en toute clarté.",
                tags: ['Aides aux collectivités', 'Soutien Européen', 'Pré-remplissage automatique'],
                tint: C.royalPale,
                accent: C.royal,
              },
              {
                icon: Users,
                title: 'Propriétaires privés',
                desc: "Château, manoir, demeure — découvrez subventions, fiscal et mécénat accessibles aux particuliers.",
                tags: ['Déductions fiscales', 'Subventions', 'Mécénat'],
                tint: C.terraPale,
                accent: C.terra,
              },
              {
                icon: HardHat,
                title: 'Professionnels BTP',
                desc: "Accédez à des projets de rénovation financés. Collaborez avec les maîtres d'ouvrage pour restaurer le patrimoine bâti.",
                tags: ['CRM prospects', 'Relations clients', 'Architectes partenaires'],
                tint: C.royalPale,
                accent: C.royal,
              },
            ] as const).map((seg, i) => (
              <Reveal key={seg.title} delay={i * 120}>
                <div
                  className="group relative flex flex-col h-full border p-10 transition-all duration-500 hover:shadow-lg hover:shadow-black/[0.03]"
                  style={{ borderColor: C.border, background: C.bgAlt }}
                >
                  {/* icon */}
                  <div
                    className="flex h-14 w-14 items-center justify-center rounded-full mb-8 transition-all duration-500"
                    style={{ background: seg.tint, color: seg.accent }}
                  >
                    <seg.icon className="h-6 w-6" />
                  </div>

                  <h3
                    className="text-[28px] font-normal mb-4"
                    style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
                  >
                    {seg.title}
                  </h3>
                  <p className="flex-1 text-[15px] leading-[1.8] mb-10" style={{ color: C.textMuted }}>{seg.desc}</p>

                  <ul className="space-y-3 border-t pt-6" style={{ borderColor: C.border }}>
                    {seg.tags.map((t) => (
                      <li key={t} className="flex items-center gap-3 text-[13px] font-medium uppercase tracking-[0.08em]" style={{ color: C.textLight }}>
                        <Minus className="h-3 w-3" style={{ color: seg.accent }} />
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA FINAL */}
      <section className="py-32 px-6 lg:px-10 relative" style={{ background: C.bgAlt }}>
        <div className="absolute inset-x-0 top-0 h-px" style={{ background: `linear-gradient(to right, transparent, ${C.border}, transparent)` }} />

        <Reveal>
          <div className="mx-auto max-w-4xl text-center relative overflow-hidden rounded-2xl px-8 py-24 sm:px-16" style={{ background: C.royal }}>
            {/* decorative glows */}
            <div className="pointer-events-none absolute -top-20 right-[-10%] h-60 w-60 rounded-full blur-[100px]" style={{ background: `${C.royalLight}40` }} />
            <div className="pointer-events-none absolute -bottom-20 left-[-10%] h-48 w-48 rounded-full blur-[100px]" style={{ background: `${C.terra}20` }} />

            <div className="relative">
              <h2
                className="text-[clamp(2rem,4vw,3.5rem)] font-light leading-[1.15] tracking-[-0.02em] text-white"
                style={{ fontFamily: "'Cormorant Garamond', serif" }}
              >
                Prêt à financer votre{' '}
                <em className="italic" style={{ color: '#E8C9A0' }}>patrimoine</em> ?
              </h2>
              <p className="mx-auto mt-6 max-w-md text-[16px] leading-[1.8] text-white/50">
                Découvrez en quelques minutes le montant total des aides disponibles pour vos monuments.
              </p>

              <div className="mt-12">
                <button
                  onClick={goToApp}
                  className="group inline-flex items-center gap-3 bg-white px-10 py-4 text-[14px] font-semibold uppercase tracking-[0.08em] transition-all duration-400 hover:shadow-xl"
                  style={{ color: C.royal }}
                >
                  Créer mon compte gratuitement
                  <ArrowRight className="h-4 w-4 transition-transform duration-400 group-hover:translate-x-1" />
                </button>
              </div>
              <p className="mt-6 text-[13px] text-white/30 uppercase tracking-[0.12em]">Aucune carte bancaire requise</p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* FOOTER */}
      <footer className="relative border-t py-12 px-6 lg:px-10" style={{ borderColor: C.border, background: C.bg }}>
        <div className="mx-auto max-w-7xl flex flex-col items-center gap-6">
          <div className="flex items-center gap-2.5 opacity-60">
            <img src="/patrys.png" alt="Patrys" className="h-5" />
            <span
              className="text-[1.15rem] font-light tracking-[-0.01em]"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: C.royal }}
            >
              Patrys
            </span>
          </div>

          <p className="text-[13px] text-center" style={{ color: C.textLight }}>
            La plateforme de financement du patrimoine historique français.
          </p>

          <div className="flex items-center gap-8 text-[12px] uppercase tracking-[0.12em]" style={{ color: C.textLight }}>
            <a href="mailto:paul@monumia.fr" className="transition-colors duration-300 hover:text-[#1A237E]">Contact</a>
            <a href="#" className="transition-colors duration-300 hover:text-[#1A237E]">Mentions légales</a>
          </div>

          <p className="text-[11px] uppercase tracking-[0.15em]" style={{ color: `${C.textLight}80` }}>
            © {new Date().getFullYear()} Patrys. Tous droits réservés.
          </p>
        </div>
      </footer>

      {/* MARQUEE ANIMATION */}
      <style>{`
        @keyframes marquee {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        @keyframes marquee-reverse {
          from { transform: translateX(-50%); }
          to { transform: translateX(0); }
        }
        .animate-marquee {
          animation: marquee 120s linear infinite;
        }
        .animate-marquee-reverse {
          animation: marquee-reverse 120s linear infinite;
        }
      `}</style>
    </div>
  );
}
