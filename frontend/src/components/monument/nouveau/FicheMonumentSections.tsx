import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ETATS_CONSERVATION } from '@/constants/monument-options';
import {
  GROUPES_PROTECTION,
  GROUPES_SIECLE,
  GROUPES_TYPE_EDIFICE,
  SIECLES_EXCLUSIFS,
  affectationApplicable,
  architectureRomaneApplicable,
  avecProtection,
  avecTypesEdifice,
  formaterSiecles,
  groupesProprietaire,
  lireSiecles,
  protectionApplicable,
  sectionsRemplies,
  proprietairesCoches,
  typesCoches,
  type ChampFiche,
  type FicheMonument,
} from '@/lib/fiche-monument';
import type { Monument, ProtectionLevel } from '@/types';
import { ChampCommune } from './ChampCommune';
import { MenuChoix } from './MenuChoix';

interface FicheMonumentSectionsProps {
  fiche: FicheMonument;
  onChange: (maj: FicheMonument) => void;
  /** La recherche Mérimée et ses liens, en tête de la section 1. */
  merimee: ReactNode;
  /** Champs encadrés en orange : ce qui reste à remplir après Mérimée. */
  aRemplir?: ReadonlySet<ChampFiche>;
}

/**
 * Une précision oui/non du type d'édifice, en deux boutons. Recliquer la
 * réponse choisie la retire : « je ne sais pas » n'est pas un bouton de plus,
 * c'est l'absence de réponse, et la question reste alors posée au
 * questionnaire.
 */
function Precision({
  id,
  titre,
  pourquoi,
  oui,
  non,
  valeur,
  onChange,
  className,
}: {
  id: string;
  titre: string;
  pourquoi: string;
  oui: string;
  non: string;
  valeur: boolean | null | undefined;
  onChange: (v: boolean | null) => void;
  className: string;
}) {
  const { t } = useTranslation(['monuments', 'common']);
  return (
    <div className={className}>
      <span className="lb" id={id}>
        {titre} <span className="opt">{t('FicheMonumentSections.facultatif')}</span>
      </span>
      <p className="why">{pourquoi}</p>
      <div className="seg seg-2" role="group" aria-labelledby={id}>
        {([true, false] as const).map((v) => (
          <button
            key={String(v)}
            type="button"
            aria-pressed={valeur === v}
            onClick={() => onChange(valeur === v ? null : v)}
          >
            {v ? oui : non}
          </button>
        ))}
      </div>
    </div>
  );
}

function Section({
  n,
  titre,
  remplie,
  children,
}: {
  n: number;
  titre: string;
  remplie: boolean;
  children: ReactNode;
}) {
  const id = `nm-s${n}`;
  return (
    <section className={remplie ? 'sec full' : 'sec'} aria-labelledby={id}>
      <div className="sec-t">
        <span className="num">{remplie ? <Picto nom="coche" /> : n}</span>
        <h2 id={id}>{titre}</h2>
      </div>
      {children}
    </section>
  );
}

/**
 * Les trois sections du formulaire de création (maquette du designer), sur les
 * champs du produit. Pas de quatrième section « Votre projet » : travaux et
 * montant appartiennent au projet, et se saisissent dans son wizard.
 */
export function FicheMonumentSections({ fiche, onChange, merimee, aRemplir }: FicheMonumentSectionsProps) {
  const { t } = useTranslation(['monuments', 'common']);
  const [s1, s2, s3] = sectionsRemplies(fiche);
  const siecles = lireSiecles(fiche.siecleConstruction);
  const fld = (champ: ChampFiche) => (aRemplir?.has(champ) ? 'fld a-remplir' : 'fld');

  return (
    <>
      <Section n={1} titre={t('FicheMonumentSections.sectionMonument')} remplie={s1}>
        {merimee}
        <div className="row2">
          <div className={fld('nom')}>
            <label htmlFor="nm-nom">{t('FicheMonumentSections.nomBatiment')}</label>
            <input
              className="txt"
              id="nm-nom"
              value={fiche.nom ?? ''}
              placeholder={t('FicheMonumentSections.nomPlaceholder')}
              autoComplete="off"
              onChange={(e) => onChange({ nom: e.target.value })}
            />
          </div>
          <div className={fld('commune')}>
            <label htmlFor="nm-commune">{t('FicheMonumentSections.commune')}</label>
            <ChampCommune
              id="nm-commune"
              value={fiche.commune ?? ''}
              reconnue={Boolean(fiche.codeInsee)}
              onChange={(nom) => onChange({ commune: nom, codeInsee: '', departement: undefined })}
              onSelect={(c) =>
                onChange({ commune: c.nom, codeInsee: c.codeInsee, departement: c.departement })
              }
            />
          </div>
        </div>

        <div className={fld('typeEdifice')}>
          <span className="lb">
            {t('FicheMonumentSections.typeEdifice')}{' '}
            <span className="opt">{t('FicheMonumentSections.plusieursChoix')}</span>
          </span>
          <p className="why">
            {t('FicheMonumentSections.typeEdificeAide')}
          </p>
          <MenuChoix
            label={t('FicheMonumentSections.typeEdificeMenu')}
            placeholder={t('FicheMonumentSections.typeEdificePlaceholder')}
            groupes={GROUPES_TYPE_EDIFICE}
            multiple
            recherche
            valeurs={typesCoches(fiche)}
            onChange={(v) => onChange(avecTypesEdifice(fiche, v))}
          />
        </div>

        {/* L'affectation n'apparaît que si au moins un type coché l'admet
            (`TYPES_AVEC_AFFECTATION_CULTE`), et se vide quand plus aucun ne le
            fait. Le style roman suit le domaine Mérimée de la notice choisie. */}
        {affectationApplicable(fiche) && (
          <Precision
            id="nm-l-culte"
            titre={t('FicheMonumentSections.culte.titre')}
            pourquoi={t('FicheMonumentSections.culte.pourquoi')}
            oui={t('FicheMonumentSections.culte.oui')}
            non={t('FicheMonumentSections.culte.non')}
            valeur={fiche.affecteAuCulte}
            className={fld('affecteAuCulte')}
            onChange={(v) => onChange({ affecteAuCulte: v })}
          />
        )}
        {architectureRomaneApplicable(fiche) && (
          <Precision
            id="nm-l-roman"
            titre={t('FicheMonumentSections.roman.titre')}
            pourquoi={t('FicheMonumentSections.roman.pourquoi')}
            oui={t('FicheMonumentSections.roman.oui')}
            non={t('common:reponses.non')}
            valeur={fiche.architectureRomane}
            className={fld('architectureRomane')}
            onChange={(v) => onChange({ architectureRomane: v })}
          />
        )}

        <div className="fld">
          <span className="lb" id="nm-l-siecle">
            {t('FicheMonumentSections.siecle')}{' '}
            <span className="opt">{t('FicheMonumentSections.plusieursChoix')}</span>
          </span>
          <MenuChoix
            label={t('FicheMonumentSections.siecle')}
            placeholder={t('FicheMonumentSections.sieclePlaceholder')}
            groupes={GROUPES_SIECLE}
            multiple
            exclusifs={SIECLES_EXCLUSIFS}
            valeurs={siecles ?? []}
            onChange={(v) => onChange({ siecleConstruction: formaterSiecles(v) })}
            texteLibre={siecles === null ? fiche.siecleConstruction : undefined}
            onEffacerTexteLibre={() => onChange({ siecleConstruction: '' })}
            notePanel={
              siecles === null ? (
                <>
                  {t('FicheMonumentSections.texteActuel', { texte: fiche.siecleConstruction })}
                </>
              ) : undefined
            }
          />
        </div>

        <div className={fld('etatConservation')}>
          <span className="lb" id="nm-l-etat">
            {t('FicheMonumentSections.etatBatiment')}
          </span>
          <p className="why">{t('FicheMonumentSections.etatAide')}</p>
          <div className="seg" role="group" aria-labelledby="nm-l-etat">
            {ETATS_CONSERVATION.map((e) => (
              <button
                key={e.value}
                type="button"
                aria-pressed={fiche.etatConservation === e.value}
                onClick={() =>
                  onChange({
                    etatConservation:
                      fiche.etatConservation === e.value
                        ? undefined
                        : (e.value as Monument['etatConservation']),
                  })
                }
              >
                {e.label}
              </button>
            ))}
          </div>
        </div>

        <div className="fld">
          <label htmlFor="nm-description">
            {t('FicheMonumentSections.descriptionGenerale')}{' '}
            <span className="opt">{t('FicheMonumentSections.facultatif')}</span>
          </label>
          <textarea
            className="txt"
            id="nm-description"
            rows={4}
            value={fiche.descriptionGenerale ?? ''}
            placeholder={t('FicheMonumentSections.descriptionPlaceholder')}
            onChange={(e) => onChange({ descriptionGenerale: e.target.value })}
          />
        </div>
      </Section>

      <Section n={2} titre={t('FicheMonumentSections.sectionProtection')} remplie={s2}>
        <div className={fld('protection')}>
          <span className="lb">{t('FicheMonumentSections.protection')}</span>
          <MenuChoix
            label={t('FicheMonumentSections.protection')}
            placeholder={t('FicheMonumentSections.protectionPlaceholder')}
            groupes={GROUPES_PROTECTION}
            valeurs={fiche.protection ? [fiche.protection] : []}
            onChange={(v) => onChange(avecProtection(v[0] as ProtectionLevel | undefined))}
          />
        </div>
        {/* Un bien non protégé n'a ni date ni détail : les deux champs se
            retirent, comme le « Siècle de la protection » de la maquette, et
            sont vidés au passage (`avecProtection`). */}
        <div className="fld" hidden={!protectionApplicable(fiche)}>
          <label htmlFor="nm-date">
            {t('FicheMonumentSections.dateProtection')}{' '}
            <span className="opt">{t('FicheMonumentSections.facultatif')}</span>
          </label>
          <input
            className="txt"
            id="nm-date"
            type="date"
            value={fiche.dateProtection ?? ''}
            onChange={(e) => onChange({ dateProtection: e.target.value })}
          />
        </div>
        <div className="fld" hidden={!protectionApplicable(fiche)}>
          <label htmlFor="nm-detail">
            {t('FicheMonumentSections.detailProtection')}{' '}
            <span className="opt">{t('FicheMonumentSections.facultatif')}</span>
          </label>
          <input
            className="txt"
            id="nm-detail"
            value={fiche.typeProtection ?? ''}
            placeholder={t('FicheMonumentSections.detailPlaceholder')}
            autoComplete="off"
            onChange={(e) => onChange({ typeProtection: e.target.value })}
          />
        </div>
      </Section>

      <Section n={3} titre={t('FicheMonumentSections.sectionProprietaire')} remplie={s3}>
        <div className={fld('proprietaire')}>
          <span className="lb">
            {t('FicheMonumentSections.proprietaireType')}{' '}
            <span className="opt">{t('FicheMonumentSections.plusieursChoix')}</span>
          </span>
          <p className="why">
            {t('FicheMonumentSections.proprietaireAide')}
          </p>
          <MenuChoix
            label={t('FicheMonumentSections.proprietaireType')}
            placeholder={t('FicheMonumentSections.proprietairePlaceholder')}
            groupes={groupesProprietaire(fiche)}
            multiple
            recherche
            valeurs={proprietairesCoches(fiche)}
            onChange={(v) =>
              onChange({
                proprietaire: proprietairesCoches({ proprietaire: v as Monument['proprietaire'] }),
              })
            }
          />
        </div>
      </Section>
    </>
  );
}
