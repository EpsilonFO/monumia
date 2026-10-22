import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { IconInfo } from '@/components/icons';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface InfoBulleProps {
  /** Ce que le « i » annonce aux lecteurs d'écran (le titre de la section). */
  libelle: string;
  children: React.ReactNode;
}

/**
 * Petit « i » d'explication posé à côté d'un titre de section : le texte
 * apparaît au survol, et au clavier dès que le « i » prend le focus.
 *
 * L'ouverture est CONTRÔLÉE pour ajouter le clic à ce que Radix gère déjà
 * (survol et focus) : sur un écran tactile il n'y a pas de survol, et sans ce
 * clic l'explication serait réservée aux souris. Court délai avant apparition,
 * pour qu'un passage de souris vers un autre élément ne fasse pas clignoter la
 * bulle.
 */
export function InfoBulle({ libelle, children }: InfoBulleProps) {
  const { t } = useTranslation('shell');
  const [open, setOpen] = useState(false);

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip open={open} onOpenChange={setOpen}>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={t('InfoBulle.enSavoirPlus', { libelle })}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <IconInfo className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          align="start"
          sideOffset={6}
          className="max-w-80 text-[14.5px] font-normal leading-relaxed text-balance"
        >
          {children}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
