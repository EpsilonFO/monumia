import { Fragment } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { formatCurrency } from '@/lib/format-utils';
import { C, SERIF } from '@/lib/brand';
import type { SyntheseInvite } from '@/types';

/**
 * La page de connexion, en portant `?reprise=brouillon`.
 *
 * Ce paramètre est ce qui autorise la page de connexion à finir sur l'écran de
 * reprise (le monument et le projet y sont créés, puis on atterrit sur le
 * diagnostic). Sans lui, un brouillon oublié dans le `localStorage`
 * détournerait n'importe quelle connexion ordinaire.
 */
const LIEN_CONNEXION = '/login?reprise=brouillon';

/**
 * Un chiffre et ce qu'il veut dire.
 *
 * « jusqu'à » est une ligne à part, au-dessus de la valeur : ce sont des
 * plafonds cumulés, pas des montants acquis, et la nuance doit se lire d'un
 * coup d'œil plutôt que se cacher dans le libellé.
 */
function Chiffre({ valeur, libelle }: { valeur: string; libelle: string }) {
  const { t } = useTranslation('project');
  return (
    <div
      className="flex w-full min-w-0 flex-col items-center gap-0.5 rounded-2xl border px-4 py-4 sm:flex-1"
      style={{ background: C.card, borderColor: C.border }}
    >
      <span
        className="text-[13px] font-semibold uppercase tracking-[0.12em]"
        style={{ color: C.grayMuted }}
      >
        {t('InscriptionStep.jusqua')}
      </span>
      <span
        className="text-[clamp(1.4rem,4vw,1.9rem)] font-bold leading-none tabular-nums"
        style={{ fontFamily: SERIF, color: C.orange }}
      >
        {valeur}
      </span>
      <span className="mt-0.5 text-[14.5px] leading-snug" style={{ color: C.grayFg }}>
        {libelle}
      </span>
    </div>
  );
}

interface InscriptionStepProps {
  /** Résultat du dernier diagnostic invité, ou `null` s'il n'a pas abouti. Son
   *  absence n'empêche pas de continuer : elle ne coûte que l'accroche. */
  synthese: SyntheseInvite | null;
  /** Retour au questionnaire. On arrive ici aussi en QUITTANT le questionnaire
   *  en cours de route : sans ce retour, ce serait une porte à sens unique. */
  onRetour?: () => void;
}

/**
 * Dernière étape du parcours découverte : le résultat en chiffres, et la porte.
 *
 * Toute la page tient sur un nombre — combien de financements — parce que c'est
 * la seule chose que le visiteur est venu chercher, et la seule qui justifie de
 * créer un compte. Le reste (montant, part des travaux, dispositifs passés au
 * crible) le qualifie, en une phrase chacun.
 *
 * Ce qui manque pour aller plus loin est un `users.id` : `monuments.user_id` a
 * une clé étrangère vers `public.users`, et il n'existe pas de compte anonyme
 * (cf. `useBrouillonInviteStore`). D'où la porte, et non un « inscrivez-vous »
 * posé en travers du diagnostic.
 *
 * Un seul bouton, vers la VRAIE page de connexion : elle porte déjà Google, la
 * connexion et l'inscription, et son `?reprise=brouillon` ramène ici même — le
 * brouillon est rejoué, puis on atterrit sur la page du projet. Dupliquer un
 * formulaire d'inscription sur cet écran l'aurait noyé, alors qu'on veut qu'il
 * ne dise qu'une chose.
 */
export function InscriptionStep({ synthese, onRetour }: InscriptionStepProps) {
  const { t } = useTranslation('project');
  const nombre = synthese
    ? synthese.eligibles + synthese.potentielles + synthese.atteignables
    : 0;
  const montant = synthese?.montantPotentielTotal ?? synthese?.montantAtteignableTotal ?? null;
  const taux = synthese?.tauxTravauxMaxPct ?? null;

  const chiffres = [
    montant
      ? { valeur: formatCurrency(montant), libelle: t('InscriptionStep.financementsCumules') }
      : null,
    taux
      ? { valeur: t('InscriptionStep.taux', { taux }), libelle: t('InscriptionStep.coutTravaux') }
      : null,
  ].filter((c): c is { valeur: string; libelle: string } => c !== null);

  return (
    // Centré verticalement, contrairement aux autres étapes : la scène du shell
    // est ancrée en haut pour que les formulaires ne fassent pas glisser leur
    // en-tête en grandissant. Ici le contenu a une hauteur fixe, et le chiffre
    // doit tomber au milieu de l'écran.
    //
    // La hauteur se calcule ici plutôt qu'en étirant la scène du shell : elle
    // sert cinq autres étapes, dont l'ancrage en haut est voulu. On retire les
    // 8 rem du gouttière verticale de la scène et du header mobile — un peu
    // court plutôt qu'un peu long, pour ne pas faire apparaître d'ascenseur.
    <div className="flex min-h-[calc(100dvh-7rem)] flex-col items-center justify-center gap-7 text-center sm:min-h-[calc(100dvh-9rem)] lg:min-h-[calc(100dvh-5rem)]">
      <div className="flex flex-col items-center gap-3">
        <div
          className="text-[14px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.orange }}
        >
          {synthese === null ? t('InscriptionStep.derniereEtape') : t('InscriptionStep.diagnosticPret')}
        </div>

        {synthese === null ? (
          // La relance du diagnostic a échoué : on ignore le compte réel, donc
          // on n'avance AUCUN chiffre. Le parcours continue quand même — les
          // réponses sont dans le brouillon, le diagnostic sera recalculé
          // côté compte.
          <>
            <h1
              className="max-w-md text-[clamp(1.3rem,3.2vw,1.7rem)] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {t('InscriptionStep.manqueCompte')}
            </h1>
            <p className="max-w-md text-[16px] leading-relaxed" style={{ color: C.grayFg }}>
              {t('InscriptionStep.reponsesEnregistrees')}
            </p>
          </>
        ) : nombre > 0 ? (
          <>
            {/* Le nombre EST la page : tout le reste le commente. */}
            <span
              className="block text-[clamp(4.5rem,22vw,7rem)] font-bold leading-[0.9] tabular-nums"
              style={{ fontFamily: SERIF, color: C.blue }}
            >
              {nombre}
            </span>
            <h1
              className="max-w-md text-[clamp(1.25rem,3vw,1.6rem)] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {t('InscriptionStep.peuventContribuer', { count: nombre })}
            </h1>
            {synthese && synthese.totalAnalysees > 0 && (
              <p className="max-w-md text-[16px] leading-relaxed" style={{ color: C.grayFg }}>
                <Trans
                  t={t}
                  i18nKey="InscriptionStep.compare"
                  count={synthese.totalAnalysees}
                  components={{
                    nombre: <span className="font-semibold tabular-nums" style={{ color: C.ink }} />,
                  }}
                />
              </p>
            )}
          </>
        ) : (
          // Zéro financement, et on le sait : on ne le maquille pas. Le détail
          // garde de la valeur — il dit sur quel critère chaque aide s'est
          // arrêtée, et ce qui suffirait parfois à la faire basculer.
          <>
            <h1
              className="max-w-md text-[clamp(1.3rem,3.2vw,1.7rem)] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {t('InscriptionStep.aucunFinancement')}
            </h1>
            <p className="max-w-md text-[16px] leading-relaxed" style={{ color: C.grayFg }}>
              {t('InscriptionStep.detailCritere')}
            </p>
          </>
        )}
      </div>

      {chiffres.length > 0 && (
        // « ou » et non deux chiffres côte à côte : les deux plafonds ne
        // s'additionnent pas, ils disent la même enveloppe de deux façons —
        // beaucoup d'aides plafonnent en euros, d'autres en part des travaux.
        <div className="flex w-full max-w-md flex-col items-center gap-3 sm:flex-row">
          {chiffres.map((c, i) => (
            <Fragment key={c.libelle}>
              {i > 0 && (
                <span
                  className="shrink-0 text-[14px] font-semibold uppercase tracking-[0.14em]"
                  style={{ color: C.grayMuted }}
                >
                  {t('InscriptionStep.ou')}
                </span>
              )}
              <Chiffre valeur={c.valeur} libelle={c.libelle} />
            </Fragment>
          ))}
        </div>
      )}

      <div className="relative flex flex-col items-center gap-3">
        <Link
          to={LIEN_CONNEXION}
          className="group inline-flex items-center gap-2 rounded-2xl px-7 py-4 text-[18px] font-semibold text-white transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[var(--shadow-pop)]"
          style={{ background: C.orange }}
        >
          {t('InscriptionStep.seConnecter')}
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
        </Link>

        {/* Discret, mais indispensable : on atteint aussi cet écran en quittant
            le questionnaire, et répondre à quelques questions de plus est le
            geste qui affine le plus le diagnostic. */}
        {onRetour && (
          <button
            type="button"
            onClick={onRetour}
            className="inline-flex items-center gap-1.5 text-[15px] font-medium underline-offset-2 hover:underline"
            style={{ color: C.grayMuted }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t('InscriptionStep.plusDeQuestions')}
          </button>
        )}
      </div>
    </div>
  );
}
