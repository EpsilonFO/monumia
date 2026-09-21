/**
 * Savoir, depuis la landing, si le visiteur est déjà connecté à l'application.
 *
 * monumia.fr et app.monumia.fr sont deux ORIGINES distinctes : le localStorage
 * de l'application est illisible ici, et son cookie de session (`monumia_refresh`,
 * httpOnly, posé sur app.monumia.fr) ne nous est ni envoyé ni lisible. À la
 * place, l'application dépose un cookie de PRÉSENCE sur le domaine parent
 * (`frontend/src/lib/session.ts`, `setSessionCookie`) : aucun token, un simple
 * drapeau, effacé à la déconnexion et à chaque refresh refusé.
 *
 * C'est donc une INDICATION, pas une preuve — et elle n'a rien à protéger :
 * elle ne change qu'un libellé et une destination, et l'application refera
 * l'authentification pour de vrai à l'arrivée. Un cookie resté là après
 * l'expiration de la session mène à l'écran de connexion, ce qui est
 * exactement ce qu'il fallait.
 *
 * En développement, l'application (port 3000) et la landing (port 3001)
 * partagent l'hôte `localhost` : les cookies ignorant le port, le drapeau se
 * lit tel quel.
 */

const COOKIE_SESSION = 'monumia_session';

export function sessionActive(): boolean {
  if (typeof document === 'undefined') return false;
  return document.cookie
    .split(';')
    .some((morceau) => {
      const [nom, ...valeur] = morceau.split('=');
      return nom.trim() === COOKIE_SESSION && valeur.join('=') === '1';
    });
}
