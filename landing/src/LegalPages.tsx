import { useEffect, type ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import type { ParseKeys } from 'i18next';
import { Trans, useTranslation } from 'react-i18next';
import { C, Clover } from './LandingPage';
import { langueCourante, localeIntl } from './i18n';

/* Pages légales : CGU (avec mentions légales) et politique de confidentialité.
   Servies par le fallback SPA de nginx (cf. main.tsx). */

const BASE = import.meta.env.BASE_URL;
export const CGU_PATH = `${BASE}cgu`;
export const PRIVACY_PATH = `${BASE}confidentialite`;

// 8 octobre 2026, mis en forme selon la langue au rendu.
const DERNIERE_MAJ = new Date(2026, 9, 8);
const CONTACT_EMAIL = 'contact@monumia.fr';

type CleLegale = ParseKeys<'legal'>;

function Section({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mt-10 scroll-mt-24">
      <h2 className="font-serif text-[1.3rem] font-bold leading-snug" style={{ color: C.blue }}>
        {title}
      </h2>
      <div className="mt-3 space-y-3 text-[15px] leading-[1.75]" style={{ color: C.inkSoft }}>
        {children}
      </div>
    </section>
  );
}

// `children` facultatif : <Trans> fournit le contenu depuis la traduction.
function Strong({ children }: { children?: ReactNode }) {
  return (
    <strong className="font-semibold" style={{ color: C.ink }}>
      {children}
    </strong>
  );
}

function Ul({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-1.5 pl-5">{children}</ul>;
}

function LegalLink({ href, children }: { href: string; children?: ReactNode }) {
  const external = href.startsWith('http');
  return (
    <a
      href={href}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="underline underline-offset-2 transition-colors duration-200 hover:text-[#f17105]"
      style={{ color: C.blue }}
    >
      {children}
    </a>
  );
}

/* Balises utilisables dans les textes de legal.json. */
const BALISES = {
  gras: <Strong />,
  mail: <LegalLink href={`mailto:${CONTACT_EMAIL}`} />,
  confidentialite: <LegalLink href={PRIVACY_PATH} />,
  anonymisation: <LegalLink href={`${PRIVACY_PATH}#donnees-anonymisees`} />,
  cgu: <LegalLink href={CGU_PATH} />,
  mentions: <LegalLink href={`${CGU_PATH}#mentions-legales`} />,
  ovh: <LegalLink href="https://www.ovhcloud.com" />,
  cnil: <LegalLink href="https://www.cnil.fr" />,
};

/** Un paragraphe ou une puce de legal.json, gras et liens compris. */
function Texte({ k }: { k: CleLegale }) {
  const { t } = useTranslation('legal');
  return <Trans t={t} i18nKey={k} components={BALISES} values={{ email: CONTACT_EMAIL }} />;
}

function LegalLayout({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const { t } = useTranslation('legal');

  useEffect(() => {
    document.title = t('LegalLayout.titreOnglet', { titre: title });
  }, [t, title]);

  const derniereMaj = DERNIERE_MAJ.toLocaleDateString(localeIntl(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="font-sans relative flex min-h-screen flex-col" style={{ background: C.cream, color: C.ink }}>
      <header className="mx-auto flex h-16 w-full max-w-3xl items-center px-5 lg:px-8">
        <a href={BASE} className="flex items-center gap-2.5" aria-label={t('LegalLayout.accueilAria')}>
          <Clover className="h-7 w-7" style={{ color: C.orange }} />
          <span className="font-serif text-[1.35rem] font-bold tracking-[-0.01em]" style={{ color: C.blue }}>
            Monumia
          </span>
        </a>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-5 pb-20 pt-10 lg:px-8">
        <h1
          className="font-serif text-[clamp(1.8rem,4vw,2.5rem)] leading-[1.15] tracking-[-0.01em]"
          style={{ color: C.ink }}
        >
          {title}
        </h1>
        <p className="mt-3 text-[13.5px] uppercase tracking-[0.12em]" style={{ color: C.inkFaint }}>
          {t('LegalLayout.derniereMaj', { date: derniereMaj })}
        </p>

        {/* Seule la version française fait foi : la traduction le dit d'emblée. */}
        {langueCourante() === 'en' && (
          <p
            className="mt-6 rounded-md border px-4 py-3 text-[14px] leading-[1.6]"
            style={{ borderColor: C.border, color: C.inkSoft }}
          >
            {t('LegalLayout.avertissementTraduction')}
          </p>
        )}

        {children}

        <div className="mt-14 border-t pt-6" style={{ borderColor: C.border }}>
          <a
            href={BASE}
            className="group inline-flex items-center gap-2 text-[14px] font-medium transition-colors duration-200 hover:text-[#0a369d]"
            style={{ color: C.inkSoft }}
          >
            <ArrowLeft className="h-4 w-4 transition-transform duration-300 group-hover:-translate-x-1" />
            {t('LegalLayout.retourAccueil')}
          </a>
        </div>
      </main>
    </div>
  );
}

/* ────────────────────────────────────────────
   Conditions générales d'utilisation
   ──────────────────────────────────────────── */

export function CguPage() {
  const { t } = useTranslation('legal');
  return (
    <LegalLayout title={t('Cgu.titre')}>
      <div className="mt-6 space-y-3 text-[15px] leading-[1.75]" style={{ color: C.inkSoft }}>
        <p>
          <Texte k="Cgu.intro" />
        </p>
      </div>

      <Section id="mentions-legales" title={t('Cgu.mentions.titre')}>
        <p>
          <Texte k="Cgu.mentions.editeur" />
        </p>
        <p>
          <Texte k="Cgu.mentions.directeur" />
        </p>
        <p>
          <Texte k="Cgu.mentions.contact" />
        </p>
        <p>
          <Texte k="Cgu.mentions.hebergeur" />
        </p>
        <p>
          <Texte k="Cgu.mentions.donnees" />
        </p>
      </Section>

      <Section title={t('Cgu.objet.titre')}>
        <p>{t('Cgu.objet.p1')}</p>
      </Section>

      <Section title={t('Cgu.resultats.titre')}>
        <p>
          <Texte k="Cgu.resultats.p1" />
        </p>
        <p>{t('Cgu.resultats.p2')}</p>
        <Ul>
          <li>
            <Texte k="Cgu.resultats.puce1" />
          </li>
          <li>
            <Texte k="Cgu.resultats.puce2" />
          </li>
          <li>
            <Texte k="Cgu.resultats.puce3" />
          </li>
          <li>
            <Texte k="Cgu.resultats.puce4" />
          </li>
        </Ul>
      </Section>

      <Section title={t('Cgu.acces.titre')}>
        <p>
          <Texte k="Cgu.acces.p1" />
        </p>
        <p>
          <Texte k="Cgu.acces.p2" />
        </p>
        <p>{t('Cgu.acces.p3')}</p>
      </Section>

      <Section title={t('Cgu.usage.titre')}>
        <p>{t('Cgu.usage.intro')}</p>
        <Ul>
          <li>{t('Cgu.usage.puce1')}</li>
          <li>{t('Cgu.usage.puce2')}</li>
          <li>{t('Cgu.usage.puce3')}</li>
          <li>{t('Cgu.usage.puce4')}</li>
        </Ul>
        <p>{t('Cgu.usage.p2')}</p>
      </Section>

      <Section title={t('Cgu.paiement.titre')}>
        <p>
          <Texte k="Cgu.paiement.p1" />
        </p>
        <p>{t('Cgu.paiement.p2')}</p>
        <p>{t('Cgu.paiement.p3')}</p>
      </Section>

      <Section title={t('Cgu.retractation.titre')}>
        <p>
          <Texte k="Cgu.retractation.p1" />
        </p>
        <p>{t('Cgu.retractation.p2')}</p>
      </Section>

      <Section title={t('Cgu.propriete.titre')}>
        <p>{t('Cgu.propriete.p1')}</p>
        <p>
          <Texte k="Cgu.propriete.p2" />
        </p>
        <p>{t('Cgu.propriete.p3')}</p>
      </Section>

      <Section id="donnees-anonymisees" title={t('Cgu.anonymisation.titre')}>
        <p>
          <Texte k="Cgu.anonymisation.p1" />
        </p>
        <p>
          <Texte k="Cgu.anonymisation.p2" />
        </p>
        <Ul>
          <li>{t('Cgu.anonymisation.puce1')}</li>
          <li>{t('Cgu.anonymisation.puce2')}</li>
          <li>{t('Cgu.anonymisation.puce3')}</li>
        </Ul>
        <p>
          <Texte k="Cgu.anonymisation.p3" />
        </p>
        <p>
          <Texte k="Cgu.anonymisation.p4" />
        </p>
        <p>
          <Texte k="Cgu.anonymisation.p5" />
        </p>
      </Section>

      <Section title={t('Cgu.donneesPersonnelles.titre')}>
        <p>
          <Texte k="Cgu.donneesPersonnelles.p1" />
        </p>
      </Section>

      <Section title={t('Cgu.responsabilite.titre')}>
        <p>{t('Cgu.responsabilite.p1')}</p>
        <p>{t('Cgu.responsabilite.p2')}</p>
      </Section>

      <Section title={t('Cgu.resiliation.titre')}>
        <p>
          <Texte k="Cgu.resiliation.p1" />
        </p>
      </Section>

      <Section title={t('Cgu.mediation.titre')}>
        <p>
          <Texte k="Cgu.mediation.p1" />
        </p>
        {/* À rétablir dès qu'un médiateur de la consommation est désigné (CM2C,
            Médicys…) : « Médiateur désigné : <nom et coordonnées> ». */}
      </Section>

      <Section title={t('Cgu.modification.titre')}>
        <p>{t('Cgu.modification.p1')}</p>
      </Section>

      <Section title={t('Cgu.droitApplicable.titre')}>
        <p>{t('Cgu.droitApplicable.p1')}</p>
      </Section>

      <p className="mt-10 text-[14px] leading-[1.7]" style={{ color: C.inkFaint }}>
        <Texte k="Cgu.voirAussi" />
      </p>
    </LegalLayout>
  );
}

/* ────────────────────────────────────────────
   Politique de confidentialité
   ──────────────────────────────────────────── */

export function PrivacyPage() {
  const { t } = useTranslation('legal');
  return (
    <LegalLayout title={t('Confidentialite.titre')}>
      <div className="mt-6 space-y-3 text-[15px] leading-[1.75]" style={{ color: C.inkSoft }}>
        <p>
          <Texte k="Confidentialite.intro1" />
        </p>
        <p>
          <Texte k="Confidentialite.intro2" />
        </p>
      </div>

      <Section title={t('Confidentialite.responsable.titre')}>
        <p>
          <Texte k="Confidentialite.responsable.p1" />
        </p>
      </Section>

      <Section title={t('Confidentialite.collecte.titre')}>
        <p>{t('Confidentialite.collecte.intro')}</p>
        <Ul>
          <li>
            <Texte k="Confidentialite.collecte.attente" />
          </li>
          <li>
            <Texte k="Confidentialite.collecte.compte" />
          </li>
          <li>
            <Texte k="Confidentialite.collecte.projets" />
          </li>
          <li>
            <Texte k="Confidentialite.collecte.facturation" />
          </li>
          <li>
            <Texte k="Confidentialite.collecte.techniques" />
          </li>
          <li>
            <Texte k="Confidentialite.collecte.audience" />
          </li>
        </Ul>
        <p>{t('Confidentialite.collecte.nonIntro')}</p>
        <Ul>
          <li>{t('Confidentialite.collecte.non1')}</li>
          <li>{t('Confidentialite.collecte.non2')}</li>
          <li>{t('Confidentialite.collecte.non3')}</li>
          <li>{t('Confidentialite.collecte.non4')}</li>
        </Ul>
      </Section>

      <Section title={t('Confidentialite.finalites.titre')}>
        <Ul>
          <li>
            <Texte k="Confidentialite.finalites.service" />
          </li>
          <li>
            <Texte k="Confidentialite.finalites.lancement" />
          </li>
          <li>
            <Texte k="Confidentialite.finalites.facturation" />
          </li>
          <li>
            <Texte k="Confidentialite.finalites.securite" />
          </li>
          <li>
            <Texte k="Confidentialite.finalites.audience" />
          </li>
          <li>
            <Texte k="Confidentialite.finalites.emails" />
          </li>
          <li>
            <Texte k="Confidentialite.finalites.anonymisation" />
          </li>
        </Ul>
      </Section>

      <Section id="donnees-anonymisees" title={t('Confidentialite.anonymisation.titre')}>
        <p>
          <Texte k="Confidentialite.anonymisation.p1" />
        </p>
        <p>
          <Texte k="Confidentialite.anonymisation.utilise" />
        </p>
        <Ul>
          <li>{t('Confidentialite.anonymisation.puce1')}</li>
          <li>{t('Confidentialite.anonymisation.puce2')}</li>
          <li>{t('Confidentialite.anonymisation.puce3')}</li>
        </Ul>
        <p>
          <Texte k="Confidentialite.anonymisation.jamaisUtilise" />
        </p>
        <p>
          <Texte k="Confidentialite.anonymisation.methode" />
        </p>
        <p>
          <Texte k="Confidentialite.anonymisation.opposition" />
        </p>
      </Section>

      <Section title={t('Confidentialite.destinataires.titre')}>
        <p>{t('Confidentialite.destinataires.intro')}</p>
        <Ul>
          <li>
            <Texte k="Confidentialite.destinataires.ovh" />
          </li>
          <li>
            <Texte k="Confidentialite.destinataires.supabase" />
          </li>
          <li>
            <Texte k="Confidentialite.destinataires.stripe" />
          </li>
          <li>
            <Texte k="Confidentialite.destinataires.resend" />
          </li>
          <li>
            <Texte k="Confidentialite.destinataires.posthog" />
          </li>
        </Ul>
        <p>{t('Confidentialite.destinataires.p2')}</p>
      </Section>

      <Section title={t('Confidentialite.transferts.titre')}>
        <p>
          <Texte k="Confidentialite.transferts.p1" />
        </p>
      </Section>

      <Section title={t('Confidentialite.conservation.titre')}>
        <Ul>
          <li>
            <Texte k="Confidentialite.conservation.compte" />
          </li>
          <li>
            <Texte k="Confidentialite.conservation.documents" />
          </li>
          <li>
            <Texte k="Confidentialite.conservation.anonymises" />
          </li>
          <li>
            <Texte k="Confidentialite.conservation.attente" />
          </li>
          <li>
            <Texte k="Confidentialite.conservation.factures" />
          </li>
          <li>
            <Texte k="Confidentialite.conservation.journaux" />
          </li>
          <li>
            <Texte k="Confidentialite.conservation.audience" />
          </li>
        </Ul>
      </Section>

      <Section title={t('Confidentialite.droits.titre')}>
        <p>{t('Confidentialite.droits.intro')}</p>
        <Ul>
          <li>{t('Confidentialite.droits.acces')}</li>
          <li>{t('Confidentialite.droits.rectification')}</li>
          <li>{t('Confidentialite.droits.effacement')}</li>
          <li>{t('Confidentialite.droits.limitation')}</li>
          <li>{t('Confidentialite.droits.opposition')}</li>
          <li>{t('Confidentialite.droits.portabilite')}</li>
          <li>{t('Confidentialite.droits.consentement')}</li>
          <li>{t('Confidentialite.droits.directives')}</li>
        </Ul>
        <p>
          <Texte k="Confidentialite.droits.exercice" />
        </p>
        <p>
          <Texte k="Confidentialite.droits.cnil" />
        </p>
      </Section>

      <Section title={t('Confidentialite.cookies.titre')}>
        <p>
          <Texte k="Confidentialite.cookies.site" />
        </p>
        <p>{t('Confidentialite.cookies.application')}</p>
        <p>{t('Confidentialite.cookies.audience')}</p>
        <p>{t('Confidentialite.cookies.futur')}</p>
        <p>{t('Confidentialite.cookies.stripe')}</p>
      </Section>

      <Section title={t('Confidentialite.mineurs.titre')}>
        <p>
          <Texte k="Confidentialite.mineurs.p1" />
        </p>
      </Section>

      <Section title={t('Confidentialite.securite.titre')}>
        <p>{t('Confidentialite.securite.p1')}</p>
      </Section>

      <Section title={t('Confidentialite.decision.titre')}>
        <p>
          <Texte k="Confidentialite.decision.p1" />
        </p>
      </Section>

      <Section title={t('Confidentialite.modifications.titre')}>
        <p>{t('Confidentialite.modifications.p1')}</p>
      </Section>

      <p className="mt-10 text-[14px] leading-[1.7]" style={{ color: C.inkFaint }}>
        <Texte k="Confidentialite.voirAussi" />
      </p>
    </LegalLayout>
  );
}
