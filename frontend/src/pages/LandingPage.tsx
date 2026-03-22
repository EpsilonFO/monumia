import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import {
  Landmark,
  Search,
  FileCheck,
  Euro,
  ArrowRight,
  ChevronDown,
  Building2,
  Users,
  HardHat,
  CheckCircle2,
  Sparkles,
  Shield,
  Clock,
  TrendingUp,
  MapPin,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

/* ─── Animated counter ─── */
function AnimatedNumber({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const duration = 2000;
          const steps = 60;
          const increment = target / steps;
          let current = 0;
          const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
              setValue(target);
              clearInterval(timer);
            } else {
              setValue(Math.floor(current));
            }
          }, duration / steps);
        }
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return (
    <span ref={ref}>
      {value.toLocaleString('fr-FR')}
      {suffix}
    </span>
  );
}

/* ─── Reveal on scroll ─── */
function Reveal({ children, className = '', delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setVisible(true), delay);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [delay]);

  return (
    <div
      ref={ref}
      className={`transition-all duration-700 ease-out ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'} ${className}`}
    >
      {children}
    </div>
  );
}

/* ─── Main ─── */
export default function LandingPage() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-white text-foreground overflow-x-hidden">
      {/* ━━━ Navbar ━━━ */}
      <nav
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
          scrolled
            ? 'bg-white/80 backdrop-blur-xl shadow-sm border-b border-stone-200/60'
            : 'bg-transparent'
        }`}
      >
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center">
            <img src="/patrialta.png" alt="PatriAlta" className="h-8" />
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-muted-foreground">
            <a href="#fonctionnalites" className="hover:text-foreground transition-colors">Fonctionnalités</a>
            <a href="#comment-ca-marche" className="hover:text-foreground transition-colors">Comment ça marche</a>
            <a href="#qui" className="hover:text-foreground transition-colors">Pour qui</a>
          </div>
          <Button size="sm" onClick={() => navigate('/login')}>
            Commencer
            <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Button>
        </div>
      </nav>

      {/* ━━━ Hero ━━━ */}
      <section className="relative min-h-[100svh] flex items-center justify-center px-6 pt-20">
        {/* Background pattern */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-gradient-to-bl from-amber-100/40 via-orange-50/20 to-transparent rounded-full -translate-y-1/3 translate-x-1/4" />
          <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-gradient-to-tr from-stone-100/60 via-amber-50/30 to-transparent rounded-full translate-y-1/3 -translate-x-1/4" />
          {/* Grid */}
          <div
            className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
              backgroundSize: '80px 80px',
            }}
          />
        </div>

        <div className="relative max-w-4xl mx-auto text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/5 border border-primary/10 text-primary text-sm font-medium">
            <Sparkles className="h-3.5 w-3.5" />
            Plateforme de financement du patrimoine
          </div>

          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.08]">
            <span className="text-foreground">Financez la rénovation</span>
            <br />
            <span className="bg-gradient-to-r from-primary via-amber-600 to-primary bg-clip-text text-transparent">
              de votre patrimoine
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Identifiez en quelques clics toutes les aides disponibles pour vos monuments historiques.
            Constituez vos dossiers, suivez vos demandes, et maximisez vos financements.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
            <Button size="lg" className="text-base px-8 h-12 rounded-xl shadow-lg shadow-primary/20" onClick={() => navigate('/login')}>
              Diagnostiquer mon monument
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button variant="outline" size="lg" className="text-base px-8 h-12 rounded-xl" asChild>
              <a href="#comment-ca-marche">
                Voir comment ça marche
              </a>
            </Button>
          </div>

          {/* Social proof */}
          <div className="flex items-center justify-center gap-8 pt-8 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              100% gratuit
            </div>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-blue-600" />
              Données sécurisées
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-600" />
              Résultats en 2 min
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <a
          href="#chiffres"
          className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-muted-foreground/40 hover:text-muted-foreground/60 transition-colors"
        >
          <ChevronDown className="h-5 w-5 animate-bounce" />
        </a>
      </section>

      {/* ━━━ Chiffres ━━━ */}
      <section id="chiffres" className="py-24 bg-gradient-to-b from-stone-50/50 to-white">
        <div className="max-w-5xl mx-auto px-6">
          <Reveal>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12">
              {[
                { value: 440000, suffix: '', label: 'Monuments en France', icon: Landmark },
                { value: 150, suffix: '+', label: 'Aides référencées', icon: Euro },
                { value: 18, suffix: '', label: 'Régions couvertes', icon: MapPin },
                { value: 50, suffix: '%', label: "De financement moyen obtenu", icon: TrendingUp },
              ].map((stat) => (
                <div key={stat.label} className="text-center space-y-2">
                  <stat.icon className="h-6 w-6 mx-auto text-primary/70 mb-3" />
                  <div className="text-3xl sm:text-4xl font-bold text-foreground">
                    <AnimatedNumber target={stat.value} suffix={stat.suffix} />
                  </div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ━━━ Fonctionnalités ━━━ */}
      <section id="fonctionnalites" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <div className="text-center max-w-2xl mx-auto mb-16 space-y-4">
              <p className="text-sm font-semibold text-primary uppercase tracking-widest">Fonctionnalités</p>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
                Tout ce qu'il faut pour financer vos travaux
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                De l'identification des aides à la constitution de vos dossiers, PatriAlta vous accompagne à chaque étape.
              </p>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Search,
                title: 'Diagnostic intelligent',
                desc: "Analysez votre monument et découvrez instantanément toutes les aides auxquelles vous êtes éligible — DRAC, régions, fondations, fiscal.",
                accent: 'from-amber-500 to-orange-600',
              },
              {
                icon: Euro,
                title: 'Catalogue d\'aides complet',
                desc: "Plus de 150 dispositifs de financement agrégés : subventions directes, prêts, déductions fiscales, mécénat, labels.",
                accent: 'from-emerald-500 to-teal-600',
              },
              {
                icon: FileCheck,
                title: 'Gestion de dossiers',
                desc: 'Constituez vos demandes de subvention pas à pas avec checklists, suivi documentaire et jalons.',
                accent: 'from-blue-500 to-indigo-600',
              },
              {
                icon: Landmark,
                title: 'Fiche monument',
                desc: 'Centralisez toutes les informations de votre bien : statut de protection, état, travaux prévus, photos.',
                accent: 'from-violet-500 to-purple-600',
              },
              {
                icon: Building2,
                title: 'Base Mérimée intégrée',
                desc: 'Retrouvez et importez les données officielles du Ministère de la Culture en un clic.',
                accent: 'from-rose-500 to-pink-600',
              },
              {
                icon: TrendingUp,
                title: 'Suivi & tableaux de bord',
                desc: "Visualisez l'avancement de vos dossiers, les échéances à venir et le montant total de vos financements.",
                accent: 'from-cyan-500 to-blue-600',
              },
            ].map((feat, i) => (
              <Reveal key={feat.title} delay={i * 80}>
                <div className="group relative h-full rounded-2xl border border-stone-200/80 bg-white p-7 hover:shadow-lg hover:shadow-stone-200/50 hover:border-stone-300/80 transition-all duration-300">
                  <div className={`inline-flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br ${feat.accent} text-white mb-5`}>
                    <feat.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{feat.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{feat.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ━━━ Comment ça marche ━━━ */}
      <section id="comment-ca-marche" className="py-24 bg-stone-50/70 px-6">
        <div className="max-w-5xl mx-auto">
          <Reveal>
            <div className="text-center max-w-2xl mx-auto mb-16 space-y-4">
              <p className="text-sm font-semibold text-primary uppercase tracking-widest">Comment ça marche</p>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
                3 étapes vers votre financement
              </h2>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connector line */}
            <div className="hidden md:block absolute top-16 left-[16.5%] right-[16.5%] h-px bg-gradient-to-r from-primary/20 via-primary/40 to-primary/20" />

            {[
              {
                step: '01',
                title: 'Décrivez votre monument',
                desc: 'Renseignez les caractéristiques de votre bien : localisation, protection, état de conservation, travaux envisagés.',
                icon: Landmark,
              },
              {
                step: '02',
                title: 'Lancez le diagnostic',
                desc: "Notre moteur analyse votre situation et identifie toutes les aides compatibles parmi les dispositifs nationaux, régionaux et privés.",
                icon: Sparkles,
              },
              {
                step: '03',
                title: 'Constituez vos dossiers',
                desc: 'Créez et suivez vos demandes de subvention avec des checklists complètes et un suivi documentaire intégré.',
                icon: FileCheck,
              },
            ].map((step, i) => (
              <Reveal key={step.step} delay={i * 120}>
                <div className="relative text-center space-y-4">
                  <div className="relative mx-auto w-16 h-16 rounded-2xl bg-white border-2 border-primary/20 flex items-center justify-center shadow-sm">
                    <step.icon className="h-7 w-7 text-primary" />
                    <span className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center">
                      {step.step}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold">{step.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed max-w-xs mx-auto">{step.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ━━━ Pour qui ━━━ */}
      <section id="qui" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <Reveal>
            <div className="text-center max-w-2xl mx-auto mb-16 space-y-4">
              <p className="text-sm font-semibold text-primary uppercase tracking-widest">Pour qui</p>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
                Une plateforme pour tous les acteurs du patrimoine
              </h2>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: Building2,
                title: 'Communes',
                desc: 'Identifiez les financements pour vos bâtiments publics historiques. Pilotez la restauration de votre patrimoine communal avec une vision claire des aides disponibles.',
                features: ['Aides spécifiques collectivités', 'Multi-monuments', 'Suivi des échéances'],
                gradient: 'from-amber-50 to-orange-50',
                border: 'border-amber-200/60',
              },
              {
                icon: Users,
                title: 'Propriétaires privés',
                desc: "Château, manoir, demeure historique — découvrez les subventions, déductions fiscales et dispositifs de mécénat accessibles aux particuliers.",
                features: ['Déductions fiscales', 'Fondation du Patrimoine', 'Mécénat populaire'],
                gradient: 'from-blue-50 to-indigo-50',
                border: 'border-blue-200/60',
              },
              {
                icon: HardHat,
                title: 'Professionnels BTP',
                desc: "Accédez à un vivier de projets de rénovation financés. Suivez vos prospects et identifiez les opportunités grâce à notre CRM intégré.",
                features: ['CRM prospects', 'Intelligence financement', 'Pipeline projets'],
                gradient: 'from-emerald-50 to-teal-50',
                border: 'border-emerald-200/60',
              },
            ].map((segment, i) => (
              <Reveal key={segment.title} delay={i * 100}>
                <div className={`relative rounded-2xl bg-gradient-to-br ${segment.gradient} border ${segment.border} p-8 h-full flex flex-col`}>
                  <segment.icon className="h-10 w-10 text-foreground/70 mb-5" />
                  <h3 className="text-xl font-bold mb-3">{segment.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed mb-6 flex-1">{segment.desc}</p>
                  <ul className="space-y-2">
                    {segment.features.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-sm text-foreground/80">
                        <ChevronRight className="h-3.5 w-3.5 text-primary" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ━━━ CTA ━━━ */}
      <section className="py-24 px-6">
        <Reveal>
          <div className="max-w-4xl mx-auto relative overflow-hidden rounded-3xl bg-gradient-to-br from-stone-900 via-stone-800 to-stone-900 p-12 sm:p-16 text-center">
            {/* Decorative glow */}
            <div className="absolute top-0 right-0 w-96 h-96 bg-primary/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />

            <div className="relative space-y-6">
              <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                Prêt à financer votre patrimoine ?
              </h2>
              <p className="text-stone-300 text-lg max-w-xl mx-auto leading-relaxed">
                Rejoignez PatriAlta et découvrez en quelques minutes le montant total des aides disponibles pour vos monuments.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
                <Button
                  size="lg"
                  className="text-base px-8 h-12 rounded-xl bg-white text-stone-900 hover:bg-stone-100 shadow-lg"
                  onClick={() => navigate('/login')}
                >
                  Créer mon compte gratuitement
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
              <p className="text-stone-500 text-sm">Aucune carte bancaire requise</p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ━━━ Footer ━━━ */}
      <footer className="border-t border-stone-200/80 py-12 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center">
              <img src="/patrialta.png" alt="PatriAlta" className="h-7" />
            </div>
            <p className="text-sm text-muted-foreground">
              La plateforme de financement du patrimoine historique français.
            </p>
            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <a href="#" className="hover:text-foreground transition-colors">Mentions légales</a>
              <a href="#" className="hover:text-foreground transition-colors">Contact</a>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t border-stone-100 text-center text-xs text-muted-foreground">
            © {new Date().getFullYear()} PatriAlta. Tous droits réservés.
          </div>
        </div>
      </footer>
    </div>
  );
}
