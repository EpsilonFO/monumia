import { useEffect, type ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { C, Clover } from './LandingPage';

/* Pages légales : CGU (avec mentions légales) et politique de confidentialité.
   Servies par le fallback SPA de nginx (cf. main.tsx). */

const BASE = import.meta.env.BASE_URL;
export const CGU_PATH = `${BASE}cgu`;
export const PRIVACY_PATH = `${BASE}confidentialite`;

const DERNIERE_MAJ = '8 octobre 2026';
const CONTACT_EMAIL = 'contact@monumia.fr';

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

function Strong({ children }: { children: ReactNode }) {
  return (
    <strong className="font-semibold" style={{ color: C.ink }}>
      {children}
    </strong>
  );
}

function Ul({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-1.5 pl-5">{children}</ul>;
}

function LegalLink({ href, children }: { href: string; children: ReactNode }) {
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

function LegalLayout({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  useEffect(() => {
    document.title = `${title} — Monumia`;
  }, [title]);

  return (
    <div className="font-sans relative flex min-h-screen flex-col" style={{ background: C.cream, color: C.ink }}>
      <header className="mx-auto flex h-16 w-full max-w-3xl items-center px-5 lg:px-8">
        <a href={BASE} className="flex items-center gap-2.5" aria-label="Monumia, retour à l'accueil">
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
          Dernière mise à jour : {DERNIERE_MAJ}
        </p>

        {children}

        <div className="mt-14 border-t pt-6" style={{ borderColor: C.border }}>
          <a
            href={BASE}
            className="group inline-flex items-center gap-2 text-[14px] font-medium transition-colors duration-200 hover:text-[#0a369d]"
            style={{ color: C.inkSoft }}
          >
            <ArrowLeft className="h-4 w-4 transition-transform duration-300 group-hover:-translate-x-1" />
            Retour à l'accueil
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
  return (
    <LegalLayout title="Conditions générales d'utilisation">
      <div className="mt-6 space-y-3 text-[15px] leading-[1.75]" style={{ color: C.inkSoft }}>
        <p>
          Les présentes conditions générales d'utilisation (les « <Strong>CGU</Strong> ») régissent
          l'accès et l'utilisation du site <Strong>monumia.fr</Strong> et de l'application{' '}
          <Strong>app.monumia.fr</Strong> (ensemble, le « <Strong>Service</Strong> »), édités par
          Monumia. En créant un compte ou en utilisant le Service, vous acceptez sans réserve les
          présentes CGU. Si vous ne les acceptez pas, vous ne devez pas utiliser le Service.
        </p>
      </div>

      <Section id="mentions-legales" title="1. Mentions légales">
        <p>
          <Strong>Éditeur du Service</Strong> : Monumia, société par actions simplifiée (SAS) au
          capital de 400,00 €, immatriculée au RCS de Lyon sous le numéro 106 236 748, dont le
          siège social est situé 10 avenue Jean Jaurès, 69370 Saint-Didier-au-Mont-d'Or, France.
          Numéro de TVA intracommunautaire : FR72106236748.
        </p>
        <p>
          <Strong>Directeur de la publication</Strong> : Paul Vacheret, président.
        </p>
        <p>
          <Strong>Contact</Strong> :{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>.
        </p>
        <p>
          <Strong>Hébergeur</Strong> : OVH SAS, 2 rue Kellermann, 59100 Roubaix, France,
          immatriculée au RCS de Lille Métropole sous le numéro 424 761 419, téléphone :
          +33 9 72 10 10 07 (<LegalLink href="https://www.ovhcloud.com">www.ovhcloud.com</LegalLink>).
          Les serveurs du Service sont hébergés en France.
        </p>
        <p>
          <Strong>Base de données et stockage de fichiers</Strong> : Supabase, Inc., avec un
          hébergement des données situé exclusivement au sein de l'Union européenne (voir la{' '}
          <LegalLink href={PRIVACY_PATH}>politique de confidentialité</LegalLink>).
        </p>
      </Section>

      <Section title="2. Objet du Service">
        <p>
          Monumia est un service en ligne qui aide les propriétaires et gestionnaires de patrimoine
          bâti à identifier les aides au financement (subventions publiques, aides de fondations,
          dispositifs fiscaux, mécénat) susceptibles de s'appliquer à leur monument et à leur
          projet, puis à préparer leurs dossiers de demande.
        </p>
      </Section>

      <Section title="3. Caractère informatif des résultats">
        <p>
          <Strong>
            Les résultats fournis par Monumia (diagnostics d'éligibilité, estimations, listes
            d'aides, contenus d'accompagnement) ont une valeur strictement informative et
            indicative.
          </Strong>{' '}
          Ils sont établis à partir des informations que vous déclarez et de sources publiques
          (textes officiels, règlements d'intervention, sites des organismes financeurs) qui
          peuvent évoluer, être modifiées ou supprimées à tout moment par les organismes concernés.
        </p>
        <p>En conséquence :</p>
        <Ul>
          <li>
            Monumia <Strong>ne garantit ni l'éligibilité effective</Strong> à une aide, ni son
            obtention, ni son montant : la décision d'attribution appartient exclusivement à
            l'organisme financeur (État, collectivité, fondation, etc.), au terme de sa propre
            instruction ;
          </li>
          <li>
            le Service <Strong>ne constitue pas un conseil juridique, fiscal, financier ou
            architectural</Strong> et ne se substitue ni à l'analyse d'un professionnel qualifié
            (avocat, notaire, expert-comptable, architecte du patrimoine), ni aux échanges directs
            avec les organismes financeurs ;
          </li>
          <li>
            il vous appartient de <Strong>vérifier les conditions officielles</Strong> de chaque
            aide auprès de l'organisme concerné avant toute décision engageante (travaux,
            embauche, financement) ;
          </li>
          <li>
            Monumia est tenue à une <Strong>obligation de moyens</Strong> : elle met tout en œuvre
            pour maintenir des informations exactes et à jour, sans pouvoir le garantir de manière
            absolue.
          </li>
        </Ul>
      </Section>

      <Section title="4. Accès au Service et compte utilisateur">
        <p>
          Le Service est réservé aux <Strong>personnes physiques majeures</Strong> disposant de la
          pleine capacité juridique et aux personnes morales agissant par l'intermédiaire d'un
          représentant habilité. <Strong>Le Service n'est pas destiné aux mineurs</Strong>, qui ne
          doivent ni créer de compte ni transmettre de données personnelles via le Service.
        </p>
        <p>
          La création d'un compte requiert des informations exactes, complètes et à jour. Vous êtes
          responsable de la confidentialité de vos identifiants et de toute activité réalisée
          depuis votre compte. En cas d'utilisation non autorisée, prévenez-nous sans délai à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>.
        </p>
        <p>
          L'exactitude des résultats dépend directement de l'exactitude des informations que vous
          déclarez sur votre monument et votre projet : des déclarations erronées produisent des
          résultats erronés, sans que la responsabilité de Monumia puisse être engagée de ce fait.
        </p>
      </Section>

      <Section title="5. Utilisation acceptable">
        <p>Vous vous engagez à ne pas :</p>
        <Ul>
          <li>utiliser le Service à des fins illicites ou contraires aux présentes CGU ;</li>
          <li>
            tenter d'accéder sans autorisation aux systèmes, comptes ou données d'autres
            utilisateurs, ou de perturber le fonctionnement du Service ;
          </li>
          <li>
            extraire de manière systématique ou automatisée le contenu du Service (scraping,
            aspiration de base de données) à des fins de réutilisation commerciale ;
          </li>
          <li>
            téléverser des contenus illicites, contrefaisants ou portant atteinte aux droits de
            tiers.
          </li>
        </Ul>
        <p>
          Monumia se réserve le droit de suspendre ou de résilier, après notification sauf urgence,
          tout compte contrevenant aux présentes CGU.
        </p>
      </Section>

      <Section title="6. Offres payantes et paiement">
        <p>
          Certaines fonctionnalités du Service sont payantes. Les prix, exprimés en euros et toutes
          taxes comprises pour les consommateurs, sont indiqués avant toute souscription. Le
          paiement est traité par notre prestataire <Strong>Stripe</Strong>, sur des pages de
          paiement sécurisées opérées par Stripe : Monumia n'accède jamais à vos données de carte
          bancaire.
        </p>
        <p>
          Les abonnements sont sans engagement de durée sauf mention contraire : ils peuvent être
          résiliés à tout moment depuis votre espace client, la résiliation prenant effet à la fin
          de la période en cours, sans remboursement au prorata de la période entamée sauf
          disposition légale contraire.
        </p>
        <p>
          Monumia peut faire évoluer ses tarifs ; toute modification est notifiée au moins un mois
          avant son entrée en vigueur et ne s'applique qu'aux périodes de facturation suivantes.
          Vous restez libre de résilier avant l'application du nouveau tarif.
        </p>
      </Section>

      <Section title="7. Droit de rétractation (consommateurs)">
        <p>
          Si vous êtes un consommateur au sens du code de la consommation, vous disposez d'un délai
          de <Strong>quatorze (14) jours</Strong> à compter de la souscription pour exercer votre
          droit de rétractation, sans motif ni pénalité, en écrivant à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink> (articles
          L221-18 et suivants du code de la consommation).
        </p>
        <p>
          Si vous demandez expressément l'accès immédiat au Service avant l'expiration de ce délai,
          vous pouvez toujours vous rétracter dans les quatorze jours, mais un montant proportionnel
          au service déjà fourni jusqu'à votre demande de rétractation reste dû (article L221-25 du
          code de la consommation).
        </p>
      </Section>

      <Section title="8. Propriété intellectuelle">
        <p>
          Le Service, sa structure, ses textes, sa charte graphique, son logo et ses logiciels sont
          protégés par le droit de la propriété intellectuelle et demeurent la propriété exclusive
          de Monumia ou de ses concédants. Toute reproduction ou réutilisation non autorisée est
          interdite.
        </p>
        <p>
          Les documents et informations que vous téléversez <Strong>restent votre propriété</Strong>.
          Vous concédez à Monumia une licence limitée, non exclusive et révocable, aux fins de
          fournir le Service (stockage, affichage, préparation de vos dossiers) et, dans les
          conditions de l'article 9, de constituer des jeux de données anonymisés. Cette licence
          prend fin à la suppression des contenus ou de votre compte ; elle subsiste toutefois pour
          les données déjà anonymisées, qui ne permettent plus de vous identifier ni de retrouver
          vos contenus.
        </p>
        <p>
          Les textes officiels et informations publiques relatifs aux aides restent soumis à leurs
          régimes propres et sont cités à titre de référence.
        </p>
      </Section>

      <Section id="donnees-anonymisees" title="9. Données anonymisées et modèles d'intelligence artificielle">
        <p>
          Pour fiabiliser ses diagnostics et développer de nouvelles fonctionnalités, Monumia peut
          constituer, à partir des informations renseignées sur le Service, des{' '}
          <Strong>jeux de données anonymisés</Strong> destinés à l'analyse statistique et à
          l'<Strong>entraînement de modèles d'intelligence artificielle</Strong>, par Monumia ou
          pour son compte.
        </p>
        <p>
          Seules sont concernées les données relatives aux <Strong>monuments et aux projets</Strong>,
          jamais celles qui décrivent votre personne :
        </p>
        <Ul>
          <li>
            les informations déclarées sur le monument (nature du bien, protection, état sanitaire,
            caractéristiques, localisation généralisée) et sur le projet (nature et ampleur des
            travaux, calendrier, budget) ;
          </li>
          <li>vos réponses au questionnaire d'éligibilité et les résultats du diagnostic ;</li>
          <li>
            les pièces de dossier qui, par nature ou par votre choix, ont vocation à être rendues
            publiques (par exemple un dossier de demande d'aide destiné à publication).
          </li>
        </Ul>
        <p>
          Sont <Strong>exclus</Strong> de cette utilisation : votre identité, vos coordonnées, vos
          identifiants de connexion, vos données de facturation, les journaux techniques et les
          documents confidentiels (pièces d'identité, coordonnées bancaires, documents fiscaux,
          correspondance privée, tout document que vous n'avez pas destiné à une diffusion
          publique).
        </p>
        <p>
          Avant toute utilisation, les données sont <Strong>anonymisées de manière irréversible</Strong> :
          suppression ou généralisation de tout élément permettant, directement ou par recoupement,
          de vous identifier ou d'identifier un propriétaire privé. Monumia s'engage à ne pas
          chercher à réidentifier les personnes concernées et à interdire cette réidentification à
          ses éventuels prestataires. Les jeux de données ainsi constitués ne comportent plus de
          données personnelles et peuvent être conservés après la clôture de votre compte.
        </p>
        <p>
          Vous pouvez <Strong>vous opposer</Strong> à tout moment à cette utilisation pour vos
          données non encore anonymisées en écrivant à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>. Les modalités
          détaillées figurent dans la{' '}
          <LegalLink href={`${PRIVACY_PATH}#donnees-anonymisees`}>politique de confidentialité</LegalLink>.
        </p>
      </Section>

      <Section title="10. Données personnelles">
        <p>
          Le traitement de vos données personnelles est décrit dans notre{' '}
          <LegalLink href={PRIVACY_PATH}>politique de confidentialité</LegalLink>, conforme au
          règlement (UE) 2016/679 (« RGPD ») et à la loi Informatique et Libertés.
        </p>
      </Section>

      <Section title="11. Disponibilité et responsabilité">
        <p>
          Monumia s'efforce d'assurer un accès continu au Service, sans garantir une disponibilité
          ininterrompue : des interruptions pour maintenance, mise à jour ou cas de force majeure
          peuvent survenir. Monumia ne saurait être tenue responsable des dommages indirects
          (perte de chance d'obtenir une aide, perte d'exploitation, préjudice d'image) résultant
          de l'utilisation ou de l'impossibilité d'utiliser le Service.
        </p>
        <p>
          Pour les utilisateurs professionnels, la responsabilité totale de Monumia, toutes causes
          confondues, est plafonnée aux sommes effectivement versées par l'utilisateur au titre des
          douze derniers mois. Aucune stipulation des présentes ne limite la responsabilité de
          Monumia en cas de dol, de faute lourde, de dommage corporel, ni aucune responsabilité qui
          ne peut être légalement limitée à l'égard des consommateurs.
        </p>
      </Section>

      <Section title="12. Résiliation">
        <p>
          Vous pouvez cesser d'utiliser le Service et demander la suppression de votre compte à
          tout moment, depuis l'application ou en écrivant à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>. Les conséquences
          de la suppression sur vos données sont décrites dans la{' '}
          <LegalLink href={PRIVACY_PATH}>politique de confidentialité</LegalLink>.
        </p>
      </Section>

      <Section title="13. Médiation de la consommation">
        <p>
          Conformément aux articles L612-1 et suivants du code de la consommation, tout consommateur
          a le droit de recourir gratuitement à un médiateur de la consommation en vue de la
          résolution amiable d'un litige avec Monumia, après avoir tenté au préalable de résoudre
          le litige directement auprès de{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>.
        </p>
        {/* À rétablir dès qu'un médiateur de la consommation est désigné (CM2C,
            Médicys…) : « Médiateur désigné : <nom et coordonnées> ». */}
      </Section>

      <Section title="14. Modification des CGU">
        <p>
          Monumia peut modifier les présentes CGU pour tenir compte des évolutions du Service ou de
          la réglementation. Les utilisateurs disposant d'un compte sont informés de toute
          modification substantielle au moins quinze jours avant son entrée en vigueur. La poursuite
          de l'utilisation du Service après cette date vaut acceptation des CGU modifiées ; à
          défaut, vous pouvez résilier dans les conditions de l'article 12.
        </p>
      </Section>

      <Section title="15. Droit applicable et juridiction">
        <p>
          Les présentes CGU sont soumises au droit français. En cas de litige et à défaut de
          résolution amiable, les tribunaux français sont compétents dans les conditions du droit
          commun. Le consommateur peut saisir, à son choix, l'une des juridictions territorialement
          compétentes en vertu du code de procédure civile ou la juridiction du lieu où il demeurait
          au moment de la conclusion du contrat. Ces CGU ne privent pas les consommateurs résidant
          dans un autre État membre de l'Union européenne des protections impératives de leur droit
          national.
        </p>
      </Section>

      <p className="mt-10 text-[14px] leading-[1.7]" style={{ color: C.inkFaint }}>
        Voir aussi : <LegalLink href={PRIVACY_PATH}>Politique de confidentialité</LegalLink>
      </p>
    </LegalLayout>
  );
}

/* ────────────────────────────────────────────
   Politique de confidentialité
   ──────────────────────────────────────────── */

export function PrivacyPage() {
  return (
    <LegalLayout title="Politique de confidentialité">
      <div className="mt-6 space-y-3 text-[15px] leading-[1.75]" style={{ color: C.inkSoft }}>
        <p>
          Cette politique décrit comment Monumia traite vos données personnelles, en conformité
          avec le règlement (UE) 2016/679 (« <Strong>RGPD</Strong> ») et la loi n° 78-17 du
          6 janvier 1978 (« Informatique et Libertés »). Elle s'applique au site monumia.fr, à
          l'application app.monumia.fr et à la liste d'attente de lancement.
        </p>
        <p>
          Notre principe : <Strong>nous ne collectons que ce qui est nécessaire au Service, nous ne
          vendons ni ne louons jamais vos données, et nous n'affichons aucune publicité.</Strong>
        </p>
      </div>

      <Section title="1. Responsable du traitement">
        <p>
          Le responsable du traitement est Monumia, SAS immatriculée au RCS de Lyon sous le
          numéro 106 236 748, dont le siège social est situé 10 avenue Jean Jaurès,
          69370 Saint-Didier-au-Mont-d'Or, France, joignable à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>, y compris pour
          toute question relative aux données personnelles.
        </p>
      </Section>

      <Section title="2. Données que nous collectons">
        <p>Nous collectons uniquement les données suivantes :</p>
        <Ul>
          <li>
            <Strong>Liste d'attente de lancement</Strong> : votre adresse e-mail et la page depuis
            laquelle vous vous êtes inscrit. Rien d'autre.
          </li>
          <li>
            <Strong>Compte utilisateur</Strong> : prénom, nom, adresse e-mail, mot de passe (stocké
            exclusivement sous forme hachée) et, si vous le renseignez, numéro de téléphone.
          </li>
          <li>
            <Strong>Données de vos projets</Strong> : les informations que vous déclarez sur vos
            monuments et vos projets (localisation, protections, nature des travaux, réponses au
            questionnaire) et les documents que vous téléversez pour vos dossiers.
          </li>
          <li>
            <Strong>Facturation</Strong> : l'historique de vos abonnements et paiements. Les données
            de carte bancaire sont saisies directement sur les pages sécurisées de Stripe et{' '}
            <Strong>ne transitent jamais par nos serveurs</Strong>.
          </li>
          <li>
            <Strong>Données techniques</Strong> : journaux de connexion des serveurs (adresse IP,
            horodatage, pages appelées), à des fins de sécurité et de diagnostic d'incident.
          </li>
          <li>
            <Strong>Mesure d'audience de l'application</Strong> : les pages consultées et les
            étapes franchies (création d'un monument, d'un projet, d'un dossier), sous forme de
            statistiques anonymes. Aucun cookie ni stockage sur votre appareil, aucun identifiant
            de compte, de monument ou de projet, aucun texte affiché à l'écran, aucun
            enregistrement de votre session (voir l'article 9).
          </li>
        </Ul>
        <p>Et voici ce que nous ne faisons pas :</p>
        <Ul>
          <li>aucun cookie publicitaire ni traceur, aucun suivi individuel de votre navigation ;</li>
          <li>aucune revente, location ou cession de vos données à des tiers ;</li>
          <li>
            aucune transmission de vos données personnelles à des services d'intelligence
            artificielle externes : le moteur d'analyse d'éligibilité de Monumia fonctionne sur nos
            propres serveurs, sans appel à des services tiers. Seules des données préalablement
            anonymisées, qui ne vous concernent plus, peuvent servir à entraîner des modèles (voir
            l'article 4) ;
          </li>
          <li>aucune collecte de données auprès de mineurs (voir l'article 10).</li>
        </Ul>
      </Section>

      <Section title="3. Finalités et bases légales">
        <Ul>
          <li>
            <Strong>Fournir le Service</Strong> (compte, diagnostics, dossiers, support) :
            exécution du contrat (article 6.1.b du RGPD).
          </li>
          <li>
            <Strong>Vous prévenir du lancement</Strong> (liste d'attente) : votre consentement
            (article 6.1.a), retirable à tout moment.
          </li>
          <li>
            <Strong>Facturation et comptabilité</Strong> : obligation légale (article 6.1.c).
          </li>
          <li>
            <Strong>Sécurité du Service</Strong> (journaux, prévention des abus) : intérêt
            légitime (article 6.1.f).
          </li>
          <li>
            <Strong>Mesure d'audience de l'application</Strong>, pour repérer les écrans qui se
            comprennent mal : intérêt légitime (article 6.1.f). Vous pouvez vous y opposer à tout
            moment (voir l'article 9).
          </li>
          <li>
            <Strong>E-mails liés au fonctionnement du Service</Strong> (confirmations, invitations
            de collaboration, alertes sur vos projets) : exécution du contrat. Nous n'envoyons pas
            de prospection commerciale pour le compte de tiers.
          </li>
          <li>
            <Strong>Constitution de jeux de données anonymisés</Strong> pour améliorer le Service
            et entraîner des modèles d'intelligence artificielle (voir l'article 4) : intérêt
            légitime (article 6.1.f), l'anonymisation étant un traitement ultérieur compatible
            avec les finalités initiales (article 5.1.b). Vous pouvez vous y opposer à tout moment.
          </li>
        </Ul>
      </Section>

      <Section id="donnees-anonymisees" title="4. Données anonymisées et entraînement de modèles d'intelligence artificielle">
        <p>
          Pour fiabiliser nos diagnostics d'éligibilité et développer de nouvelles fonctionnalités,
          nous pouvons constituer, à partir des informations renseignées sur le Service, des{' '}
          <Strong>jeux de données anonymisés</Strong> servant à des analyses statistiques et à
          l'<Strong>entraînement de modèles d'intelligence artificielle</Strong>, par Monumia ou
          pour son compte.
        </p>
        <p>
          <Strong>Ce qui peut être utilisé</Strong> : uniquement les données qui décrivent le
          monument et le projet, jamais celles qui vous décrivent.
        </p>
        <Ul>
          <li>
            les informations déclarées sur le monument (nature du bien, protection, état sanitaire,
            caractéristiques, localisation généralisée à l'échelle de la commune ou du département)
            et sur le projet (nature et ampleur des travaux, calendrier, budget) ;
          </li>
          <li>vos réponses au questionnaire d'éligibilité et les résultats du diagnostic ;</li>
          <li>
            les pièces de dossier qui, par nature ou par votre choix, ont vocation à être rendues
            publiques (par exemple un dossier de demande d'aide destiné à publication).
          </li>
        </Ul>
        <p>
          <Strong>Ce qui n'est jamais utilisé</Strong> : vos nom, prénom, adresse e-mail, numéro
          de téléphone, identifiants de connexion, données de facturation, journaux techniques, ni
          les documents confidentiels (pièces d'identité, coordonnées bancaires, documents fiscaux,
          correspondance privée, tout document que vous n'avez pas destiné à une diffusion
          publique).
        </p>
        <p>
          <Strong>Comment nous anonymisons</Strong> : avant toute utilisation, nous supprimons ou
          généralisons tout élément permettant, directement ou par recoupement, de vous identifier
          ou d'identifier un propriétaire privé (identifiants de compte, adresse précise, références
          cadastrales, noms de personnes présents dans les documents). L'anonymisation est
          irréversible : les jeux de données obtenus ne constituent plus des données personnelles
          au sens du RGPD. Nous nous engageons à ne pas chercher à réidentifier les personnes
          concernées et imposons la même interdiction à nos éventuels prestataires. Les données
          relatives aux monuments appartenant à des personnes morales (communes, associations,
          sociétés) ne sont pas des données personnelles et peuvent être utilisées sous la même
          forme.
        </p>
        <p>
          <Strong>Votre droit d'opposition</Strong> : vous pouvez vous opposer à tout moment, sans
          motif, à l'utilisation de vos données à cette fin en écrivant à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>. Votre opposition
          prend effet pour toutes les données non encore anonymisées ; les données déjà anonymisées
          ne pouvant plus vous être rattachées, il nous est techniquement impossible de les retirer
          des jeux de données existants. Cette opposition n'a aucune incidence sur votre accès au
          Service.
        </p>
      </Section>

      <Section title="5. Destinataires et sous-traitants">
        <p>
          Vos données ne sont accessibles qu'à l'équipe de Monumia, dans la limite de ce qui est
          nécessaire, et aux sous-traitants suivants, chacun lié par un accord de traitement des
          données conforme à l'article 28 du RGPD :
        </p>
        <Ul>
          <li>
            <Strong>OVH SAS</Strong> (France) : hébergement des serveurs applicatifs, en France.
          </li>
          <li>
            <Strong>Supabase, Inc.</Strong> : base de données, authentification et stockage de
            fichiers, avec des données hébergées exclusivement dans l'Union européenne.
          </li>
          <li>
            <Strong>Stripe</Strong> (Stripe Payments Europe, Ltd., Irlande) : traitement des
            paiements.
          </li>
          <li>
            <Strong>Resend, Inc.</Strong> (États-Unis) : envoi des e-mails du Service (adresse
            e-mail et contenu des messages uniquement).
          </li>
          <li>
            <Strong>PostHog, Inc.</Strong> : mesure d'audience de l'application, avec des données
            hébergées dans l'Union européenne.
          </li>
        </Ul>
        <p>
          Vos données peuvent également être communiquées aux autorités lorsque la loi l'exige. Si
          vous partagez un projet avec un collaborateur, celui-ci accède aux données de ce projet
          dans la limite du rôle que vous lui attribuez.
        </p>
      </Section>

      <Section title="6. Transferts hors de l'Union européenne">
        <p>
          Nos serveurs et nos bases de données sont situés en France et dans l'Union européenne.
          Certains sous-traitants (Supabase, Inc., Resend, Inc. et PostHog, Inc., sociétés américaines) peuvent
          impliquer un accès à des données depuis les États-Unis ; ces transferts sont encadrés par
          des garanties appropriées au sens du chapitre V du RGPD (clauses contractuelles types de
          la Commission européenne et, le cas échéant, certification au cadre de protection des
          données UE-États-Unis). Vous pouvez obtenir une copie de ces garanties en écrivant à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>.
        </p>
      </Section>

      <Section title="7. Durées de conservation">
        <Ul>
          <li>
            <Strong>Compte et données de projets</Strong> : pendant toute la durée de vie du
            compte, puis suppression dans les trente (30) jours suivant sa clôture. Certaines
            données peuvent être conservées en archivage restreint le temps des prescriptions
            légales (au maximum cinq ans) lorsque c'est nécessaire à la défense de nos droits.
          </li>
          <li>
            <Strong>Documents téléversés</Strong> : supprimés avec le projet ou le compte auquel
            ils sont rattachés.
          </li>
          <li>
            <Strong>Jeux de données anonymisés</Strong> (article 4) : n'étant plus des données
            personnelles, ils peuvent être conservés sans limitation de durée, y compris après la
            clôture de votre compte.
          </li>
          <li>
            <Strong>Liste d'attente</Strong> : jusqu'au lancement du Service, puis au plus trois
            ans après le dernier contact ; suppression immédiate sur simple demande.
          </li>
          <li>
            <Strong>Factures et pièces comptables</Strong> : dix ans (obligation légale).
          </li>
          <li>
            <Strong>Journaux techniques</Strong> : douze mois au maximum.
          </li>
          <li>
            <Strong>Statistiques de mesure d'audience</Strong> : vingt-cinq mois au maximum.
          </li>
        </Ul>
      </Section>

      <Section title="8. Vos droits">
        <p>
          Conformément au RGPD et à la loi Informatique et Libertés, vous disposez des droits
          suivants sur vos données :
        </p>
        <Ul>
          <li>droit d'accès et droit d'obtenir une copie de vos données ;</li>
          <li>droit de rectification des données inexactes ou incomplètes ;</li>
          <li>droit à l'effacement (« droit à l'oubli ») ;</li>
          <li>droit à la limitation du traitement ;</li>
          <li>
            droit d'opposition, notamment aux traitements fondés sur notre intérêt légitime, y
            compris la constitution de jeux de données anonymisés décrite à l'article 4 ;
          </li>
          <li>droit à la portabilité de vos données ;</li>
          <li>
            droit de retirer votre consentement à tout moment, sans remettre en cause la licéité
            du traitement antérieur ;
          </li>
          <li>
            droit de définir des directives relatives au sort de vos données après votre décès
            (article 85 de la loi Informatique et Libertés).
          </li>
        </Ul>
        <p>
          Pour exercer ces droits, écrivez à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink>. Nous répondons
          dans un délai d'un mois, prorogeable de deux mois pour les demandes complexes. Une pièce
          justifiant de votre identité peut être demandée en cas de doute raisonnable.
        </p>
        <p>
          Si vous estimez que vos droits ne sont pas respectés, vous pouvez introduire une
          réclamation auprès de la CNIL : Commission Nationale de l'Informatique et des Libertés,
          3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07 (
          <LegalLink href="https://www.cnil.fr">www.cnil.fr</LegalLink>).
        </p>
      </Section>

      <Section title="9. Cookies et stockage local">
        <p>
          Le site monumia.fr <Strong>n'utilise aucun cookie</Strong> : pas de traceur, pas de
          mesure d'audience, pas de bouton de partage tiers. Les polices de caractères sont
          hébergées sur nos propres serveurs.
        </p>
        <p>
          L'application app.monumia.fr utilise uniquement le stockage local de votre navigateur
          pour conserver votre session d'authentification. Ce stockage est strictement nécessaire
          à la fourniture du Service et est, à ce titre, exempté de consentement préalable
          (article 82 de la loi Informatique et Libertés).
        </p>
        <p>
          L'application mesure aussi son audience, avec l'outil PostHog, dans les conditions où la
          CNIL dispense la mesure d'audience de consentement : sans cookie ni stockage sur votre
          appareil, sous forme de statistiques anonymes réservées à Monumia, jamais recoupées avec
          votre compte ni avec d'autres traitements. Les adresses des pages sont transmises sans
          les identifiants qu'elles contiennent, et ni le texte affiché à l'écran ni le
          déroulement de votre session ne sont enregistrés. Aucun bandeau de consentement n'est
          donc requis. Vous pouvez vous opposer à cette mesure à tout moment depuis la page
          Profil de l'application ; votre choix est retenu dans votre navigateur. Le réglage « Do
          Not Track » de votre navigateur vaut également opposition.
        </p>
        <p>
          Si nous devions un jour introduire des traceurs soumis à consentement, celui-ci vous
          serait demandé au préalable.
        </p>
        <p>
          Les pages de paiement sont opérées par Stripe sur son propre domaine et sont soumises à
          sa propre politique de confidentialité.
        </p>
      </Section>

      <Section title="10. Mineurs">
        <p>
          Le Service est réservé aux personnes majeures. <Strong>Nous ne collectons pas sciemment
          de données personnelles concernant des mineurs</Strong>, et aucune de nos offres ne leur
          est destinée. Si vous êtes titulaire de l'autorité parentale et pensez qu'un mineur nous
          a transmis des données personnelles, contactez-nous à{' '}
          <LegalLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</LegalLink> : elles seront
          supprimées sans délai.
        </p>
      </Section>

      <Section title="11. Sécurité">
        <p>
          Nous mettons en œuvre des mesures techniques et organisationnelles adaptées : chiffrement
          des échanges (TLS), hébergement en France et dans l'Union européenne, mots de passe
          stockés exclusivement sous forme hachée, cloisonnement des accès aux données par compte,
          accès administrateur restreint et journalisé. En cas de violation de données susceptible
          d'engendrer un risque pour vos droits et libertés, nous notifierons la CNIL dans les 72
          heures et, si le risque est élevé, nous vous en informerons directement.
        </p>
      </Section>

      <Section title="12. Absence de décision entièrement automatisée">
        <p>
          Le diagnostic d'éligibilité de Monumia est calculé automatiquement à partir de vos
          déclarations, mais il est <Strong>purement informatif</Strong> : il ne produit aucune
          décision ayant des effets juridiques à votre égard au sens de l'article 22 du RGPD. La
          décision d'attribuer ou non une aide appartient exclusivement aux organismes financeurs.
        </p>
      </Section>

      <Section title="13. Modifications de cette politique">
        <p>
          Nous pouvons faire évoluer cette politique, notamment en cas de changement de
          sous-traitant ou de fonctionnalité. La date de dernière mise à jour figure en haut de
          page ; en cas de modification substantielle, les utilisateurs disposant d'un compte en
          sont informés par e-mail ou dans l'application.
        </p>
      </Section>

      <p className="mt-10 text-[14px] leading-[1.7]" style={{ color: C.inkFaint }}>
        Voir aussi : <LegalLink href={CGU_PATH}>Conditions générales d'utilisation</LegalLink>
        {' · '}
        <LegalLink href={`${CGU_PATH}#mentions-legales`}>Mentions légales</LegalLink>
      </p>
    </LegalLayout>
  );
}
