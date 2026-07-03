import type { ComponentType, SVGProps } from 'react';
import type { IconWeight } from '@phosphor-icons/react';

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'strokeWidth'> & {
  size?: number;
  strokeWidth?: number;
  /** Surcharge ponctuelle de la graisse (ex. `bold` pour un rendu net sur fond plein). */
  weight?: IconWeight;
};

export type IconComponent = ComponentType<IconProps>;
