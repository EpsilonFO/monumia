import { isUnknownAnswer } from '@/components/project/wizard/unknownAnswer';
import type { QcmOption, QcmQuestion } from '@/types';

/**
 * Ordre d'affichage des options : les vraies réponses d'abord, les
 * échappatoires (« je ne sais pas ») en bas, sous forme de carte pointillée.
 * Sert aussi de parcours au clavier, pour que les flèches suivent ce qu'on voit.
 */
export function displayOrder(question: QcmQuestion): QcmOption[] {
  return [
    ...question.options.filter((o) => !isUnknownAnswer(o)),
    ...question.options.filter(isUnknownAnswer),
  ];
}

/**
 * Coche/décoche une case d'une question à choix multiple.
 *
 * Deux règles, et ni l'une ni l'autre n'est cosmétique : les réponses « je ne
 * sais pas » sont EXCLUSIVES des autres — cocher « pas encore décidé » ET
 * « association » n'aurait aucun sens — et la sélection est triée dans l'ordre
 * du moteur, pour que ce qui est persisté ne dépende pas de l'ordre des clics.
 *
 * Rend une liste vide quand on décoche la dernière case : l'appelant traduit
 * cela par « question passée » (clé effacée), pas par « aucune réponse ne
 * convient ».
 */
export function toggleMulti(
  question: QcmQuestion,
  current: string[],
  option: QcmOption,
): string[] {
  const optionOf = (id: string) => question.options.find((o) => o.id === id);
  let next: string[];
  if (current.includes(option.id)) {
    next = current.filter((id) => id !== option.id);
  } else if (isUnknownAnswer(option)) {
    next = [option.id];
  } else {
    const kept = current.filter((id) => {
      const o = optionOf(id);
      return o ? !isUnknownAnswer(o) : true;
    });
    next = [...kept, option.id];
  }
  const rang = (id: string) => question.options.findIndex((o) => o.id === id);
  return [...next].sort((a, b) => rang(a) - rang(b));
}

/**
 * Le pseudo-choix « Passer cette question » que le moteur ajoute à toute
 * question à choix simple. Le wizard le remplace par le lien « Je ne sais pas,
 * passer » de sa barre de navigation : même effet (le fait reste inconnu),
 * sans une carte de plus. Les « je ne sais pas » déclarés par l'ontologie
 * (`unknown: true`), eux, restent des réponses à part entière.
 */
export const PSEUDO_PASSER = 'skip';

/** Les réponses du wizard, dans l'ordre de l'écran et du clavier. */
export function reponsesAffichees(question: QcmQuestion): QcmOption[] {
  return displayOrder(question).filter((o) => o.id !== PSEUDO_PASSER);
}

/**
 * Les réponses cochées, hors pseudo-choix « passer » : une réponse `skip` déjà
 * enregistrée ne coche aucune carte, et ne vaut pas réponse donnée pour
 * « Continuer ».
 */
export function reponsesChoisies(value: string | string[] | undefined): string[] {
  const ids = Array.isArray(value) ? value : typeof value === 'string' ? [value] : [];
  return ids.filter((id) => id !== PSEUDO_PASSER);
}
