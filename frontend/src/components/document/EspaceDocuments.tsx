import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Picto } from '@/components/shared/ecrans/Picto';
import { PictoDoc, PictoDossierPlein, type NomPictoDoc } from '@/components/document/PictosDocuments';
import { CarteDocument, LigneDocument, type DocumentAfficheProps } from '@/components/document/LigneDocument';
import { TYPES_DOSSIERS, dossierLabel } from '@/lib/document-type-meta';
import type { TriDocuments, VueDocuments } from '@/lib/documents-espace';
import type { Document, DocumentType } from '@/types';
import './documents.css';

/*
 * Les briques de l'espace de fichiers de la maquette `monumia-documents.html`,
 * partagées par Mes documents et par les onglets Documents d'un monument et
 * d'un projet : recherche et affichage, dossiers, grille ou tableau, barre de
 * sélection, dépôt par glisser.
 */

/* ---- recherche + grille / liste ---- */

export function OutilsDocuments({
  recherche, onRecherche, vue, onVue, children,
}: {
  recherche: string;
  onRecherche: (q: string) => void;
  vue: VueDocuments;
  onVue: (v: VueDocuments) => void;
  /** Des boutons en plus, à droite (l'onglet d'un monument ou d'un projet). */
  children?: ReactNode;
}) {
  const { t } = useTranslation('documents');
  return (
    <div className="top">
      <label className="search">
        <span className="sr">{t('EspaceDocuments.rechercher')}</span>
        <Picto nom="loupe" />
        <input
          type="search"
          placeholder={t('EspaceDocuments.rechercher')}
          value={recherche}
          onChange={(e) => onRecherche(e.target.value)}
        />
      </label>
      <div className="views" role="group" aria-label={t('EspaceDocuments.affichage')}>
        <button type="button" aria-pressed={vue === 'grille'} aria-label={t('EspaceDocuments.grille')} title={t('EspaceDocuments.grille')} onClick={() => onVue('grille')}>
          <PictoDoc nom="grille" />
        </button>
        <button type="button" aria-pressed={vue === 'liste'} aria-label={t('EspaceDocuments.liste')} title={t('EspaceDocuments.liste')} onClick={() => onVue('liste')}>
          <PictoDoc nom="lignes" />
        </button>
      </div>
      {children}
    </div>
  );
}

/* ---- intertitre de section, avec le tri ---- */

export function BarreSection({ titre, tri, onTri, droite }: {
  titre: string;
  tri?: TriDocuments;
  onTri?: (t: TriDocuments) => void;
  /** À la place du tri (l'avancement des pièces demandées). */
  droite?: ReactNode;
}) {
  const { t } = useTranslation('documents');
  return (
    <div className="bar">
      <h3>{titre}</h3>
      {tri && onTri && (
        <button className="sort" type="button" onClick={() => onTri(tri === 'nom' ? 'date' : 'nom')}>
          <PictoDoc nom="trier" />{tri === 'nom' ? t('EspaceDocuments.trierParNom') : t('EspaceDocuments.plusRecents')}
        </button>
      )}
      {droite}
    </div>
  );
}

/* ---- dossiers ---- */

/**
 * Un dossier par type (maquette `.fold`), vide compris. On peut y glisser un
 * fichier de l'ordinateur : il s'y range (cf. useDepotGlisse, qui lit
 * `data-dossier` sous le pointeur ; `survole` le met en évidence).
 *
 * Sur téléphone, les dossiers vides (souvent 17 sur 20) se replient derrière un
 * bouton : on n'y glisse rien, et ils allongeaient la page de 1 000 px. Le
 * repli est en CSS (`.folders:not(.vides-ouverts) .fold.vide`), l'ordinateur
 * les garde tous.
 */
export function DossiersDocuments({ comptes, onOuvrir, survole }: {
  comptes: Partial<Record<DocumentType, number>>;
  onOuvrir: (t: DocumentType) => void;
  survole?: DocumentType | null;
}) {
  const { t } = useTranslation('documents');
  const [videsOuverts, setVidesOuverts] = useState(false);
  const nbVides = TYPES_DOSSIERS.filter((tp) => !comptes[tp]).length;

  return (
    <>
      <div className={videsOuverts ? 'folders vides-ouverts' : 'folders'} data-dossiers="">
        {TYPES_DOSSIERS.map((tp) => {
          const n = comptes[tp] ?? 0;
          return (
            <button
              key={tp}
              type="button"
              data-dossier={tp}
              className={`fold${n ? '' : ' vide'}${survole === tp ? ' drop' : ''}`}
              onClick={() => onOuvrir(tp)}
            >
              <PictoDossierPlein />
              <span><b>{dossierLabel(tp)}</b><small>{n ? t('commun.nbDocuments', { count: n }) : t('EspaceDocuments.vide')}</small></span>
            </button>
          );
        })}
      </div>
      {nbVides > 0 && (
        <button type="button" className="lnk voir-vides" aria-expanded={videsOuverts} onClick={() => setVidesOuverts((v) => !v)}>
          {videsOuverts ? t('EspaceDocuments.masquerVides') : t('EspaceDocuments.afficherVides', { nombre: nbVides })}
        </button>
      )}
    </>
  );
}

/* ---- la grille ou le tableau ---- */

export function FichiersDocuments({ documents, vue, proprietes }: {
  documents: Document[];
  vue: VueDocuments;
  /** Tout ce qu'une carte ou une ligne reçoit, document par document. */
  proprietes: (d: Document) => DocumentAfficheProps;
}) {
  const { t } = useTranslation('documents');
  if (vue === 'liste') {
    return (
      <div className="tablewrap">
        <table className="dtable">
          <thead>
            <tr>
              <th>{t('EspaceDocuments.colonneNom')}</th>
              <th>{t('EspaceDocuments.colonneDossier')}</th>
              <th>{t('EspaceDocuments.colonneAjoute')}</th>
              <th>{t('EspaceDocuments.colonneTaille')}</th>
              <th><span className="sr">{t('EspaceDocuments.colonneActions')}</span></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => <LigneDocument key={d.id} {...proprietes(d)} />)}
          </tbody>
        </table>
      </div>
    );
  }
  return (
    <div className="files">
      {documents.map((d) => <CarteDocument key={d.id} {...proprietes(d)} />)}
    </div>
  );
}

/** La grille pendant le premier chargement : les gabarits des cartes, en sable. */
export function FichiersSquelette() {
  const { t } = useTranslation('documents');
  return (
    <div className="files" aria-busy="true" aria-label={t('EspaceDocuments.chargement')}>
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="file sk-file">
          <span className="sk" style={{ height: 139, borderRadius: 0 }} />
          <div className="meta"><div><span className="sk" style={{ height: 14, width: '70%' }} /><span className="sk" style={{ height: 11, width: '45%', marginTop: 8 }} /></div></div>
        </div>
      ))}
    </div>
  );
}

/* ---- barre de sélection ---- */

export interface GesteSelection {
  label: string;
  picto: NomPictoDoc | 'telecharger';
  onClick: () => void;
}

export function BarreSelection({ nombre, gestes, onVider }: { nombre: number; gestes: GesteSelection[]; onVider: () => void }) {
  const { t } = useTranslation('documents');
  if (nombre === 0) return null;
  return (
    <div className="selbar" role="region" aria-label={t('EspaceDocuments.selection')}>
      <span>{t('EspaceDocuments.selectionnes', { count: nombre })}</span>
      {gestes.map((g) => (
        <button key={g.label} type="button" onClick={g.onClick}>
          {g.picto === 'telecharger' ? <Picto nom="telecharger" /> : <PictoDoc nom={g.picto} />}
          {g.label}
        </button>
      ))}
      <button type="button" aria-label={t('EspaceDocuments.annulerSelection')} onClick={onVider}><Picto nom="croix" /></button>
    </div>
  );
}

/* ---- bloc vide ---- */

export function VideDocuments({ titre, texte, action }: { titre: string; texte?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <b>{titre}</b>
      {texte && <p>{texte}</p>}
      {action}
    </div>
  );
}

/* ---- dépôt par glisser : le voile (le geste est dans useDepotGlisse) ---- */

export function VoileDepot({ actif, dossier }: { actif: boolean; dossier?: DocumentType | null }) {
  const { t } = useTranslation('documents');
  if (!actif) return null;
  return (
    <div className="dropover" aria-hidden="true">
      <div>
        <b>{dossier ? t('EspaceDocuments.deposezDans', { dossier: dossierLabel(dossier) }) : t('EspaceDocuments.deposezIci')}</b>
        <p>{dossier ? t('EspaceDocuments.rangesDansCeDossier') : t('EspaceDocuments.choisirEnsuite')}</p>
      </div>
    </div>
  );
}
