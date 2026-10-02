"""Lancer en même temps des appels Supabase qui ne dépendent pas les uns des autres.

Chaque requête PostgREST coûte un aller-retour vers Francfort, de l'ordre de
20 à 35 ms. Le dashboard en enchaînait seize en série alors que la plupart
n'attendent rien des autres : les regrouper en vagues rend l'essentiel de ce
temps, sans passer le backend en async ni déplacer la logique dans des RPC.

Trois règles tiennent ce module :

  * UN exécuteur pour tout le process, borné. Les routes sont des `def`
    synchrones, déjà servies par le threadpool d'anyio (40 threads) : un
    exécuteur créé par requête échapperait à toute limite.
  * Les exceptions levées dans un appel ressortent telles quelles chez
    l'appelant, `HTTPException` comprise. Elles sont relevées dans l'ordre des
    appels : mettre le contrôle d'accès en premier garantit que c'est son refus
    qui sort, et pas l'erreur d'une lecture partie en même temps.
  * Pas d'imbrication : un appel qui tourne déjà dans l'exécuteur et qui
    rappelle `en_parallele` exécute ses sous-appels en série. Attendre depuis un
    worker des tâches soumises au même pool borné finit en interblocage dès que
    le pool est plein.

Sûr pour le client service-role : `supabase.table(...)` construit un query
builder neuf à chaque appel et seule la session httpx est partagée. Elle est
thread-safe parce qu'elle parle HTTP/1.1 (une connexion du pool par requête),
cf. `db._service_client`. En HTTP/2, le défaut de postgrest, les 16 threads se
partageaient une seule connexion multiplexée, qui lâchait par rafales et
emportait toutes les requêtes en vol. Les opérations d'authentification, qui
mutent l'état du client, passent par `get_anon_supabase()`, créé par requête —
ne jamais en faire passer une ici sur le client partagé.
"""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, overload

#: Au-delà, les appels attendent leur tour : quatre vagues de quatre requêtes
#: pour quelques requêtes HTTP simultanées, c'est largement assez.
MAX_WORKERS = 16

_local = threading.local()


def _marquer_worker() -> None:
    _local.worker = True


_POOL = ThreadPoolExecutor(
    max_workers=MAX_WORKERS, thread_name_prefix="supabase-io", initializer=_marquer_worker
)


@overload
def en_parallele[A, B](a: Callable[[], A], b: Callable[[], B], /) -> tuple[A, B]: ...
@overload
def en_parallele[A, B, C](
    a: Callable[[], A], b: Callable[[], B], c: Callable[[], C], /
) -> tuple[A, B, C]: ...
@overload
def en_parallele[A, B, C, D](
    a: Callable[[], A], b: Callable[[], B], c: Callable[[], C], d: Callable[[], D], /
) -> tuple[A, B, C, D]: ...
def en_parallele(*appels: Callable[[], Any]) -> tuple[Any, ...]:
    """Exécute les appels en même temps et rend leurs résultats, dans l'ordre."""
    if len(appels) <= 1 or getattr(_local, "worker", False):
        return tuple(appel() for appel in appels)
    futures = [_POOL.submit(appel) for appel in appels]
    return tuple(future.result() for future in futures)
