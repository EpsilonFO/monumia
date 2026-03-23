import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import {
  Search,
  FileCheck,
  Euro,
  ArrowRight,
  Building2,
  Users,
  HardHat,
  Sparkles,
  TrendingUp,
  ChevronRight,
  Landmark,
  MapPin,
  Clock,
  Shield,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

/* ────────────────────────────────────────────
   Utilities
   ──────────────────────────────────────────── */

function useInView(threshold = 0.2) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setInView(true); obs.disconnect(); } }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

function Reveal({ children, className = '', delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const { ref, inView } = useInView(0.12);
  const [show, setShow] = useState(false);
  useEffect(() => { if (inView) { const t = setTimeout(() => setShow(true), delay); return () => clearTimeout(t); } }, [inView, delay]);
  return (
    <div ref={ref} className={`transition-all duration-700 ease-out ${show ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'} ${className}`}>
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
    const step = to / 50;
    const id = setInterval(() => { cur += step; if (cur >= to) { setVal(to); clearInterval(id); } else setVal(Math.floor(cur)); }, 30);
    return () => clearInterval(id);
  }, [inView, to]);
  return <span ref={ref}>{val.toLocaleString('fr-FR')}{suffix}</span>;
}

/* ────────────────────────────────────────────
   Landing Page
   ──────────────────────────────────────────── */

export function LandingPage() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', fn, { passive: true });
    return () => window.removeEventListener('scroll', fn);
  }, []);

  return (
    <div className="min-h-screen bg-[#F8F9FC] text-foreground antialiased">

      {/* ═══════════════ NAV ═══════════════ */}
      <header
        className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
          scrolled ? 'bg-white/70 backdrop-blur-2xl shadow-[0_1px_2px_rgba(0,0,0,0.04)] border-b border-slate-200/50' : ''
        }`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <img src="/patrialta.png" alt="PatriAlta" className="h-7" />

          <nav className="hidden md:flex items-center gap-10 text-[13px] font-medium text-slate-500">
            <a href="#fonctionnalites" className="hover:text-foreground transition-colors">Fonctionnalités</a>
            <a href="#methode" className="hover:text-foreground transition-colors">Méthode</a>
            <a href="#pour-qui" className="hover:text-foreground transition-colors">Pour qui</a>
          </nav>

          <Button size="sm" className="rounded-full px-5" onClick={() => navigate('/login')}>
            Commencer
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </div>
      </header>

      {/* ═══════════════ HERO ═══════════════ */}
      <section className="relative isolate flex min-h-[100svh] flex-col items-center justify-center px-6 pt-24 pb-20 text-center overflow-hidden">
        {/* background decoration */}
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute -top-40 right-1/4 h-[600px] w-[600px] rounded-full bg-gradient-to-br from-primary/8 to-blue-200/10 blur-3xl" />
          <div className="absolute bottom-0 left-1/4 h-[500px] w-[500px] rounded-full bg-gradient-to-tr from-slate-200/30 to-transparent blur-3xl" />
          <svg className="absolute inset-0 h-full w-full opacity-[0.018]" xmlns="http://www.w3.org/2000/svg">
            <defs><pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M 60 0 L 0 0 0 60" fill="none" stroke="currentColor" strokeWidth="0.5" /></pattern></defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>
        </div>

        <Reveal>
          <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-accent/15 bg-accent/[0.06] px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-accent">
            <Sparkles className="h-3.5 w-3.5" />
            Patrimoine historique
          </span>
        </Reveal>

        <Reveal delay={80}>
          <h1 className="mx-auto max-w-3xl text-[clamp(2.5rem,6vw,4.5rem)] font-extrabold leading-[1.08] tracking-tight">
            Trouvez <span className="bg-gradient-to-r from-primary to-blue-800 bg-clip-text text-transparent">toutes les aides</span> pour
            restaurer votre <span className="text-accent">patrimoine</span>
          </h1>
        </Reveal>

        <Reveal delay={160}>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            PatriAlta identifie les subventions, déductions fiscales et dispositifs de mécénat
            auxquels vos monuments sont éligibles — puis vous aide à monter vos dossiers.
          </p>
        </Reveal>

        <Reveal delay={240}>
          <div className="mt-10 flex flex-col sm:flex-row items-center gap-4">
            <Button size="lg" className="h-12 rounded-full px-8 text-[15px] shadow-xl shadow-primary/15" onClick={() => navigate('/login')}>
              Lancer mon diagnostic gratuit
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button variant="ghost" size="lg" className="h-12 rounded-full px-8 text-[15px] text-muted-foreground" asChild>
              <a href="#methode">Comment ça marche ?</a>
            </Button>
          </div>
        </Reveal>

        <Reveal delay={320}>
          <div className="mt-12 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-[13px] text-muted-foreground">
            <span className="flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-500" />100 % gratuit</span>
            <span className="flex items-center gap-1.5"><Shield className="h-4 w-4 text-primary" />Données sécurisées</span>
            <span className="flex items-center gap-1.5"><Clock className="h-4 w-4 text-accent" />Résultat en 2 min</span>
          </div>
        </Reveal>
      </section>

      {/* ═══════════════ CHIFFRES ═══════════════ */}
      <section className="border-y border-slate-200/60 bg-white py-16">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-y-10 px-6 lg:grid-cols-4">
          {([
            { n: 440000, s: '', label: 'Monuments en France', icon: Landmark },
            { n: 150, s: '+', label: 'Aides référencées', icon: Euro },
            { n: 18, s: '', label: 'Régions couvertes', icon: MapPin },
            { n: 50, s: '%', label: 'Financement moyen', icon: TrendingUp },
          ] as const).map((d) => (
            <div key={d.label} className="flex flex-col items-center text-center gap-1">
              <d.icon className="mb-2 h-5 w-5 text-primary/60" />
              <span className="text-3xl font-bold tracking-tight"><Counter to={d.n} suffix={d.s} /></span>
              <span className="text-xs font-medium text-muted-foreground">{d.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ═══════════════ FONCTIONNALITÉS ═══════════════ */}
      <section id="fonctionnalites" className="py-28 px-6">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="text-center text-xs font-bold uppercase tracking-[0.2em] text-accent">Fonctionnalités</p>
            <h2 className="mx-auto mt-3 max-w-xl text-center text-3xl font-bold tracking-tight sm:text-4xl">
              Tout pour financer vos travaux
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-center text-muted-foreground">
              De l'identification des aides à la constitution de vos dossiers, PatriAlta vous accompagne à chaque étape.
            </p>
          </Reveal>

          <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {([
              { icon: Search, title: 'Diagnostic intelligent', desc: "Croisez les caractéristiques de votre monument avec l'ensemble des dispositifs d'aide — DRAC, régions, fondations, fiscal.", color: 'from-blue-800 to-indigo-900' },
              { icon: Euro, title: "Catalogue d'aides complet", desc: 'Plus de 150 dispositifs agrégés : subventions, prêts, déductions fiscales, mécénat, labels patrimoniaux.', color: 'from-amber-500 to-orange-600' },
              { icon: FileCheck, title: 'Gestion de dossiers', desc: 'Constituez vos demandes pas à pas : checklists, pièces jointes, jalons et collaborateurs.', color: 'from-blue-700 to-blue-900' },
              { icon: Landmark, title: 'Fiche monument', desc: 'Centralisez toutes les données de votre bien : protection, état, travaux prévus, photos.', color: 'from-indigo-700 to-blue-900' },
              { icon: Building2, title: 'Base Mérimée', desc: 'Importez en un clic les données officielles du Ministère de la Culture.', color: 'from-orange-500 to-amber-600' },
              { icon: TrendingUp, title: 'Tableaux de bord', desc: "Suivez l'avancement de vos dossiers, les échéances et le montant total de vos financements.", color: 'from-blue-700 to-indigo-800' },
            ] as const).map((f, i) => (
              <Reveal key={f.title} delay={i * 60}>
                <div className="group h-full rounded-2xl border border-slate-200/70 bg-white p-7 transition-all duration-300 hover:shadow-lg hover:shadow-blue-100/40 hover:border-slate-300">
                  <div className={`mb-5 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${f.color} text-white shadow-sm`}>
                    <f.icon className="h-[18px] w-[18px]" />
                  </div>
                  <h3 className="text-[15px] font-semibold mb-1.5">{f.title}</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ MÉTHODE (3 étapes) ═══════════════ */}
      <section id="methode" className="py-28 px-6 bg-white">
        <div className="mx-auto max-w-4xl">
          <Reveal>
            <p className="text-center text-xs font-bold uppercase tracking-[0.2em] text-accent">Méthode</p>
            <h2 className="mt-3 text-center text-3xl font-bold tracking-tight sm:text-4xl">3 étapes vers votre <span className="text-accent">financement</span></h2>
          </Reveal>

          <div className="relative mt-20">
            {/* vertical connector */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-primary/20 via-primary/10 to-transparent hidden md:block md:left-1/2 md:-translate-x-px" />

            {([
              { step: '01', title: 'Décrivez votre monument', desc: 'Renseignez localisation, protection, état de conservation et travaux envisagés. Importez depuis Mérimée si votre bien est répertorié.', icon: Landmark },
              { step: '02', title: 'Lancez le diagnostic', desc: "Notre moteur croise votre situation avec l'ensemble des aides nationales, régionales et privées. Résultat instantané.", icon: Sparkles },
              { step: '03', title: 'Constituez vos dossiers', desc: 'Créez vos demandes de subvention avec checklists complètes, suivi documentaire et collaboration.', icon: FileCheck },
            ] as const).map((s, i) => (
              <Reveal key={s.step} delay={i * 120}>
                <div className={`relative mb-16 last:mb-0 flex flex-col md:flex-row items-start gap-6 md:gap-12 ${i % 2 === 1 ? 'md:flex-row-reverse md:text-right' : ''}`}>
                  {/* bullet */}
                  <div className="relative z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border-2 border-primary/20 bg-[#F8F9FC] shadow-sm md:mx-auto">
                    <s.icon className="h-5 w-5 text-primary" />
                    <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">{s.step}</span>
                  </div>
                  {/* text */}
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold">{s.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground max-w-sm">{s.desc}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ POUR QUI ═══════════════ */}
      <section id="pour-qui" className="py-28 px-6">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="text-center text-xs font-bold uppercase tracking-[0.2em] text-accent">Pour qui</p>
            <h2 className="mt-3 text-center text-3xl font-bold tracking-tight sm:text-4xl">
              Tous les acteurs du <span className="text-accent">patrimoine</span>
            </h2>
          </Reveal>

          <div className="mt-16 grid gap-6 md:grid-cols-3">
            {([
              {
                icon: Building2, title: 'Communes',
                desc: "Identifiez les financements pour vos bâtiments publics. Pilotez la restauration de votre patrimoine communal en toute clarté.",
                tags: ['Aides collectivités', 'Multi-monuments', 'Échéances'],
                bg: 'bg-blue-50/60', border: 'border-blue-200/50',
              },
              {
                icon: Users, title: 'Propriétaires privés',
                desc: "Château, manoir, demeure — découvrez subventions, fiscal et mécénat accessibles aux particuliers.",
                tags: ['Déductions fiscales', 'Fondation du Patrimoine', 'Mécénat'],
                bg: 'bg-indigo-50/60', border: 'border-indigo-200/50',
              },
              {
                icon: HardHat, title: 'Professionnels BTP',
                desc: "Accédez à des projets de rénovation financés. Gérez vos prospects grâce au CRM intégré.",
                tags: ['CRM prospects', 'Intelligence financement', 'Pipeline'],
                bg: 'bg-amber-50/60', border: 'border-amber-200/50',
              },
            ] as const).map((seg, i) => (
              <Reveal key={seg.title} delay={i * 80}>
                <div className={`flex h-full flex-col rounded-2xl border ${seg.border} ${seg.bg} p-8`}>
                  <seg.icon className="mb-5 h-9 w-9 text-foreground/60" />
                  <h3 className="text-xl font-bold mb-2">{seg.title}</h3>
                  <p className="flex-1 text-sm leading-relaxed text-muted-foreground mb-6">{seg.desc}</p>
                  <ul className="space-y-1.5">
                    {seg.tags.map((t) => (
                      <li key={t} className="flex items-center gap-2 text-[13px] text-foreground/75">
                        <ChevronRight className="h-3 w-3 text-primary" />{t}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ CTA FINAL ═══════════════ */}
      <section className="px-6 pb-28">
        <Reveal>
          <div className="relative mx-auto max-w-4xl overflow-hidden rounded-[2rem] bg-gradient-to-br from-blue-950 via-[#0a1340] to-blue-950 px-8 py-20 text-center sm:px-16">
            <div className="pointer-events-none absolute -top-32 right-0 h-80 w-80 rounded-full bg-blue-400/8 blur-[100px]" />
            <div className="pointer-events-none absolute -bottom-32 left-0 h-64 w-64 rounded-full bg-amber-500/8 blur-[100px]" />

            <div className="relative">
              <h2 className="text-3xl font-bold text-white sm:text-4xl tracking-tight">
                Prêt à financer votre patrimoine ?
              </h2>
              <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-blue-200/60">
                Découvrez en quelques minutes le montant total des aides disponibles pour vos monuments.
              </p>
              <Button
                size="lg"
                className="mt-8 h-12 rounded-full bg-white px-8 text-[15px] font-semibold text-slate-900 shadow-xl hover:bg-slate-100"
                onClick={() => navigate('/login')}
              >
                Créer mon compte gratuitement
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <p className="mt-4 text-xs text-blue-300/40">Aucune carte bancaire requise</p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ═══════════════ FOOTER ═══════════════ */}
      <footer className="border-t border-slate-200/60 bg-white py-10 px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 md:flex-row">
          <img src="/patrialta.png" alt="PatriAlta" className="h-6" />
          <p className="text-xs text-muted-foreground">La plateforme de financement du patrimoine historique français.</p>
          <div className="flex gap-6 text-xs text-muted-foreground">
            <a href="#" className="hover:text-foreground transition-colors">Mentions légales</a>
            <a href="#" className="hover:text-foreground transition-colors">Contact</a>
          </div>
        </div>
        <p className="mt-6 text-center text-[11px] text-slate-400">© {new Date().getFullYear()} PatriAlta. Tous droits réservés.</p>
      </footer>
    </div>
  );
}
