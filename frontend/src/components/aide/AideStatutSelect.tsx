import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type { AideSuivi, AideSuiviStatut, AideRefusMotif } from '@/types';
import {
  AIDE_SUIVI_STATUTS,
  AIDE_SUIVI_STATUT_LABELS,
  AIDE_REFUS_MOTIFS,
  AIDE_REFUS_MOTIF_LABELS,
} from '@/types';
import { suiviService } from '@/services/suivi.service';
import { AIDE_STATUT_STYLES } from './AideStatutBadge';
import { C } from '@/lib/brand';

interface Props {
  projetId: string;
  aideId: string;
  suivi?: AideSuivi;
}

interface SavePatch {
  statut?: AideSuiviStatut;
  montantObtenu?: number;
  motifRefusCode?: AideRefusMotif;
  motifRefusDetail?: string;
}

export function AideStatutSelect({ projetId, aideId, suivi }: Props) {
  const { t } = useTranslation('aide');
  const [saving, setSaving] = useState(false);
  const [montant, setMontant] = useState(suivi?.montantObtenu?.toString() ?? '');
  const [motif, setMotif] = useState<AideRefusMotif>(suivi?.motifRefusCode ?? 'autre');
  const [motifDetail, setMotifDetail] = useState(suivi?.motifRefusDetail ?? '');

  // Un dossier est toujours suivi : à défaut de suivi enregistré, il est « À faire ».
  const statut: AideSuiviStatut = suivi?.statut ?? 'a_faire';

  // PUT = upsert complet : on renvoie toujours les valeurs courantes fusionnées.
  async function save(patch: SavePatch) {
    const targetStatut = patch.statut ?? statut;
    setSaving(true);
    try {
      await suiviService.upsert(projetId, aideId, {
        statut: targetStatut,
        montantObtenu: patch.montantObtenu ?? suivi?.montantObtenu,
        motifRefusCode: patch.motifRefusCode ?? suivi?.motifRefusCode,
        motifRefusDetail: patch.motifRefusDetail ?? suivi?.motifRefusDetail,
        note: suivi?.note,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('AideStatutSelect.erreurMiseAJour'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 text-[15px]">
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="font-semibold" style={{ color: C.ink }}>
          {t('AideStatutSelect.avancement')}
        </span>
        <div className="relative inline-flex items-center">
          <select
            value={statut}
            disabled={saving}
            onChange={(e) => save({ statut: e.target.value as AideSuiviStatut })}
            className={`appearance-none rounded-lg pl-4 pr-10 py-2 text-[16px] font-semibold border cursor-pointer shadow-sm transition-shadow hover:shadow focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-60 ${AIDE_STATUT_STYLES[statut]}`}
          >
            {AIDE_SUIVI_STATUTS.map((s) => (
              <option key={s} value={s}>
                {AIDE_SUIVI_STATUT_LABELS[s]}
              </option>
            ))}
          </select>
          <ChevronDown
            className={`pointer-events-none absolute right-3 h-4 w-4 ${AIDE_STATUT_STYLES[statut].split(' ').find(c => c.startsWith('text-'))}`}
          />
        </div>
      </div>

      {statut === 'accorde' && (
        <div className="flex items-center gap-2">
          <label className="text-muted-foreground">{t('AideStatutSelect.montantObtenu')}</label>
          <input
            type="number"
            min="0"
            value={montant}
            disabled={saving}
            onChange={(e) => setMontant(e.target.value)}
            onBlur={() => save({ montantObtenu: montant === '' ? undefined : Number(montant) })}
            className="rounded-md border border-border px-2.5 py-1.5 w-36 focus:outline-none focus:ring-2 focus:ring-offset-1"
          />
        </div>
      )}

      {statut === 'refuse' && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <label className="text-muted-foreground">{t('AideStatutSelect.motifRefus')}</label>
            <select
              value={motif}
              disabled={saving}
              onChange={(e) => {
                const m = e.target.value as AideRefusMotif;
                setMotif(m);
                save({ motifRefusCode: m });
              }}
              className="rounded-md border border-border px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-offset-1"
            >
              {AIDE_REFUS_MOTIFS.map((m) => (
                <option key={m} value={m}>
                  {AIDE_REFUS_MOTIF_LABELS[m]}
                </option>
              ))}
            </select>
          </div>
          <input
            type="text"
            placeholder={t('AideStatutSelect.detailPlaceholder')}
            value={motifDetail}
            disabled={saving}
            onChange={(e) => setMotifDetail(e.target.value)}
            onBlur={() => save({ motifRefusDetail: motifDetail })}
            className="rounded-md border border-border px-2.5 py-1.5 w-full max-w-sm focus:outline-none focus:ring-2 focus:ring-offset-1"
          />
        </div>
      )}
    </div>
  );
}
