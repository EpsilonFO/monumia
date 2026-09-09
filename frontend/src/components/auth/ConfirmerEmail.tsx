import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { IconCourrier } from '@/components/icons';
import { authService } from '@/services/auth.service';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';

/** Ce qui doit se passer une fois l'adresse confirmée. Se transmet au lien de
 *  confirmation, côté serveur, pour que le retour ne perde pas le fil. */
export interface IntentionRetour {
  /** Parcours découverte : reprendre le brouillon (monument + projet). */
  reprise?: boolean;
  /** Jeton de l'invitation à rejoindre. */
  invitation?: string;
}

interface ConfirmerEmailProps {
  email: string;
  intention?: IntentionRetour;
  /** Ce qui a mené ici : une inscription, ou une connexion refusée faute de
   *  confirmation. Les deux disent la même chose, mais pas dans le même temps. */
  variante?: 'inscription' | 'connexion';
  /** Précision propre à l'appelant (le sort de l'invitation, par exemple). */
  children?: React.ReactNode;
}

/**
 * L'écran d'attente de confirmation d'email.
 *
 * Un écran et non un toast : à ce moment précis l'utilisateur n'a plus qu'une
 * chose à faire, aller dans sa boîte, et il doit pouvoir relire l'adresse qu'il
 * a tapée. Un message qui s'efface au bout de quatre secondes laisse quelqu'un
 * devant un formulaire vide, persuadé que son inscription a échoué.
 *
 * Tenu volontairement sobre : une seule carte, un seul accent de couleur, aucun
 * lien souligné. C'est un écran d'attente, pas un carrefour — chaque mot mis en
 * valeur y ferait chercher une action qui n'existe pas.
 *
 * Le renvoi est le seul chemin de sortie quand le premier message se perd :
 * l'adresse est prise, donc l'inscription répond 409 et la connexion 403. Sans
 * ce bouton, le compte est mort et le support est le seul recours.
 */
export function ConfirmerEmail({
  email,
  intention,
  variante = 'inscription',
  children,
}: ConfirmerEmailProps) {
  const [renvoi, setRenvoi] = useState<'idle' | 'envoi' | 'envoye'>('idle');

  const renvoyer = async () => {
    setRenvoi('envoi');
    try {
      await authService.resendConfirmation(email, intention);
      setRenvoi('envoye');
    } catch (err: unknown) {
      // Le back répond 200 même quand rien n'est en attente ; n'arrive ici que
      // la limite de fréquence de Supabase, ou une panne réseau.
      setRenvoi('idle');
      toast.error(
        err instanceof Error ? err.message : "L'email n'a pas pu être renvoyé, réessayez.",
      );
    }
  };

  return (
    <div className="space-y-5">
      <div
        className="rounded-2xl border px-6 py-7 text-center"
        style={{ background: C.card, borderColor: C.border }}
      >
        <div
          className="mx-auto flex h-12 w-12 items-center justify-center rounded-full"
          style={{ background: C.paleBlue }}
        >
          <IconCourrier className="h-6 w-6" style={{ color: C.blue }} />
        </div>
        <h2
          className="mt-4 text-[22px] leading-[1.2]"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          Vérifiez votre boîte mail
        </h2>
        <p className="mt-2.5 text-[14px] leading-[1.6]" style={{ color: C.grayFg }}>
          {variante === 'inscription'
            ? 'Votre compte est créé. Un lien de confirmation vient de partir vers'
            : 'Votre adresse n’est pas encore confirmée. Un lien vient de partir vers'}
        </p>
        <p className="mt-1 text-[15px] font-semibold break-all" style={{ color: C.ink }}>
          {email}
        </p>
        <p className="mt-3 text-[14px] leading-[1.6]" style={{ color: C.grayFg }}>
          Ouvrez-le pour activer votre compte : vous serez connecté directement.
        </p>
      </div>

      {renvoi === 'envoye' ? (
        <p className="text-center text-[13.5px]" style={{ color: C.grayFg }}>
          Un nouvel email vient de partir. Il peut mettre quelques minutes à arriver.
        </p>
      ) : (
        <div className="space-y-2.5">
          <p className="text-center text-[13.5px]" style={{ color: C.grayMuted }}>
            Rien reçu ? Pensez à regarder dans les indésirables.
          </p>
          <button
            type="button"
            onClick={renvoyer}
            disabled={renvoi === 'envoi'}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-lg border text-[14px] font-semibold transition-colors hover:bg-secondary disabled:opacity-60"
            style={{ borderColor: C.border, color: C.ink, background: C.card }}
          >
            {renvoi === 'envoi' && <Loader2 className="h-4 w-4 animate-spin" />}
            Renvoyer l’email
          </button>
        </div>
      )}

      {children}
    </div>
  );
}
