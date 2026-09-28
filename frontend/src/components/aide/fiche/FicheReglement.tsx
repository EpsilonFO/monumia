import { useCallback, useEffect, useImperativeHandle, useState, type Ref } from 'react';
import { Ico, type NomIco } from './Ico';
import { signalerPoint } from './useFiche';
import { aplatir, type PointReglement, type Reglement, type Rubrique } from '@/lib/fiche-aide';

const RUBRIQUE: Record<Rubrique, { ico: NomIco; teinte: string }> = {
  criteres: { ico: 'coche', teinte: 't-green' },
  candidater: { ico: 'maison', teinte: 't-blue' },
  projet: { ico: 'document', teinte: 't-gold' },
  montant: { ico: 'montant', teinte: 't-orange' },
  dossier: { ico: 'depot', teinte: 't-blue' },
  apres: { ico: 'coche', teinte: 't-green' },
  autres: { ico: 'info', teinte: 't-sand' },
};

export interface FicheReglementHandle {
  /** Déplie le point (et ce qui le contient), le fait défiler et le signale. */
  ouvrirPoint: (id: string) => void;
}

interface Source {
  libelle: string;
  url: string;
  ico: NomIco;
}

const hote = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
};

export function FicheReglement({
  reglement,
  sources,
  ref,
}: {
  reglement: Reglement;
  sources: Source[];
  ref?: Ref<FicheReglementHandle>;
}) {
  // Ce qu'il faut déplier pour voir un point : lui et sa rubrique. Les
  // démarches n'y sont plus : elles vivent dans « Avant de déposer »
  // (FicheAvantDepot), qui porte leur ancre.
  const clesPour = useCallback(
    (id: string): string[] | null => {
      const rubrique = reglement.rubriques.find((r) => r.points.some((p) => p.id === id));
      if (!rubrique) return null;
      return [`p:${id}`, `th:${rubrique.cle}`];
    },
    [reglement],
  );

  const [requete, setRequete] = useState('');
  // Arriver par un lien copié (« #p-… ») ouvre le point dès le premier rendu.
  const [ouverts, setOuverts] = useState<Set<string>>(() => {
    const ancre = location.hash.startsWith('#p-') ? location.hash.slice(3) : null;
    return new Set((ancre && clesPour(ancre)) || []);
  });
  const [copie, setCopie] = useState<{ id: string; ok: boolean } | null>(null);

  const q = aplatir(requete.trim());
  const cherche = q.length > 0;
  const visible = (p: PointReglement) => !cherche || p.cherche.includes(q);

  const basculer = (cle: string, ouvert: boolean) =>
    setOuverts((s) => {
      if (s.has(cle) === ouvert) return s;
      const suite = new Set(s);
      if (ouvert) suite.add(cle);
      else suite.delete(cle);
      return suite;
    });

  const ouvrirPoint = useCallback(
    (id: string) => {
      const cles = clesPour(id);
      if (!cles) return;
      setRequete('');
      setOuverts((s) => new Set([...s, ...cles]));
      history.replaceState(null, '', `#p-${id}`);
      signalerPoint(id);
    },
    [clesPour],
  );
  useImperativeHandle(ref, () => ({ ouvrirPoint }), [ouvrirPoint]);

  // Le point d'un lien copié est déjà déplié (état initial) : il reste à y aller.
  useEffect(() => {
    if (location.hash.startsWith('#p-')) signalerPoint(location.hash.slice(3));
  }, []);

  const copier = (id: string) => {
    const url = `${location.origin}${location.pathname}#p-${id}`;
    history.replaceState(null, '', `#p-${id}`);
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject())
      .then(() => setCopie({ id, ok: true }))
      .catch(() => setCopie({ id, ok: false }));
  };

  const point = (p: PointReglement, filtrable = false) => (
    <details
      key={p.id}
      id={`p-${p.id}`}
      className="pt"
      hidden={filtrable && !visible(p)}
      open={ouverts.has(`p:${p.id}`)}
      onToggle={(e) => basculer(`p:${p.id}`, e.currentTarget.open)}
    >
      <summary>
        <span className="pn">{p.n}</span>
        <span className="ptt">{p.titre}</span>
        {p.pastille === 'verifier' && <span className="kb k-check">À vérifier</span>}
        {p.pastille === 'choix' && <span className="kb k-disc">Au choix du financeur</span>}
      </summary>
      <div className="pb">
        <p>{p.resume}</p>
        {p.derogation && <p className="derog">Une dérogation est possible.</p>}
        {p.quote && (
          <blockquote>
            <small>Texte officiel</small>« {p.quote} »
          </blockquote>
        )}
        <button type="button" className={`copy${copie?.id === p.id && copie.ok ? ' done' : ''}`} onClick={() => copier(p.id)}>
          {copie?.id === p.id ? (copie.ok ? 'Lien copié' : 'Lien dans la barre d’adresse') : 'Copier le lien de ce point'}
        </button>
      </div>
    </details>
  );

  // Les démarches sont dans « Avant de déposer » : sans rubrique ni source, rien à montrer ici.
  if (reglement.rubriques.length === 0 && !sources.length) return null;
  const { rubriques } = reglement;
  const trouves = rubriques.reduce((n, r) => n + r.points.filter(visible).length, 0);

  return (
    <section className="block reglement" id="reglement">
      <div className="reg-h">
        <span className="chip t-solid"><Ico nom="livre" /></span>
        <div>
          <h2>Le règlement complet</h2>
          <p>Pas besoin de tout lire : chaque point se consulte au besoin, par thème.</p>
        </div>
      </div>

      {rubriques.length > 0 && (
        <div className="reg-more">
          <div className="reg-more-h">
            <h3>Le règlement, par thème</h3>
            <label className="search">
              <Ico nom="loupe" />
              <input
                type="search"
                placeholder="Chercher un mot"
                aria-label="Chercher dans le règlement"
                value={requete}
                onChange={(e) => setRequete(e.target.value)}
              />
            </label>
          </div>
          {rubriques.map((r) => {
            const n = r.points.filter(visible).length;
            return (
              <details
                key={r.cle}
                className="theme"
                hidden={cherche && n === 0}
                open={cherche ? n > 0 : ouverts.has(`th:${r.cle}`)}
                onToggle={(e) => !cherche && basculer(`th:${r.cle}`, e.currentTarget.open)}
              >
                <summary>
                  <span className={`chip sm ${RUBRIQUE[r.cle].teinte}`}><Ico nom={RUBRIQUE[r.cle].ico} /></span>
                  <span className="th-t">
                    <b>{r.titre}</b>
                    <small>{r.points.map((p) => p.titre).join(' · ')}</small>
                  </span>
                  <span className="th-n">{r.points.length}</span>
                </summary>
                <div className="th-b">{r.points.map((p) => point(p, true))}</div>
              </details>
            );
          })}
          {cherche && trouves === 0 && <p className="empty">Aucun point ne contient ce mot.</p>}
        </div>
      )}

      {sources.length > 0 && (
        <details className="sources">
          <summary><Ico nom="fichier" />Textes officiels ({sources.length})</summary>
          {sources.map((s) => (
            <a key={s.url} href={s.url} target="_blank" rel="noopener noreferrer">
              <Ico nom={s.ico} />
              <span>{s.libelle}<small>{hote(s.url)}</small></span>
            </a>
          ))}
        </details>
      )}
    </section>
  );
}
