"""Le budget d'un run : réserver le coût plafond avant un appel, régler sur le coût facturé.

Un appel réserve d'abord ce qu'il peut coûter au pire ; le budget refuse s'il
ne reste pas de quoi le couvrir. Une fois l'appel fait, la réservation se règle
sur le coût que la réponse a facturé ; un coût inconnu (panne, réponse sans
`usage.cost`) compte pour toute la réservation, jamais pour zéro. Sûr entre
fils : plusieurs extractions en parallèle tirent sur le même budget.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


class BudgetEpuise(Exception):
    """Plus de quoi couvrir la réservation demandée."""


@dataclass
class Reservation:
    montant: float
    etiquette: str
    reglee: bool = False


class Budget:
    def __init__(self, plafond_usd: float) -> None:
        if plafond_usd <= 0:
            raise ValueError("plafond nul ou négatif")
        self.plafond = plafond_usd
        self._depense = 0.0
        self._reserve = 0.0
        self._inconnus = 0
        self._verrou = threading.Lock()

    @property
    def depense(self) -> float:
        return self._depense

    @property
    def reserve(self) -> float:
        return self._reserve

    @property
    def couts_inconnus(self) -> int:
        """Nombre d'appels réglés sans coût facturé (comptés à leur réservation)."""
        return self._inconnus

    def reserver(self, montant: float, etiquette: str = "") -> Reservation:
        if montant < 0:
            raise ValueError("réservation négative")
        with self._verrou:
            if self._depense + self._reserve + montant > self.plafond:
                raise BudgetEpuise(
                    f"{etiquette or 'appel'} : {montant:.4f} $ demandés, "
                    f"{self.plafond - self._depense - self._reserve:.4f} $ disponibles"
                )
            self._reserve += montant
            return Reservation(montant, etiquette)

    def regler(self, r: Reservation, cout_usd: float | None) -> None:
        with self._verrou:
            if r.reglee:
                raise ValueError(f"réservation déjà réglée : {r.etiquette}")
            r.reglee = True
            self._reserve -= r.montant
            if cout_usd is None:
                self._inconnus += 1
                self._depense += r.montant
            else:
                self._depense += cout_usd
