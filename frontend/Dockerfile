# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=https://app.monumia.fr/api
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
# Widget de retour Ybug : vide = pas de widget dans ce build.
ARG VITE_YBUG_ID=
# Mesure d'audience PostHog : vide = pas de mesure dans ce build.
ARG VITE_POSTHOG_KEY=
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_YBUG_ID=$VITE_YBUG_ID
ENV VITE_POSTHOG_KEY=$VITE_POSTHOG_KEY

# `vite build` seul, pas `npm run build` (= `tsc -b && vite build`) : le
# type-check a déjà tourné au pre-commit, au pre-push et en CI, et le refaire
# ici coûtait autant que le bundle lui-même, deux fois par déploiement (app et
# beta, ou landing et landing-beta) sur les processeurs du VPS.
RUN npx vite build

# The built files are in /app/dist — they will be copied by docker-compose into nginx
FROM alpine:3.19 AS output
COPY --from=build /app/dist /dist
