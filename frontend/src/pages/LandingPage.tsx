import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { 
  ShieldCheck, 
  Search, 
  ClipboardCheck, 
  Users, 
  Building2, 
  ArrowRight,
  ChevronRight,
  FileText
} from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-slate-900 font-sans">
      {/* Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[oklch(0.30_0.06_250)] rounded-lg flex items-center justify-center">
              <ShieldCheck className="text-white w-5 h-5" />
            </div>
            <span className="text-xl font-bold tracking-tight text-[oklch(0.30_0.06_250)]">Patrialta</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#solutions" className="text-sm font-medium text-slate-600 hover:text-[oklch(0.30_0.06_250)] transition-colors">Solutions</a>
            <a href="#experts" className="text-sm font-medium text-slate-600 hover:text-[oklch(0.30_0.06_250)] transition-colors">Pour les Pros</a>
            <a href="#aides" className="text-sm font-medium text-slate-600 hover:text-[oklch(0.30_0.06_250)] transition-colors">Aides & Subventions</a>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login">
              <Button variant="ghost" className="text-sm font-medium">Connexion</Button>
            </Link>
            <Link to="/login">
              <Button className="bg-[oklch(0.30_0.06_250)] hover:bg-[oklch(0.25_0.05_250)] text-sm font-medium px-5">
                Commencer
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full -z-10">
          <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-[oklch(0.30_0.06_250/0.03)] rounded-full blur-[120px]" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-[oklch(0.30_0.06_250/0.05)] rounded-full blur-[120px]" />
        </div>
        
        <div className="max-w-7xl mx-auto px-4 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 mb-8 animate-fade-in">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Solution Nouvelle Génération</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-slate-900 mb-6 leading-[1.1]">
            Financez et gérez la <br />
            <span className="text-[oklch(0.30_0.06_250)]">restauration de votre patrimoine</span>
          </h1>
          
          <p className="max-w-2xl mx-auto text-lg md:text-xl text-slate-600 mb-10 leading-relaxed">
            Patrialta automatise la recherche de subventions et simplifie le montage de vos dossiers de rénovation pour les monuments historiques.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Link to="/login">
              <Button size="lg" className="bg-[oklch(0.30_0.06_250)] hover:bg-[oklch(0.25_0.05_250)] px-8 text-base h-12 shadow-xl shadow-blue-900/10">
                Identifier mes aides <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
            <Button size="lg" variant="outline" className="px-8 text-base h-12 border-slate-200">
              Découvrir la plateforme
            </Button>
          </div>

          <div className="relative max-w-5xl mx-auto">
            <div className="absolute inset-0 bg-gradient-to-t from-white via-transparent to-transparent z-10 h-40 bottom-0 pointer-events-none" />
            <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden aspect-[16/9] flex items-center justify-center p-8 bg-slate-50">
               {/* Visual Placeholder for Dashboard */}
               <div className="w-full h-full rounded-lg border border-slate-200 bg-white p-6 shadow-sm flex flex-col gap-6">
                 <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                    <div className="flex gap-2 items-center">
                      <div className="w-8 h-8 rounded bg-slate-100" />
                      <div className="w-32 h-4 rounded bg-slate-100" />
                    </div>
                    <div className="w-24 h-8 rounded bg-slate-100" />
                 </div>
                 <div className="grid grid-cols-3 gap-4">
                    <div className="h-32 rounded-lg bg-slate-50 border border-dashed border-slate-200 flex flex-col p-4 gap-2">
                       <div className="w-1/2 h-4 rounded bg-slate-200" />
                       <div className="w-3/4 h-8 rounded bg-[oklch(0.30_0.06_250/0.1)]" />
                    </div>
                    <div className="h-32 rounded-lg bg-slate-50 border border-dashed border-slate-200 flex flex-col p-4 gap-2">
                       <div className="w-1/2 h-4 rounded bg-slate-200" />
                       <div className="w-3/4 h-8 rounded bg-green-50" />
                    </div>
                    <div className="h-32 rounded-lg bg-slate-50 border border-dashed border-slate-200 flex flex-col p-4 gap-2">
                       <div className="w-1/2 h-4 rounded bg-slate-200" />
                       <div className="w-3/4 h-8 rounded bg-blue-50" />
                    </div>
                 </div>
                 <div className="flex-1 rounded-lg bg-slate-50 border border-slate-100 p-4">
                    <div className="w-1/4 h-4 rounded bg-slate-200 mb-4" />
                    <div className="space-y-3">
                       <div className="w-full h-12 rounded bg-white border border-slate-100" />
                       <div className="w-full h-12 rounded bg-white border border-slate-100" />
                       <div className="w-full h-12 rounded bg-white border border-slate-100" />
                    </div>
                 </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-16">
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-[oklch(0.30_0.06_250)] mb-1">45k+</div>
              <div className="text-sm font-medium text-slate-500 uppercase tracking-widest">Monuments Répertoriés</div>
            </div>
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-[oklch(0.30_0.06_250)] mb-1">120+</div>
              <div className="text-sm font-medium text-slate-500 uppercase tracking-widest">Aides Identifiées</div>
            </div>
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-[oklch(0.30_0.06_250)] mb-1">2.4M€</div>
              <div className="text-sm font-medium text-slate-500 uppercase tracking-widest">Subventions Débloquées</div>
            </div>
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-[oklch(0.30_0.06_250)] mb-1">100%</div>
              <div className="text-sm font-medium text-slate-500 uppercase tracking-widest">Digitalisé</div>
            </div>
          </div>
        </div>
      </section>

      {/* Key Features */}
      <section id="solutions" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-base font-semibold text-[oklch(0.30_0.06_250)] uppercase tracking-widest mb-4">Fonctionnalités Clés</h2>
            <h3 className="text-3xl md:text-4xl font-bold text-slate-900">Une gestion simplifiée, de bout en bout</h3>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-8 rounded-2xl border border-slate-100 bg-white hover:border-slate-200 hover:shadow-xl hover:shadow-blue-900/5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-6 group-hover:bg-[oklch(0.30_0.06_250)] group-hover:text-white transition-colors">
                <Search className="w-6 h-6" />
              </div>
              <h4 className="text-xl font-bold mb-4">Moteur de Matching</h4>
              <p className="text-slate-600 leading-relaxed">
                Notre algorithme croise instantanément les caractéristiques de votre monument avec des centaines de dispositifs d'aide nationaux et régionaux.
              </p>
            </div>

            <div className="p-8 rounded-2xl border border-slate-100 bg-white hover:border-slate-200 hover:shadow-xl hover:shadow-blue-900/5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-6 group-hover:bg-[oklch(0.30_0.06_250)] group-hover:text-white transition-colors">
                <ClipboardCheck className="w-6 h-6" />
              </div>
              <h4 className="text-xl font-bold mb-4">Pipeline de Dossier</h4>
              <p className="text-slate-600 leading-relaxed">
                Suivez l'avancement de vos demandes de subvention en temps réel. De l'éligibilité jusqu'au versement final des fonds.
              </p>
            </div>

            <div className="p-8 rounded-2xl border border-slate-100 bg-white hover:border-slate-200 hover:shadow-xl hover:shadow-blue-900/5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-6 group-hover:bg-[oklch(0.30_0.06_250)] group-hover:text-white transition-colors">
                <FileText className="w-6 h-6" />
              </div>
              <h4 className="text-xl font-bold mb-4">Coffre-fort Numérique</h4>
              <p className="text-slate-600 leading-relaxed">
                Centralisez tous vos documents techniques, devis et arrêtés de protection MH. Prêts à être partagés avec les instructeurs.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Personas / Who is it for? */}
      <section id="experts" className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-base font-semibold text-[oklch(0.30_0.06_250)] uppercase tracking-widest mb-4">Pour qui ?</h2>
              <h3 className="text-4xl font-bold text-slate-900 mb-8 leading-tight">Une plateforme bi-face pour <br /> tous les acteurs du patrimoine</h3>
              
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="shrink-0 w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center">
                    <Building2 className="w-5 h-5 text-[oklch(0.30_0.06_250)]" />
                  </div>
                  <div>
                    <h5 className="font-bold text-lg mb-1">Propriétaires & Communes</h5>
                    <p className="text-slate-600">Identifiez vos droits, montez vos dossiers sans erreur et assurez le financement de vos travaux de restauration.</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="shrink-0 w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center">
                    <Users className="w-5 h-5 text-[oklch(0.30_0.06_250)]" />
                  </div>
                  <div>
                    <h5 className="font-bold text-lg mb-1">Architectes & Artisans BTP</h5>
                    <p className="text-slate-600">Accédez à un vivier de prospects qualifiés, accompagnez vos clients dans leur financement et gérez vos devis simplement.</p>
                  </div>
                </div>
              </div>
              
              <div className="mt-10">
                <Button variant="link" className="px-0 text-[oklch(0.30_0.06_250)] font-bold text-base hover:no-underline flex items-center gap-2">
                  En savoir plus sur nos outils experts <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <div className="relative">
              <div className="rounded-2xl bg-[oklch(0.30_0.06_250)] p-10 text-white shadow-2xl relative z-10">
                <blockquote className="text-xl italic mb-8 leading-relaxed">
                  "Grâce à Patrialta, notre petite commune a pu identifier une aide régionale dont nous ignorions l'existence pour le clocher de notre église. Le gain de temps a été colossal."
                </blockquote>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-white/20" />
                  <div>
                    <div className="font-bold text-lg">Maire de St-Julien-le-Petit</div>
                    <div className="text-white/70 text-sm">Utilisateur Patrialta</div>
                  </div>
                </div>
              </div>
              <div className="absolute top-10 right-[-20px] bottom-[-20px] left-10 bg-[oklch(0.30_0.06_250/0.1)] rounded-2xl -z-10 border border-[oklch(0.30_0.06_250/0.2)]" />
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section id="aides" className="py-24 bg-white overflow-hidden relative">
        <div className="max-w-5xl mx-auto px-4 text-center relative z-10">
          <div className="bg-[oklch(0.30_0.06_250)] rounded-3xl p-12 md:p-20 text-white shadow-2xl overflow-hidden relative">
             {/* Abstract background for CTA */}
             <div className="absolute top-0 right-0 w-[50%] h-full bg-white/5 skew-x-12 translate-x-1/2" />
             
             <h2 className="text-4xl md:text-5xl font-bold mb-8 relative z-10">Prêt à préserver <br />votre patrimoine ?</h2>
             <p className="text-xl text-white/80 mb-10 max-w-2xl mx-auto relative z-10">
               Créez votre compte aujourd'hui et lancez votre premier diagnostic d'éligibilité en moins de 5 minutes.
             </p>
             <div className="flex flex-col sm:flex-row items-center justify-center gap-4 relative z-10">
                <Link to="/login">
                  <Button size="lg" className="bg-white text-[oklch(0.30_0.06_250)] hover:bg-slate-50 px-10 text-lg h-14 font-bold">
                    Commencer l'aventure
                  </Button>
                </Link>
             </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-slate-100 bg-white">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-[oklch(0.30_0.06_250)] rounded flex items-center justify-center">
              <ShieldCheck className="text-white w-3.5 h-3.5" />
            </div>
            <span className="text-lg font-bold tracking-tight text-[oklch(0.30_0.06_250)]">Patrialta</span>
          </div>
          
          <div className="flex gap-8">
            <a href="#" className="text-sm text-slate-500 hover:text-slate-900">Mentions Légales</a>
            <a href="#" className="text-sm text-slate-500 hover:text-slate-900">Confidentialité</a>
            <a href="#" className="text-sm text-slate-500 hover:text-slate-900">Contact</a>
          </div>
          
          <div className="text-sm text-slate-400">
            © 2026 Patrialta. Fait avec passion pour le patrimoine français.
          </div>
        </div>
      </footer>
    </div>
  );
}
