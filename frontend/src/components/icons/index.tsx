import type { ComponentType, ReactNode, SVGProps } from 'react';

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'strokeWidth'> & {
  size?: number;
  strokeWidth?: number;
};

/** Type d'un composant de la banque — à réutiliser partout où une icône est passée en prop. */
export type IconComponent = ComponentType<IconProps>;

type IconBaseProps = IconProps & { children: ReactNode };

/**
 * Banque d'icônes Monumia — DA « fait main ».
 *
 * Deux bases, un seul langage visuel (line-art arrondi, motif « écho ») :
 *  - IconBaseFilled : pour les 3 SVG fournis par le fondateur (contours remplis,
 *    evenodd), icônes vedettes au tracé organique.
 *  - IconBaseStroke : pour toutes les icônes dessinées (centerlines, trait
 *    uniforme arrondi). Épaisseur calée pour s'accorder aux vedettes.
 *
 * Toutes utilisent currentColor → elles épousent les tokens de thème.
 * Pour changer une icône partout : éditer son tracé ici, une seule fois.
 */

function IconBaseFilled({ size = 20, children, ...props }: IconBaseProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="currentColor" aria-hidden {...props}>
      {children}
    </svg>
  );
}

function IconBaseStroke({ size = 20, children, ...props }: IconBaseProps) {
  // NB : on impose un trait gras calibré pour le viewBox 100 et on IGNORE tout
  // `strokeWidth` hérité (les appels historiques passaient des valeurs ~1.8
  // calibrées pour l'ancien viewBox 24 → quasi invisibles ici). strokeWidth
  // est donc placé APRÈS {...props} pour écraser toute valeur entrante.
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
      strokeWidth={8.5}
    >
      {children}
    </svg>
  );
}

/* ================================================================== */
/* Icônes vedettes — SVG fournis (rempli)                              */
/* ================================================================== */

/** 🔔 Notifications. */
export function IconNotification(p: IconProps) {
  return (
    <IconBaseFilled {...p}>
      <path fillRule="evenodd" clipRule="evenodd" d="M 46.216 8.186 L 43.486 8.558 L 40.756 9.303 L 38.771 10.171 L 35.793 12.032 L 32.071 15.507 L 29.838 18.857 L 28.225 22.827 L 27.728 25.061 L 27.604 26.922 L 27.356 27.418 L 24.626 27.666 L 22.269 28.287 L 20.160 29.155 L 16.809 31.140 L 13.832 33.746 L 11.102 37.344 L 9.241 41.191 L 8.248 45.037 L 8.000 49.380 L 8.620 53.846 L 9.985 58.561 L 12.095 62.780 L 13.335 64.517 L 15.196 66.502 L 17.306 68.239 L 21.152 70.473 L 24.006 71.465 L 27.480 72.210 L 29.465 78.041 L 31.451 81.516 L 33.808 84.369 L 37.778 87.595 L 42.245 90.077 L 44.355 90.821 L 46.960 91.442 L 50.931 91.690 L 54.157 91.318 L 57.383 90.325 L 59.864 89.084 L 62.842 87.099 L 66.316 83.873 L 69.046 80.399 L 70.659 77.049 L 71.651 72.830 L 71.900 72.582 L 74.009 72.210 L 76.366 71.465 L 79.592 69.976 L 82.198 68.363 L 84.059 66.874 L 86.789 64.145 L 89.022 61.043 L 90.759 57.072 L 91.876 51.613 L 91.876 47.643 L 91.131 43.548 L 90.511 41.563 L 89.518 39.329 L 87.781 36.848 L 85.300 34.242 L 80.585 30.644 L 77.855 29.155 L 75.126 28.038 L 73.885 27.790 L 73.140 27.294 L 72.272 23.448 L 70.659 19.601 L 68.425 16.375 L 65.820 13.770 L 62.222 11.288 L 59.988 10.171 L 56.762 9.055 L 52.047 8.310 L 50.558 8.434 L 49.442 8.186 Z M 17.058 65.758 L 17.678 65.634 L 20.408 67.123 L 24.006 68.363 L 26.984 68.736 L 27.232 69.232 L 27.232 70.597 L 26.612 70.721 L 24.378 70.225 L 20.780 68.860 L 17.058 66.254 Z M 85.176 35.979 L 87.781 39.081 L 89.146 41.687 L 90.139 44.913 L 90.635 48.759 L 90.263 53.722 L 89.146 57.693 L 87.781 60.547 L 85.672 63.400 L 81.950 66.874 L 78.476 69.108 L 74.381 70.721 L 70.907 71.589 L 70.287 72.706 L 69.170 77.297 L 67.309 80.647 L 63.586 84.742 L 60.609 87.099 L 58.375 88.464 L 54.281 89.953 L 52.419 90.325 L 49.690 90.449 L 44.727 89.581 L 40.632 87.843 L 40.508 87.223 L 41.253 87.099 L 45.719 88.340 L 50.931 88.340 L 54.777 87.347 L 58.251 85.610 L 61.353 83.377 L 63.835 80.895 L 65.199 79.034 L 67.185 75.188 L 68.053 72.458 L 68.425 69.728 L 68.674 69.356 L 73.016 68.612 L 75.994 67.495 L 79.965 65.013 L 82.818 62.284 L 84.679 59.802 L 86.292 56.824 L 87.409 53.598 L 88.030 50.496 L 88.030 46.402 L 87.781 44.541 L 86.168 39.453 L 84.555 36.600 L 84.555 36.103 Z M 62.470 13.273 L 63.338 13.521 L 65.944 15.631 L 67.929 17.864 L 69.294 19.849 L 71.031 23.696 L 71.900 27.542 L 71.775 28.162 L 69.294 28.038 L 68.922 27.790 L 68.425 24.192 L 67.309 20.842 L 65.448 17.492 L 63.835 15.383 L 62.346 13.894 Z M 45.719 10.171 L 49.194 10.171 L 53.040 10.916 L 56.638 12.405 L 60.360 15.010 L 63.338 18.236 L 65.696 22.331 L 66.564 24.936 L 67.433 29.403 L 67.805 29.775 L 68.674 30.024 L 71.155 30.272 L 73.513 30.892 L 76.614 32.257 L 79.592 34.242 L 82.198 36.848 L 83.935 39.453 L 84.804 41.439 L 85.672 44.541 L 86.044 47.767 L 85.796 51.117 L 85.052 54.219 L 83.439 57.817 L 81.081 61.043 L 77.979 63.897 L 74.133 66.130 L 70.783 67.247 L 67.061 67.867 L 66.440 68.860 L 66.068 71.589 L 64.951 75.064 L 63.338 78.041 L 61.477 80.399 L 59.120 82.508 L 56.514 84.245 L 53.536 85.610 L 49.442 86.479 L 46.464 86.355 L 41.997 85.238 L 39.267 83.997 L 35.793 81.640 L 33.436 79.282 L 31.326 76.304 L 29.589 72.210 L 28.473 67.123 L 27.852 66.750 L 24.750 66.378 L 21.648 65.386 L 18.919 64.021 L 16.065 62.035 L 14.080 60.050 L 12.095 57.072 L 10.730 53.722 L 10.109 50.248 L 10.109 46.774 L 10.854 42.928 L 12.591 38.957 L 14.576 36.103 L 17.554 33.250 L 20.408 31.388 L 24.130 29.775 L 28.721 28.907 L 29.465 27.914 L 29.713 25.557 L 30.582 22.207 L 32.071 19.229 L 34.304 16.251 L 36.662 14.018 L 39.391 12.157 L 41.873 11.040 Z M 46.340 15.010 L 43.982 15.507 L 40.880 16.747 L 38.027 18.857 L 35.793 21.586 L 34.304 24.688 L 33.684 27.294 L 33.560 29.900 L 33.808 31.885 L 34.428 33.870 L 34.304 34.614 L 29.962 33.746 L 26.239 33.994 L 24.130 34.614 L 22.269 35.483 L 20.160 36.848 L 18.671 38.213 L 16.809 40.570 L 15.941 42.183 L 15.072 44.541 L 14.700 46.774 L 14.700 49.504 L 15.321 52.730 L 16.934 56.080 L 18.050 57.569 L 19.787 59.306 L 21.524 60.547 L 23.758 61.663 L 26.115 62.408 L 27.852 62.656 L 30.582 62.656 L 32.443 62.284 L 33.932 61.663 L 34.552 61.787 L 33.684 65.137 L 33.560 66.626 L 33.932 70.597 L 34.677 72.830 L 35.793 74.939 L 37.034 76.677 L 38.523 78.165 L 41.004 79.903 L 43.982 81.143 L 46.588 81.640 L 49.442 81.640 L 51.675 81.267 L 54.777 80.027 L 58.003 77.669 L 59.988 75.312 L 61.477 72.334 L 62.346 68.736 L 62.346 65.758 L 61.601 62.780 L 61.725 62.035 L 62.470 62.035 L 63.710 62.532 L 65.820 62.904 L 68.549 62.904 L 70.162 62.656 L 73.761 61.291 L 75.994 59.802 L 77.359 58.561 L 79.592 55.583 L 80.585 53.350 L 81.329 50.000 L 81.329 46.774 L 80.957 44.913 L 79.468 41.191 L 77.359 38.461 L 74.257 35.979 L 70.783 34.490 L 67.929 33.994 L 64.951 34.118 L 62.097 34.987 L 61.353 34.863 L 62.346 30.768 L 62.346 27.914 L 61.973 25.805 L 61.229 23.696 L 60.112 21.586 L 57.631 18.609 L 55.273 16.871 L 51.675 15.383 L 49.690 15.010 Z M 36.910 61.787 L 37.406 61.787 L 38.647 63.028 L 38.647 63.897 L 37.903 66.750 L 37.903 69.976 L 38.399 72.458 L 39.143 74.319 L 39.019 74.939 L 38.523 74.939 L 37.034 72.706 L 35.793 68.860 L 35.793 65.137 L 36.165 63.524 Z M 61.353 37.468 L 63.338 36.724 L 65.820 36.227 L 68.301 36.227 L 71.651 37.096 L 74.629 38.957 L 76.614 40.942 L 77.731 42.555 L 77.731 43.052 L 77.111 43.176 L 75.994 42.059 L 73.885 40.570 L 70.038 39.081 L 66.564 38.833 L 62.842 39.453 L 61.353 37.965 Z M 34.056 36.724 L 34.056 37.468 L 30.706 37.716 L 29.217 38.089 L 26.612 39.205 L 24.130 40.942 L 22.517 42.679 L 20.532 46.030 L 19.787 48.387 L 19.539 52.606 L 20.035 55.583 L 19.415 55.708 L 18.422 54.343 L 17.182 51.365 L 16.809 49.380 L 16.809 47.270 L 17.182 45.161 L 17.802 43.424 L 19.663 40.446 L 21.152 38.957 L 23.137 37.468 L 26.363 36.103 L 27.480 35.855 L 30.830 35.855 Z M 52.419 21.586 L 54.653 22.083 L 56.886 23.075 L 59.120 24.688 L 59.616 25.557 L 60.236 28.162 L 60.236 31.264 L 59.616 33.746 L 58.375 36.476 L 58.623 37.716 L 62.097 41.066 L 62.594 41.315 L 65.323 40.694 L 68.549 40.694 L 71.155 41.315 L 74.009 42.804 L 76.366 45.037 L 77.235 46.278 L 78.352 48.759 L 78.848 51.489 L 78.227 53.350 L 76.490 56.204 L 74.133 58.437 L 71.279 60.050 L 68.674 60.795 L 65.199 60.795 L 63.835 60.547 L 59.988 59.058 L 58.996 59.306 L 58.623 60.422 L 59.864 64.145 L 60.236 66.502 L 60.236 68.115 L 59.616 71.093 L 58.375 73.823 L 56.018 76.552 L 53.412 78.290 L 50.062 79.406 L 46.712 79.530 L 45.471 79.034 L 43.486 77.669 L 41.501 75.436 L 40.384 73.451 L 39.516 70.721 L 39.391 67.371 L 39.640 65.634 L 40.508 63.152 L 40.384 62.656 L 38.275 60.422 L 37.406 59.058 L 36.786 58.685 L 36.165 58.685 L 33.560 59.802 L 30.210 60.547 L 27.232 60.422 L 23.882 59.306 L 22.145 56.204 L 21.648 54.715 L 21.276 52.730 L 21.276 50.000 L 21.897 47.394 L 23.261 44.665 L 25.867 41.811 L 27.108 40.942 L 29.093 39.950 L 32.071 39.205 L 34.925 39.205 L 36.786 39.578 L 39.143 40.570 L 40.136 40.446 L 40.384 39.578 L 39.143 36.600 L 38.771 32.753 L 39.143 30.520 L 40.632 27.170 L 43.362 24.192 L 45.719 22.703 L 48.821 21.710 Z M 55.645 19.849 L 55.521 20.470 L 52.295 19.849 L 49.318 19.849 L 47.829 20.097 L 45.223 20.966 L 42.866 22.331 L 40.632 24.316 L 39.143 26.301 L 37.654 29.775 L 37.158 33.622 L 36.414 33.622 L 35.669 29.651 L 36.165 26.053 L 36.786 24.316 L 37.903 22.331 L 40.880 19.353 L 44.355 17.616 L 46.588 17.120 L 48.573 16.996 L 51.179 17.492 L 52.916 18.112 Z" />
    </IconBaseFilled>
  );
}

/** ⬇️ Télécharger / exporter. */
export function IconTelecharger(p: IconProps) {
  return (
    <IconBaseFilled {...p}>
      <path fillRule="evenodd" clipRule="evenodd" d="M 9.226 71.082 L 8.899 78.926 L 9.389 82.358 L 10.370 84.482 L 12.167 87.261 L 14.292 89.222 L 16.416 90.529 L 19.685 91.510 L 39.296 91.837 L 52.533 91.019 L 75.576 91.346 L 80.969 90.856 L 85.381 90.039 L 88.323 87.914 L 89.957 84.809 L 90.774 80.560 L 90.774 75.004 L 89.794 71.735 L 86.525 68.630 L 84.401 67.486 L 83.093 67.160 L 80.479 67.160 L 79.171 67.813 L 77.864 69.121 L 77.047 71.572 L 76.720 76.802 L 76.230 77.128 L 51.226 77.128 L 44.852 77.455 L 24.261 77.619 L 23.117 77.292 L 22.790 72.553 L 21.973 70.428 L 20.175 68.630 L 18.704 67.650 L 16.580 66.996 L 12.984 67.160 L 11.840 67.486 L 9.879 69.121 Z M 89.467 79.743 L 88.323 84.973 L 87.342 86.770 L 86.035 88.078 L 84.564 88.732 L 82.276 89.222 L 73.778 90.039 L 56.455 89.549 L 43.872 90.039 L 38.805 90.529 L 20.992 90.366 L 18.051 89.712 L 15.599 88.405 L 15.763 87.588 L 18.868 87.914 L 34.066 87.914 L 46.977 87.588 L 76.556 87.588 L 80.479 87.261 L 83.093 86.444 L 85.054 84.809 L 86.035 83.012 L 87.016 77.782 L 86.852 71.245 L 87.506 71.245 L 89.140 73.696 Z M 18.704 69.774 L 19.685 69.938 L 21.156 71.899 L 21.646 75.004 L 21.482 77.292 L 19.848 77.292 L 19.195 76.965 L 19.031 72.553 L 18.541 70.591 Z M 84.728 74.350 L 84.564 79.580 L 84.074 81.868 L 83.420 83.175 L 81.459 84.646 L 77.700 85.136 L 18.704 85.626 L 15.109 85.136 L 13.311 84.319 L 12.004 82.848 L 11.187 79.416 L 11.350 71.409 L 11.677 70.428 L 12.984 69.447 L 15.109 69.447 L 16.089 70.101 L 16.743 72.553 L 17.070 77.782 L 18.377 79.253 L 20.502 79.743 L 34.066 79.907 L 41.257 79.580 L 76.883 79.253 L 78.191 78.763 L 78.844 77.946 L 79.335 71.245 L 80.315 69.774 L 81.459 69.284 L 82.767 69.447 L 83.911 70.428 Z M 47.630 8.000 L 45.506 8.327 L 44.198 8.981 L 42.728 10.615 L 41.747 13.720 L 41.420 16.825 L 41.420 27.611 L 41.911 40.848 L 41.747 48.856 L 40.767 49.019 L 35.047 43.463 L 33.086 42.319 L 31.615 41.992 L 29.654 42.319 L 27.366 44.117 L 26.385 45.914 L 26.385 48.366 L 26.875 49.673 L 28.346 51.634 L 40.113 63.237 L 45.016 68.630 L 46.486 69.774 L 48.774 70.918 L 49.918 71.245 L 52.206 71.245 L 55.148 69.611 L 65.280 59.315 L 69.202 55.720 L 71.654 52.451 L 72.307 51.144 L 72.798 49.019 L 72.307 46.568 L 71.327 44.934 L 69.529 43.300 L 66.424 41.829 L 63.482 41.829 L 62.339 42.156 L 60.214 43.463 L 58.580 45.097 L 57.763 44.934 L 57.599 34.311 L 57.926 20.420 L 57.272 14.864 L 56.128 12.249 L 53.350 9.634 L 49.918 8.163 Z M 70.019 45.588 L 71.163 47.222 L 71.327 49.673 L 70.510 51.634 L 69.039 53.759 L 53.350 69.284 L 51.879 69.938 L 49.591 69.774 L 49.428 68.957 L 52.043 67.160 L 57.436 61.276 L 67.568 51.307 L 69.202 48.366 L 69.202 45.751 Z M 54.167 12.739 L 54.984 12.903 L 55.965 14.864 L 56.619 20.257 L 56.292 32.840 L 56.292 43.300 L 56.619 47.058 L 54.984 48.693 L 54.331 48.693 L 54.004 47.712 L 54.004 32.514 L 54.331 24.669 Z M 46.977 10.288 L 48.938 10.288 L 50.409 10.778 L 51.389 11.759 L 51.716 12.576 L 52.206 15.518 L 52.206 24.506 L 51.716 37.089 L 51.879 51.307 L 52.206 52.615 L 53.187 53.268 L 54.004 52.942 L 59.724 46.895 L 62.829 44.444 L 64.790 44.117 L 65.934 44.770 L 66.914 46.241 L 66.751 48.202 L 64.790 50.981 L 53.840 61.767 L 50.735 65.198 L 48.611 66.669 L 47.140 66.669 L 45.506 65.525 L 30.634 50.817 L 28.673 47.875 L 28.673 46.405 L 29.327 45.261 L 30.798 44.280 L 31.942 44.280 L 34.066 45.424 L 41.584 52.778 L 42.891 53.105 L 43.708 51.961 L 44.198 43.790 L 43.545 25.323 L 43.708 15.681 L 44.525 12.086 L 45.669 10.778 Z" />
    </IconBaseFilled>
  );
}

/** ⚙️ Réglages / paramètres. */
export function IconReglages(p: IconProps) {
  return (
    <IconBaseFilled {...p}>
      <path fillRule="evenodd" clipRule="evenodd" d="M 48.391 8.111 L 46.172 8.444 L 41.955 9.664 L 39.847 10.885 L 39.070 11.773 L 38.515 12.882 L 38.071 14.769 L 37.517 18.985 L 35.519 20.206 L 35.075 20.206 L 32.745 18.209 L 30.526 16.655 L 29.194 16.211 L 27.863 16.211 L 23.535 17.210 L 21.427 18.431 L 17.654 22.314 L 15.435 25.089 L 14.769 26.642 L 14.658 27.752 L 14.769 28.639 L 15.546 30.415 L 18.985 34.853 L 18.985 35.741 L 18.098 37.738 L 17.432 40.069 L 17.099 40.513 L 11.995 41.622 L 9.997 42.621 L 8.999 43.731 L 8.555 44.729 L 8.222 47.392 L 8.222 53.273 L 8.666 55.604 L 9.886 57.379 L 11.995 58.489 L 16.766 59.487 L 17.432 60.042 L 17.765 61.596 L 19.207 64.703 L 19.318 65.590 L 18.542 67.033 L 16.100 70.473 L 15.546 72.137 L 15.546 73.469 L 16.211 75.244 L 17.321 76.687 L 22.314 81.902 L 24.645 83.345 L 25.865 83.678 L 27.641 83.678 L 28.861 83.345 L 30.970 82.346 L 34.188 79.794 L 34.742 79.794 L 35.630 80.460 L 37.960 81.569 L 38.626 82.235 L 39.403 86.785 L 40.402 88.560 L 41.733 89.781 L 43.065 90.446 L 47.170 91.667 L 49.279 91.889 L 54.050 91.889 L 56.602 91.445 L 57.934 90.668 L 58.600 89.892 L 59.598 87.007 L 60.042 82.457 L 60.264 81.680 L 60.819 80.904 L 63.593 79.905 L 65.590 78.795 L 66.700 78.684 L 71.694 82.790 L 73.247 83.456 L 75.133 83.456 L 76.243 83.012 L 77.353 82.235 L 82.679 76.798 L 83.345 75.799 L 83.789 74.579 L 83.789 72.914 L 82.901 70.695 L 79.461 65.701 L 79.683 64.370 L 80.904 61.818 L 81.569 59.598 L 82.013 59.155 L 88.005 58.267 L 90.114 57.268 L 91.001 56.159 L 91.445 55.049 L 91.778 52.941 L 91.778 47.059 L 91.223 44.285 L 90.668 43.287 L 89.892 42.510 L 88.116 41.733 L 82.235 40.845 L 81.458 39.958 L 80.682 37.406 L 79.794 35.519 L 79.683 34.077 L 83.900 28.750 L 84.565 27.419 L 84.787 25.421 L 84.565 24.423 L 83.234 22.314 L 78.795 17.765 L 77.020 16.433 L 75.466 15.768 L 70.584 15.546 L 69.363 15.768 L 67.477 16.544 L 64.037 19.207 L 63.371 19.540 L 62.705 19.540 L 60.930 18.764 L 60.486 18.320 L 59.376 11.440 L 58.711 9.997 L 57.712 8.999 L 56.048 8.333 L 54.494 8.111 Z M 39.625 80.127 L 41.511 80.682 L 42.399 81.680 L 43.176 87.450 L 43.065 88.227 L 42.621 88.227 L 42.177 87.894 L 41.178 86.563 L 40.734 85.009 L 40.291 81.902 L 39.514 80.682 Z M 19.096 58.933 L 20.650 59.044 L 21.205 59.487 L 22.203 62.594 L 23.313 65.147 L 23.313 65.701 L 22.869 66.589 L 19.873 70.362 L 19.096 72.026 L 18.985 73.691 L 19.318 74.801 L 20.095 76.021 L 19.984 76.576 L 19.540 76.576 L 18.320 75.244 L 17.321 73.358 L 17.321 72.248 L 17.654 71.139 L 20.650 66.811 L 20.983 65.923 L 20.983 64.481 L 19.429 61.041 L 18.985 59.598 Z M 11.773 43.509 L 12.439 43.620 L 11.773 48.391 L 11.884 53.384 L 12.439 55.826 L 12.328 56.491 L 11.662 56.491 L 10.441 55.271 L 10.108 54.050 L 9.886 51.720 L 9.886 47.614 L 10.108 45.839 L 10.663 44.396 Z M 19.096 23.313 L 19.651 23.424 L 19.651 23.868 L 18.875 25.421 L 18.875 26.975 L 19.207 27.974 L 20.206 29.749 L 23.313 34.077 L 23.091 35.408 L 22.314 36.851 L 21.205 40.291 L 20.095 40.956 L 19.318 40.956 L 19.207 40.180 L 20.761 35.963 L 20.761 34.520 L 20.095 33.300 L 17.210 29.749 L 16.544 28.306 L 16.544 26.975 L 16.877 26.198 Z M 71.472 17.432 L 71.472 17.876 L 67.810 20.983 L 67.366 21.205 L 66.367 21.205 L 65.480 20.761 L 65.480 20.317 L 68.476 17.987 L 69.918 17.432 Z M 43.176 11.329 L 43.287 11.884 L 42.288 18.209 L 41.733 18.875 L 40.180 19.540 L 39.403 19.651 L 39.292 18.985 L 39.625 17.543 L 39.736 15.435 L 40.180 13.659 L 41.178 12.106 L 42.288 11.440 Z M 50.832 10.552 L 54.161 10.663 L 56.048 11.218 L 56.713 11.995 L 57.046 12.993 L 57.823 18.764 L 58.378 19.984 L 59.487 21.094 L 62.816 22.425 L 65.258 23.757 L 66.145 23.979 L 67.699 23.979 L 69.363 23.202 L 73.358 19.873 L 74.801 19.096 L 76.132 19.207 L 77.353 20.095 L 80.793 23.646 L 82.013 25.421 L 82.013 26.420 L 81.791 26.975 L 80.682 28.639 L 78.129 31.635 L 77.020 33.744 L 77.131 35.741 L 79.017 41.067 L 80.349 42.843 L 81.680 43.509 L 85.453 43.952 L 87.894 44.507 L 88.893 45.617 L 89.226 47.725 L 89.226 51.942 L 88.671 54.716 L 88.116 55.271 L 87.339 55.604 L 81.902 56.380 L 80.349 57.046 L 79.017 58.822 L 76.909 64.259 L 76.798 66.034 L 77.131 67.033 L 78.129 68.808 L 80.571 72.026 L 81.125 73.247 L 81.015 74.357 L 80.349 75.466 L 77.353 78.684 L 75.688 80.127 L 74.690 80.682 L 73.580 80.682 L 73.136 80.460 L 68.808 76.909 L 66.922 76.021 L 65.036 76.132 L 62.705 77.353 L 59.487 78.684 L 58.267 79.794 L 57.601 81.347 L 56.935 86.452 L 56.380 88.227 L 55.604 88.893 L 53.384 89.337 L 49.501 89.337 L 47.947 89.115 L 46.727 88.671 L 46.061 88.005 L 45.728 87.118 L 45.062 81.680 L 44.396 79.794 L 43.065 78.573 L 37.738 76.021 L 35.852 75.799 L 34.742 76.132 L 29.194 80.238 L 27.974 80.238 L 26.420 79.239 L 22.758 75.355 L 21.649 73.469 L 21.649 72.803 L 22.203 71.694 L 25.199 67.810 L 25.976 65.812 L 25.754 64.037 L 24.201 60.486 L 23.646 58.600 L 23.091 57.601 L 21.871 56.713 L 20.761 56.380 L 17.876 56.159 L 15.435 55.382 L 14.769 54.605 L 14.325 52.608 L 14.325 47.392 L 14.547 46.172 L 14.991 45.173 L 15.989 44.507 L 20.983 43.620 L 22.536 42.843 L 23.091 42.288 L 23.757 41.067 L 24.090 39.736 L 25.976 35.297 L 25.976 33.522 L 25.310 32.079 L 22.758 28.750 L 21.538 26.642 L 21.649 25.643 L 22.980 23.757 L 25.643 20.983 L 28.085 18.985 L 29.083 18.985 L 29.527 19.207 L 33.855 22.758 L 35.186 23.535 L 36.074 23.757 L 37.627 23.535 L 41.511 21.760 L 42.399 21.538 L 43.287 21.094 L 44.285 20.095 L 44.729 19.318 L 45.617 13.437 L 46.283 11.551 L 47.503 10.885 Z M 50.055 28.306 L 45.728 29.194 L 41.955 30.859 L 38.404 33.078 L 35.741 35.741 L 33.744 38.626 L 32.301 41.622 L 31.746 43.287 L 30.970 46.727 L 30.859 51.609 L 31.635 55.715 L 33.522 60.264 L 36.185 64.037 L 38.515 66.367 L 41.955 68.808 L 45.062 70.251 L 48.502 71.139 L 52.497 71.361 L 56.269 70.806 L 59.709 69.585 L 62.151 68.254 L 64.037 66.922 L 66.922 64.148 L 69.363 60.597 L 70.917 56.935 L 71.804 53.052 L 71.915 47.947 L 71.250 44.174 L 69.807 40.069 L 67.699 36.407 L 64.814 33.189 L 61.818 30.970 L 57.934 29.194 L 54.494 28.417 Z M 60.930 33.522 L 63.704 35.741 L 66.256 38.737 L 68.032 41.955 L 69.252 45.950 L 69.585 48.391 L 69.585 50.943 L 69.363 52.830 L 68.587 55.937 L 67.144 59.266 L 65.812 61.374 L 64.148 63.371 L 62.040 65.258 L 60.042 66.589 L 58.933 67.144 L 58.489 67.144 L 58.378 66.589 L 59.266 65.923 L 62.040 62.927 L 64.370 59.044 L 66.034 54.272 L 66.589 49.834 L 66.256 45.728 L 65.480 42.288 L 63.149 37.517 L 60.375 34.077 L 60.375 33.633 Z M 47.836 31.081 L 50.166 31.081 L 53.162 31.857 L 56.380 33.633 L 59.376 36.296 L 61.263 38.737 L 62.816 41.733 L 63.926 45.173 L 64.370 48.613 L 64.259 51.831 L 63.815 54.605 L 62.705 57.823 L 61.596 59.931 L 60.042 62.151 L 57.823 64.370 L 55.049 66.367 L 52.497 67.588 L 49.501 68.365 L 48.169 68.365 L 46.727 68.032 L 42.954 66.367 L 40.069 64.259 L 38.071 62.262 L 36.074 59.598 L 34.853 57.379 L 33.744 54.161 L 33.300 51.054 L 33.300 48.391 L 33.966 44.618 L 34.964 41.844 L 37.184 38.071 L 38.737 36.185 L 42.288 32.967 L 44.507 31.968 Z" />
    </IconBaseFilled>
  );
}

/* ================================================================== */
/* Icônes dessinées (tracé) — DA fait-main, motif écho                 */
/* ================================================================== */

/* --- Navigation / cœur --- */

export function IconDashboard(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="14" y="14" width="30" height="30" rx="7" />
      <rect x="56" y="14" width="30" height="18" rx="7" />
      <rect x="56" y="44" width="30" height="42" rx="7" />
      <rect x="14" y="56" width="30" height="30" rx="7" />
    </IconBaseStroke>
  );
}

/** 🏛️ Patrimoine / monument / projet — double fronton + socle (écho). */
export function IconMonument(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M10 42 L50 16 L90 42" />
      <path d="M23 41 L50 25 L77 41" />
      <path d="M14 47 H86" />
      <path d="M26 50 V80 M42 50 V80 M58 50 V80 M74 50 V80" />
      <path d="M12 84 H88" />
      <path d="M16 79 H84" />
    </IconBaseStroke>
  );
}

export function IconDocuments(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M36 24 V16 H62 L78 32 V70" />
      <path d="M24 30 H50 L64 44 V84 H24 Z" />
      <path d="M50 30 V44 H64" />
      <path d="M34 58 H54 M34 70 H50" />
    </IconBaseStroke>
  );
}

export function IconDocument(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M28 14 H58 L74 30 V86 H28 Z" />
      <path d="M58 14 V30 H74" />
      <path d="M38 44 H64 M38 56 H64 M38 68 H56" />
    </IconBaseStroke>
  );
}

export function IconDocumentValide(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M28 14 H58 L74 30 V86 H28 Z" />
      <path d="M58 14 V30 H74" />
      <path d="M37 58 L46 67 L64 47" />
    </IconBaseStroke>
  );
}

export function IconDocumentAlerte(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M28 14 H58 L74 30 V86 H28 Z" />
      <path d="M58 14 V30 H74" />
      <path d="M51 44 V62" />
      <circle cx="51" cy="73" r="2.6" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconArchive(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="16" y="24" width="68" height="18" rx="5" />
      <path d="M22 42 V80 Q22 84 26 84 H74 Q78 84 78 80 V42" />
      <path d="M40 56 H60" />
    </IconBaseStroke>
  );
}

export function IconDevis(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M30 14 H70 V84 L61 90 L50 84 L39 90 L30 84 Z" />
      <path d="M40 34 H60 M40 46 H60 M40 58 H54" />
    </IconBaseStroke>
  );
}

/* --- Dossiers --- */

/** 🗂️ Dossier — chemise + écho. */
export function IconDossier(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M14 34 Q14 28 20 28 H40 L47 35 H80 Q86 35 86 41 V74 Q86 80 80 80 H20 Q14 80 14 74 Z" />
      <path d="M22 70 H78" />
    </IconBaseStroke>
  );
}

export function IconDossierOuvert(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M16 76 V36 Q16 30 22 30 H40 L47 37 H78 Q84 37 84 43 V50" />
      <path d="M16 78 L28 52 H92 L80 78 Z" />
    </IconBaseStroke>
  );
}

export function IconAjouterDossier(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M14 34 Q14 28 20 28 H40 L47 35 H80 Q86 35 86 41 V74 Q86 80 80 80 H20 Q14 80 14 74 Z" />
      <path d="M50 50 V70 M40 60 H60" />
    </IconBaseStroke>
  );
}

export function IconRetirerDossier(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M14 34 Q14 28 20 28 H40 L47 35 H80 Q86 35 86 41 V74 Q86 80 80 80 H20 Q14 80 14 74 Z" />
      <path d="M40 60 H60" />
    </IconBaseStroke>
  );
}

export function IconDepot(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 16 V58" />
      <path d="M34 32 L50 16 L66 32" />
      <path d="M22 62 V78 H78 V62" />
    </IconBaseStroke>
  );
}

export function IconSuivi(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M18 74 A36 36 0 1 1 82 74" />
      <path d="M50 72 L67 46" />
      <circle cx="50" cy="72" r="3.5" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

/* --- Aides / finances --- */

/** 💶 Les aides — billet (double bord = écho) + médaillon. Remplace l'étoile. */
export function IconAide(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="12" y="30" width="76" height="40" rx="8" />
      <rect x="20" y="37" width="60" height="26" rx="4" />
      <circle cx="50" cy="50" r="9" />
      <path d="M28 44 V56 M72 44 V56" />
    </IconBaseStroke>
  );
}

/** 💡 Accompagnement / suggestion (ex-Sparkles « magie »). */
export function IconAccompagnement(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 16 A22 22 0 0 1 64 56 Q60 60 60 66 H40 Q40 60 36 56 A22 22 0 0 1 50 16 Z" />
      <path d="M42 74 H58 M45 82 H55" />
    </IconBaseStroke>
  );
}

export function IconSubvention(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <ellipse cx="50" cy="30" rx="26" ry="10" />
      <path d="M24 30 V48 A26 10 0 0 0 76 48 V30" />
      <path d="M24 48 V66 A26 10 0 0 0 76 66 V48" />
    </IconBaseStroke>
  );
}

export function IconTendance(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M16 64 L40 40 L54 54 L84 24" />
      <path d="M64 24 H84 V44" />
    </IconBaseStroke>
  );
}

/* --- Patrimoine / protection --- */

/** 🛡️ Protection / Monument Historique — bouclier + écho intérieur. */
export function IconProtection(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 14 L80 24 V46 Q80 74 50 86 Q20 74 20 46 V24 Z" />
      <path d="M50 24 L70 31 V47 Q70 66 50 75 Q30 66 30 47 V31 Z" />
      <path d="M42 50 L48 57 L60 43" />
    </IconBaseStroke>
  );
}

export function IconDiagnostic(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M64 36 L54 54 L36 64 L46 46 Z" />
    </IconBaseStroke>
  );
}

export function IconLocalisation(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 86 C32 66 24 54 24 40 A26 26 0 0 1 76 40 C76 54 68 66 50 86 Z" />
      <circle cx="50" cy="40" r="9" />
    </IconBaseStroke>
  );
}

export function IconCalendrier(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="16" y="22" width="68" height="64" rx="9" />
      <path d="M16 40 H84 M34 14 V30 M66 14 V30" />
    </IconBaseStroke>
  );
}

export function IconEcheance(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M84 44 V31 Q84 22 75 22 H25 Q16 22 16 31 V77 Q16 86 25 86 H50" />
      <path d="M16 40 H84 M34 14 V30 M66 14 V30" />
      <circle cx="68" cy="66" r="16" />
      <path d="M68 58 V66 H75" />
    </IconBaseStroke>
  );
}

export function IconTemps(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M50 30 V50 L65 60" />
    </IconBaseStroke>
  );
}

/* --- BTP / artisans --- */

export function IconChantier(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M22 62 A28 28 0 0 1 78 62" />
      <path d="M44 35 H56 Q60 35 60 40 V60" />
      <path d="M12 62 H88 V70 H12 Z" />
    </IconBaseStroke>
  );
}

export function IconProspect(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <circle cx="50" cy="50" r="18" />
      <circle cx="50" cy="50" r="4" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconContact(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="14" y="26" width="72" height="48" rx="9" />
      <path d="M18 32 L50 56 L82 32" />
    </IconBaseStroke>
  );
}

export function IconEquipe(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="38" cy="38" r="13" />
      <path d="M15 77 Q15 56 38 56 Q54 56 60 67" />
      <circle cx="67" cy="44" r="11" />
      <path d="M59 60 Q85 59 85 79" />
    </IconBaseStroke>
  );
}

export function IconAccount(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="36" r="16" />
      <path d="M20 82 Q20 56 50 56 Q80 56 80 82" />
    </IconBaseStroke>
  );
}

/** Alias sémantique de IconAccount. */
export const IconCompte = IconAccount;

export function IconHelp(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M39 41 Q41 30 52 30 Q65 30 65 42 Q65 53 52 55 V61" />
      <circle cx="52" cy="71" r="2.6" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconAgenda(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="24" y="16" width="54" height="70" rx="8" />
      <path d="M24 36 H78" />
      <path d="M16 28 H24 M16 48 H24 M16 68 H24" />
      <circle cx="51" cy="61" r="3" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

/* --- Statuts --- */

export function IconSucces(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M36 51 L46 61 L66 39" />
    </IconBaseStroke>
  );
}

export function IconAttention(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 16 L88 82 H12 Z" />
      <path d="M50 42 V62" />
      <circle cx="50" cy="72" r="2.6" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconErreur(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M39 39 L61 61 M61 39 L39 61" />
    </IconBaseStroke>
  );
}

export function IconInfo(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M50 46 V66" />
      <circle cx="50" cy="34" r="2.6" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconVerrou(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="22" y="46" width="56" height="40" rx="8" />
      <path d="M34 46 V36 A16 16 0 0 1 66 36 V46" />
      <path d="M50 62 V72" />
    </IconBaseStroke>
  );
}

export function IconPublic(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="50" cy="50" r="34" />
      <path d="M16 50 H84 M50 16 V84" />
      <path d="M50 16 Q30 50 50 84 Q70 50 50 16" />
    </IconBaseStroke>
  );
}

/* --- Actions de marque --- */

export function IconRecherche(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="44" cy="44" r="24" />
      <path d="M62 62 L82 82" />
    </IconBaseStroke>
  );
}

export function IconModifier(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M64 22 L78 36 L40 74 L24 78 L28 62 Z" />
      <path d="M58 28 L72 42" />
    </IconBaseStroke>
  );
}

export function IconSupprimer(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M24 32 H76" />
      <path d="M32 32 V80 Q32 84 36 84 H64 Q68 84 68 80 V32" />
      <path d="M40 32 V24 H60 V32" />
      <path d="M44 44 V72 M56 44 V72" />
    </IconBaseStroke>
  );
}

export function IconVoir(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M12 50 Q50 22 88 50 Q50 78 12 50 Z" />
      <circle cx="50" cy="50" r="11" />
    </IconBaseStroke>
  );
}

export function IconRafraichir(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M78 38 A34 34 0 1 0 82 58" />
      <path d="M80 20 V40 H60" />
    </IconBaseStroke>
  );
}

export function IconAjouter(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 22 V78 M22 50 H78" />
    </IconBaseStroke>
  );
}

export function IconLienExterne(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M70 56 V76 Q70 80 66 80 H28 Q24 80 24 76 V38 Q24 34 28 34 H48" />
      <path d="M58 20 H80 V42" />
      <path d="M80 20 L46 54" />
    </IconBaseStroke>
  );
}

export function IconModele(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="18" y="18" width="64" height="64" rx="9" />
      <path d="M18 38 H82 M42 38 V82" />
    </IconBaseStroke>
  );
}

export function IconRegle(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 22 V82 M30 82 H70" />
      <path d="M20 34 H80" />
      <path d="M20 34 L10 54 H30 Z" />
      <path d="M80 34 L70 54 H90 Z" />
      <circle cx="50" cy="24" r="4" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconLivre(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M50 28 Q34 20 16 24 V76 Q34 72 50 80 Q66 72 84 76 V24 Q66 20 50 28 Z" />
      <path d="M50 28 V80" />
    </IconBaseStroke>
  );
}

export function IconCle(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <circle cx="36" cy="40" r="18" />
      <path d="M48 52 L80 84" />
      <path d="M70 74 L80 64 M62 66 L72 56" />
    </IconBaseStroke>
  );
}

export function IconEnregistrer(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M22 18 H68 L82 32 V82 H22 Z" />
      <path d="M34 18 V40 H66 V18" />
      <rect x="36" y="54" width="28" height="28" rx="3" />
    </IconBaseStroke>
  );
}

export function IconMaison(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M16 50 L50 20 L84 50" />
      <path d="M26 44 V82 H74 V44" />
      <path d="M42 82 V60 H58 V82" />
    </IconBaseStroke>
  );
}

export function IconImage(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <rect x="16" y="22" width="68" height="56" rx="9" />
      <circle cx="38" cy="42" r="7" />
      <path d="M20 72 L42 52 L56 64 L70 52 L82 64" />
    </IconBaseStroke>
  );
}

export function IconListe(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M42 30 H82 M42 50 H82 M42 70 H82" />
      <path d="M20 28 L25 33 L33 24" />
      <path d="M20 48 L25 53 L33 44" />
      <circle cx="25" cy="70" r="3.2" fill="currentColor" stroke="none" />
    </IconBaseStroke>
  );
}

export function IconCitation(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M28 38 Q18 44 18 58 H36 V42 Q36 38 32 38 Z" />
      <path d="M58 38 Q48 44 48 58 H66 V42 Q66 38 62 38 Z" />
    </IconBaseStroke>
  );
}

export function IconParchemin(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M28 24 H78 Q86 24 86 32 V72 Q86 80 78 80 H30" />
      <path d="M28 24 Q20 24 20 32 V74 Q20 80 14 80" />
      <path d="M40 42 H72 M40 56 H64" />
    </IconBaseStroke>
  );
}

export function IconDeconnexion(p: IconProps) {
  return (
    <IconBaseStroke {...p}>
      <path d="M44 24 H26 Q20 24 20 30 V70 Q20 76 26 76 H44" />
      <path d="M52 50 H86" />
      <path d="M72 36 L86 50 L72 64" />
    </IconBaseStroke>
  );
}
