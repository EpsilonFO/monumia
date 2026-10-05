import { Picto, type NomPicto } from './Picto';

export interface Onglet<V extends string> {
  value: V;
  label: string;
  picto: NomPicto;
  /** `null` : pas de compteur (la fiche du monument). */
  count: number | null;
  /** Infobulle de l'onglet, quand son libellé ne dit pas à quoi il sert. */
  title?: string;
}

/**
 * Les onglets d'une page monument ou projet : une pilule blanche, l'onglet
 * actif en orange, un compteur par onglet (grisé à zéro). Ce ne sont que des
 * boutons : la page garde la main sur l'état (le `?tab=` de l'URL).
 */
export function Onglets<V extends string>({
  onglets,
  actif,
  onChange,
  label,
}: {
  onglets: Onglet<V>[];
  actif: V;
  onChange: (v: V) => void;
  label: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {onglets.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === actif}
          title={o.title}
          onClick={() => onChange(o.value)}
        >
          <Picto nom={o.picto} />
          <span className="lbl">{o.label}</span>
          {o.count !== null && <em className={o.count === 0 ? 'zero' : undefined}>{o.count}</em>}
        </button>
      ))}
    </div>
  );
}
