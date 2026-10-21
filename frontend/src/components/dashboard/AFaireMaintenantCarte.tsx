import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { format, parseISO } from 'date-fns';
import type { TFunction } from 'i18next';
import { localeDateFns } from '@/i18n/format';
import { Picto } from '@/components/shared/ecrans/Picto';
import { deadlineLink } from '@/lib/project-stats';
import { quandLibelle, type AFaire } from '@/lib/a-faire-maintenant';

/** Le bouton et la bande « Prochaine étape », selon ce qu'il reste à faire. */
function suite(a: AFaire, t: TFunction<'dashboard'>): { cta: string; etape: React.ReactNode } {
  const gras = { b: <b /> };
  switch (a.nature) {
    case 'questions': {
      const n = a.questions;
      return {
        cta: t('AFaireMaintenantCarte.questions.cta', { count: n }),
        etape: (
          <Trans t={t} i18nKey="AFaireMaintenantCarte.questions.etape" count={n} components={gras} />
        ),
      };
    }
    case 'verifier':
      return {
        cta: t('AFaireMaintenantCarte.verifier.cta'),
        etape: <>{t('AFaireMaintenantCarte.verifier.etape')}</>,
      };
    case 'eligible':
      return {
        cta: t('AFaireMaintenantCarte.eligible.cta'),
        etape: <Trans t={t} i18nKey="AFaireMaintenantCarte.eligible.etape" components={gras} />,
      };
    case 'demarche':
      return {
        cta: t('AFaireMaintenantCarte.demarche.cta'),
        etape: <Trans t={t} i18nKey="AFaireMaintenantCarte.demarche.etape" components={gras} />,
      };
    case 'dossier':
      return {
        cta: t('AFaireMaintenantCarte.dossier.cta'),
        etape: (
          <Trans
            t={t}
            i18nKey="AFaireMaintenantCarte.dossier.etape"
            values={{ detail: a.detail }}
            components={gras}
          />
        ),
      };
  }
}

/**
 * « À faire maintenant » : la date la plus proche, en éphéméride orange, ce
 * qu'elle concerne, et la bande bleue qui dit la prochaine étape. Toute la
 * carte mène où mène son bouton (`.now-lien::after`).
 */
export function AFaireMaintenantCarte({ aFaire }: { aFaire: AFaire | null }) {
  const { t } = useTranslation('dashboard');
  if (!aFaire) {
    return (
      <section className="now calme" aria-labelledby="nowT">
        <div className="now-in">
          <div>
            <span className="tag-now">{t('toutEstAJour')}</span>
            <h2 id="nowT">{t('AFaireMaintenantCarte.aucuneDateLimite')}</h2>
          </div>
        </div>
      </section>
    );
  }

  const { echeance } = aFaire;
  const date = parseISO(echeance.date);
  const retard = echeance.joursRestants < 0;
  const { cta, etape } = suite(aFaire, t);
  const sousTitre = [aFaire.monumentNom, aFaire.nature === 'dossier' ? null : aFaire.detail].filter(Boolean);

  return (
    <section className="now" aria-labelledby="nowT">
      <div className="now-in">
        <div className={retard ? 'cal retard' : 'cal'} aria-hidden="true">
          <b>{format(date, 'd', { locale: localeDateFns() })}</b>
          <span>{format(date, 'MMM', { locale: localeDateFns() })}</span>
        </div>
        <div>
          <span className={retard ? 'tag-now retard' : 'tag-now'}>
            {t('aFaireMaintenant', { quand: quandLibelle(echeance.joursRestants) })}
          </span>
          <h2 id="nowT">{aFaire.titre}</h2>
          {(aFaire.montant || sousTitre.length > 0) && (
            <p className="sub">
              {aFaire.montant && <b>{aFaire.montant}</b>}
              {aFaire.montant && sousTitre.length > 0 && ' · '}
              {sousTitre.join(' · ')}
            </p>
          )}
        </div>
        <Link className="btn b-orange now-lien" to={deadlineLink(echeance)}>
          {cta}
          <Picto nom="fleche" />
        </Link>
      </div>
      <div className="now-step">
        <span className="lbl">{t('AFaireMaintenantCarte.prochaineEtape')}</span>
        <span>{etape}</span>
      </div>
    </section>
  );
}
