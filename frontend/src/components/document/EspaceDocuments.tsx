import { useState, type ReactNode } from 'react';
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

const plur = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;


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
  return (
    <div className="top">
      <label className="search">
        <span className="sr">Rechercher dans vos documents</span>
        <Picto nom="loupe" />
        <input
          type="search"
          placeholder="Rechercher dans vos documents"
          value={recherche}
          onChange={(e) => onRecherche(e.target.value)}
        />
      </label>
      <div className="views" role="group" aria-label="Affichage">
        <button type="button" aria-pressed={vue === 'grille'} aria-label="Grille" title="Grille" onClick={() => onVue('grille')}>
          <PictoDoc nom="grille" />
        </button>
        <button type="button" aria-pressed={vue === 'liste'} aria-label="Liste" title="Liste" onClick={() => onVue('liste')}>
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
  return (
    <div className="bar">
      <h3>{titre}</h3>
      {tri && onTri && (
        <button className="sort" type="button" onClick={() => onTri(tri === 'nom' ? 'date' : 'nom')}>
          <PictoDoc nom="trier" />{tri === 'nom' ? 'Trier par nom' : "Les plus récents d'abord"}
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
  const [videsOuverts, setVidesOuverts] = useState(false);
  const nbVides = TYPES_DOSSIERS.filter((t) => !comptes[t]).length;

  return (
    <>
      <div className={videsOuverts ? 'folders vides-ouverts' : 'folders'} data-dossiers="">
        {TYPES_DOSSIERS.map((t) => {
          const n = comptes[t] ?? 0;
          return (
            <button
              key={t}
              type="button"
              data-dossier={t}
              className={`fold${n ? '' : ' vide'}${survole === t ? ' drop' : ''}`}
              onClick={() => onOuvrir(t)}
            >
              <PictoDossierPlein />
              <span><b>{dossierLabel(t)}</b><small>{n ? plur(n, 'document') : 'Vide'}</small></span>
            </button>
          );
        })}
      </div>
      {nbVides > 0 && (
        <button type="button" className="lnk voir-vides" aria-expanded={videsOuverts} onClick={() => setVidesOuverts((v) => !v)}>
          {videsOuverts ? 'Masquer les dossiers vides' : `Afficher les dossiers vides (${nbVides})`}
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
  if (vue === 'liste') {
    return (
      <div className="tablewrap">
        <table className="dtable">
          <thead>
            <tr><th>Nom</th><th>Dossier</th><th>Ajouté le</th><th>Taille</th><th><span className="sr">Actions</span></th></tr>
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
  return (
    <div className="files" aria-busy="true" aria-label="Chargement des documents">
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
  if (nombre === 0) return null;
  return (
    <div className="selbar" role="region" aria-label="Sélection">
      <span>{nombre} sélectionné{nombre > 1 ? 's' : ''}</span>
      {gestes.map((g) => (
        <button key={g.label} type="button" onClick={g.onClick}>
          {g.picto === 'telecharger' ? <Picto nom="telecharger" /> : <PictoDoc nom={g.picto} />}
          {g.label}
        </button>
      ))}
      <button type="button" aria-label="Annuler la sélection" onClick={onVider}><Picto nom="croix" /></button>
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
  if (!actif) return null;
  return (
    <div className="dropover" aria-hidden="true">
      <div>
        <b>{dossier ? `Déposez dans « ${dossierLabel(dossier)} »` : 'Déposez vos fichiers ici'}</b>
        <p>{dossier ? 'Ils seront rangés dans ce dossier.' : 'Vous choisirez ensuite le dossier.'}</p>
      </div>
    </div>
  );
}
