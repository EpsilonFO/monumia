import { Link } from 'react-router';

import { Clover } from '@/components/illustrations';
import { C } from '@/lib/brand';
import { useAuthStore } from '@/stores/useAuthStore';

/**
 * Encadré « Découvrir Monumia » des rails du blog. Le blog sert le SEO :
 * ce CTA ne s’adresse qu’aux visiteurs anonymes et disparaît une fois connecté.
 */
export function MonumiaCta() {
  const isLoggedIn = useAuthStore((s) => !!s.user && !!s.token);
  if (isLoggedIn) return null;

  return (
    <section
      className="relative overflow-hidden rounded-2xl border p-5"
      style={{ background: C.paleBlue, borderColor: C.border }}
    >
      <Clover
        size={88}
        className="absolute -right-6 -top-6"
        style={{ color: C.blue, opacity: 0.07 }}
      />
      <p
        className="text-[15px] font-semibold leading-snug"
        style={{ fontFamily: 'var(--font-serif)', color: C.blue }}
      >
        Un projet sur un bien protégé&nbsp;?
      </p>
      <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: C.grayFg }}>
        Monumia identifie votre statut et les aides mobilisables, et vous guide dans vos
        démarches.
      </p>
      <Link
        to="/login"
        className="group mt-4 inline-flex items-center gap-1.5 rounded-full px-4 py-2.5 text-[13px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5"
        style={{ background: C.orange, boxShadow: '0 10px 30px -8px rgba(241,113,5,0.55)' }}
      >
        Découvrir Monumia
        <span className="transition-transform duration-300 group-hover:translate-x-0.5">→</span>
      </Link>
    </section>
  );
}
