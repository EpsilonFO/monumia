FROM python:3.12-slim

# uv en binaire, version épinglée
COPY --from=ghcr.io/astral-sh/uv:0.8.24 /uv /uvx /bin/

WORKDIR /app

# Le venv vit HORS de /app : docker-compose monte ./backend sur /app, ce qui
# masquait le venv construit ici. `uv run` en recréait alors un dans
# backend/.venv de l'hôte, au démarrage, partagé par les deux backends.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

# Ce calque ne change que si les dépendances changent. Pas de `COPY . .` : le
# code arrive par le bind mount, et le copier ici produisait une image neuve de
# plus de 2 Go à chaque commit touchant backend/ (data/sources compris).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# `uv run` dans le conteneur (docker exec) doit utiliser /opt/venv tel quel,
# sans tenter d'y ajouter le groupe dev.
ENV UV_NO_SYNC=1

EXPOSE 8000

# Le code n'étant plus dans l'image, un changement de code ne recrée plus le
# conteneur tout seul : deploy.sh le redémarre (cf. redemarrer_backends).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
