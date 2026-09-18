import { useEffect } from 'react';
import { useAuthStore } from '@/stores/useAuthStore';
import { useBillingStore } from '@/stores/useBillingStore';
import { contexteYbug, idProjetYbug, type YbugUser } from '@/lib/ybug';

declare global {
  interface Window {
    /** Lu par le widget à son démarrage — donc posé AVANT l'insertion du script. */
    ybug_settings?: { id: string; user?: YbugUser } & Record<string, unknown>;
    /** L'API du widget, disponible seulement une fois le script chargé. */
    Ybug?: { setUser?: (user: YbugUser) => void };
  }
}

const ID_SCRIPT = 'ybug-widget';

/**
 * Monte le bouton de retour Ybug et le tient au courant de qui l'utilise.
 *
 * Ne rend rien : le widget s'injecte lui-même dans la page. Posé à la racine
 * plutôt que dans une page, il suit le testeur partout — y compris sur la
 * connexion et les pages d'invitation, où se logent quelques-uns des bugs les
 * plus embêtants à raconter par écrit.
 *
 * Sans `VITE_YBUG_ID`, ce composant ne fait rien du tout (cf. `lib/ybug.ts`).
 */
export function YbugWidget() {
  const user = useAuthStore((s) => s.user);
  const plans = useBillingStore((s) => s.access?.plans);
  const id = idProjetYbug();
  // Clé de dépendance stable : `contexteYbug` rend un objet neuf à chaque
  // rendu, alors que son contenu ne change qu'à la connexion, à la déconnexion
  // ou quand les droits reviennent du serveur.
  const contexte = JSON.stringify(contexteYbug(user, plans));

  useEffect(() => {
    if (!id) return;
    const donnees = JSON.parse(contexte) as YbugUser;

    // Deux chemins pour la même donnée, parce que le script est asynchrone :
    // avant son chargement, `ybug_settings` est ce qu'il lira au démarrage ;
    // après, c'est `setUser` qui le met à jour. L'un prend le relais de
    // l'autre, et le premier rapport part identifié dans les deux cas.
    window.ybug_settings = { ...(window.ybug_settings ?? {}), id, user: donnees };
    window.Ybug?.setUser?.(donnees);

    if (document.getElementById(ID_SCRIPT)) return;
    const script = document.createElement('script');
    script.id = ID_SCRIPT;
    script.async = true;
    script.src = `https://widget.ybug.io/button/${id}.js`;
    document.head.appendChild(script);
    // Pas de nettoyage : le widget vit le temps de l'onglet. Le retirer au
    // démontage ferait clignoter le bouton au double montage de StrictMode, et
    // le remonter à chaque changement d'utilisateur perdrait un brouillon de
    // rapport en cours de saisie.
  }, [id, contexte]);

  return null;
}
