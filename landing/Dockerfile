# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

ARG VITE_APP_URL=https://app.monumia.fr
ENV VITE_APP_URL=$VITE_APP_URL

# URL du backend (endpoint /waitlist) : app.monumia.fr/api en prod,
# beta.monumia.fr/api en beta. Passée par docker-compose.
ARG VITE_API_URL=https://app.monumia.fr/api
ENV VITE_API_URL=$VITE_API_URL

# Chemin de base : '/' en prod, '/landing/' pour la beta (beta.monumia.fr/landing)
ARG VITE_BASE=/
ENV VITE_BASE=$VITE_BASE

# `vite build` seul, pas `npm run build` (= `tsc -b && vite build`) : le
# type-check a déjà tourné au pre-commit, au pre-push et en CI, et le refaire
# ici coûtait autant que le bundle lui-même, deux fois par déploiement (app et
# beta, ou landing et landing-beta) sur les processeurs du VPS.
RUN npx vite build

# Output stage — built files copied by docker-compose into nginx
FROM alpine:3.19 AS output
COPY --from=build /app/dist /dist
