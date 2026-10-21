import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { C, SERIF } from '@/lib/brand';
import { dateLongue } from '@/lib/fiche-aide';
import type { AideFermee } from '@/types';

interface AideFermeeDialogProps {
  fermee: AideFermee;
  open: boolean;
  /** Le panneau est lu (bouton, Échap, clic hors du panneau). */
  onCompris: () => void;
}

/**
 * L'explication d'une aide qui a quitté le catalogue alors que l'utilisateur
 * y travaillait. Deux cas :
 *
 * - dossier en préparation : il ne pourra pas être déposé, et il disparaît
 *   du projet une fois le panneau fermé (l'appelant s'en charge) ;
 * - demande déjà déposée : elle suit son cours, rien ne disparaît.
 *
 * « N'est plus proposée » et pas « close » : le guichet `clos` de la fiche dit
 * une session terminée qui rouvrira, ce n'est pas le même message.
 */
export function AideFermeeDialog({ fermee, open, onCompris }: AideFermeeDialogProps) {
  const { t } = useTranslation('aide');
  return (
    <Dialog open={open} onOpenChange={(ouvert) => !ouvert && onCompris()}>
      <DialogContent
        showCloseButton={false}
        className="gap-0 rounded-2xl border-[1.5px] p-8 sm:max-w-[34rem]"
        style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-pop)' }}
      >
        <p className="text-[15px] font-semibold" style={{ color: C.orange }}>
          {fermee.nom}
        </p>
        <DialogTitle
          className="mt-2 text-[27px] leading-tight font-normal"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          {t('AideFermeeDialog.titre')}
        </DialogTitle>
        <DialogDescription asChild>
          <div className="mt-4 space-y-3 text-[16.5px] leading-[1.7]" style={{ color: C.grayFg }}>
            <p>
              {fermee.fermeeLe
                ? t('AideFermeeDialog.retireeDepuis', { date: dateLongue(fermee.fermeeLe) })
                : t('AideFermeeDialog.retiree')}
            </p>
            {fermee.deposee ? (
              <p>{t('AideFermeeDialog.deposee')}</p>
            ) : (
              <p>{t('AideFermeeDialog.enPreparation')}</p>
            )}
          </div>
        </DialogDescription>
        <button
          type="button"
          onClick={onCompris}
          className="mt-7 w-full rounded-full px-5 py-3 text-[16.5px] font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5"
          style={{ background: C.orange }}
        >
          {t('AideFermeeDialog.compris')}
        </button>
      </DialogContent>
    </Dialog>
  );
}
