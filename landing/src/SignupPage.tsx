import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, Loader2, Mail } from 'lucide-react';
import { C, Clover } from './LandingPage';

/* L'API du backend : app.monumia.fr/api en prod, beta.monumia.fr/api en beta.
   Passée au build via VITE_API_URL (cf. Dockerfile + docker-compose). */
const API_URL = (import.meta.env.VITE_API_URL || 'https://app.monumia.fr/api').replace(/\/+$/, '');
const HOME_URL = import.meta.env.BASE_URL;

type Status = 'idle' | 'loading' | 'done' | 'error';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function SignupPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.title = 'Me tenir informé du lancement — Monumia';
    inputRef.current?.focus();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (status === 'loading') return;
    const value = email.trim();
    if (!EMAIL_RE.test(value)) {
      setStatus('error');
      setMessage('Cette adresse e-mail ne semble pas valide.');
      return;
    }
    setStatus('loading');
    setMessage('');
    try {
      const res = await fetch(`${API_URL}/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: value }),
      });
      if (!res.ok) throw new Error(`status ${res.status}`);
      setStatus('done');
    } catch {
      setStatus('error');
      setMessage('Une erreur est survenue. Merci de réessayer dans un instant.');
    }
  };

  return (
    <div className="font-sans relative flex min-h-screen flex-col" style={{ background: C.cream, color: C.ink }}>
      {/* Lueur d'ambiance, comme sur le héros */}
      <div
        className="pointer-events-none absolute -top-32 right-[-12%] h-[460px] w-[460px] rounded-full blur-[130px]"
        style={{ background: 'rgba(241, 113, 5, 0.1)' }}
      />

      {/* En-tête : le logo ramène à l'accueil */}
      <header className="relative mx-auto flex h-16 w-full max-w-3xl items-center px-5 lg:px-8">
        <a href={HOME_URL} className="flex items-center gap-2.5" aria-label="Monumia, retour à l'accueil">
          <Clover className="h-7 w-7" style={{ color: C.orange }} />
          <span className="font-serif text-[1.35rem] font-bold tracking-[-0.01em]" style={{ color: C.blue }}>
            Monumia
          </span>
        </a>
      </header>

      <main className="relative flex flex-1 items-center justify-center px-5 py-16 lg:px-8">
        <div
          className="w-full max-w-lg rounded-3xl border p-8 shadow-[0_30px_70px_-35px_rgba(10,54,157,0.45)] sm:p-12"
          style={{ background: C.card, borderColor: C.border }}
        >
          {status === 'done' ? (
            <div className="text-center">
              <span
                className="mx-auto grid h-14 w-14 place-items-center rounded-full"
                style={{ background: C.paleOrange }}
              >
                <CheckCircle2 className="h-7 w-7" style={{ color: C.orange }} strokeWidth={2} />
              </span>
              <h1 className="mt-6 font-serif text-[clamp(1.6rem,3.4vw,2.1rem)] leading-[1.2]" style={{ color: C.ink }}>
                C'est noté, merci !
              </h1>
              <p className="mx-auto mt-4 max-w-sm text-[16px] leading-[1.7]" style={{ color: C.inkSoft }}>
                Nous vous écrirons à <strong style={{ color: C.ink }}>{email.trim()}</strong> dès l'ouverture
                de Monumia. Pas de spam, juste le signal de départ.
              </p>
              <a
                href={HOME_URL}
                className="group mt-8 inline-flex items-center gap-2 text-[15px] font-semibold transition-colors duration-200 hover:text-[#0a369d]"
                style={{ color: C.blue }}
              >
                <ArrowLeft className="h-4 w-4 transition-transform duration-300 group-hover:-translate-x-1" />
                Retour à l'accueil
              </a>
            </div>
          ) : (
            <>
              <span className="text-[12.5px] font-semibold uppercase tracking-[0.18em]" style={{ color: C.orange }}>
                Lancement en Septembre 2026
              </span>
              <h1
                className="mt-4 font-serif text-[clamp(1.7rem,3.6vw,2.3rem)] leading-[1.18] tracking-[-0.01em]"
                style={{ color: C.ink }}
              >
                Soyez prévenu dès l'ouverture
              </h1>
              <p className="mt-4 text-[16px] leading-[1.7]" style={{ color: C.inkSoft }}>
                Laissez-nous votre e-mail : nous vous écrirons dès que Monumia ouvre ses portes. Pas
                de spam, juste le signal de départ.
              </p>

              <form onSubmit={submit} className="mt-8" noValidate>
                <label htmlFor="email" className="sr-only">
                  Votre adresse e-mail
                </label>
                <div
                  className={`flex items-center gap-2.5 rounded-full border bg-white px-4 py-1.5 transition-all duration-200 ${
                    status === 'error'
                      ? 'border-[#f17105] shadow-[0_0_0_4px_rgba(241,113,5,0.12)]'
                      : 'border-[#ece3d2] focus-within:border-[#f17105] focus-within:shadow-[0_0_0_4px_rgba(241,113,5,0.16),0_12px_30px_-12px_rgba(241,113,5,0.5)]'
                  }`}
                >
                  <Mail
                    className="h-[18px] w-[18px] shrink-0 transition-colors duration-200"
                    style={{ color: status === 'error' ? C.orange : C.inkFaint }}
                    strokeWidth={1.8}
                  />
                  <input
                    ref={inputRef}
                    id="email"
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    placeholder="vous@exemple.fr"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (status === 'error') setStatus('idle');
                    }}
                    className="min-w-0 flex-1 bg-transparent py-2 text-[15px] placeholder:text-[#222b35]/40"
                    style={{ color: C.ink, outline: 'none' }}
                  />
                </div>

                {status === 'error' && (
                  <p className="mt-2.5 px-1 text-[13.5px] font-medium" style={{ color: C.orange }} role="alert">
                    {message}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={status === 'loading'}
                  className="group mt-5 inline-flex w-full items-center justify-center gap-2.5 rounded-full px-7 py-3.5 text-[15px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_10px_30px_-8px_rgba(241,113,5,0.55)] disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:translate-y-0 disabled:hover:shadow-none"
                  style={{ background: C.orange }}
                >
                  {status === 'loading' ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Enregistrement…
                    </>
                  ) : (
                    <>
                      Me tenir informé du lancement
                      <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
                    </>
                  )}
                </button>
              </form>

              <p className="mt-4 text-[12.5px] leading-[1.6]" style={{ color: C.inkFaint }}>
                Votre adresse ne sert qu'à vous prévenir du lancement : jamais cédée, supprimée sur
                simple demande. Voir notre{' '}
                <a
                  href={`${HOME_URL}confidentialite`}
                  className="underline underline-offset-2 transition-colors duration-200 hover:text-[#0a369d]"
                >
                  politique de confidentialité
                </a>
                .
              </p>

              <a
                href={HOME_URL}
                className="group mt-7 inline-flex items-center gap-2 text-[14px] font-medium transition-colors duration-200 hover:text-[#0a369d]"
                style={{ color: C.inkSoft }}
              >
                <ArrowLeft className="h-4 w-4 transition-transform duration-300 group-hover:-translate-x-1" />
                Retour à l'accueil
              </a>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
