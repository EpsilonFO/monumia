# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

ARG VITE_APP_URL=https://app.monumia.fr
ENV VITE_APP_URL=$VITE_APP_URL

# Chemin de base : '/' en prod, '/landing/' pour la beta (beta.monumia.fr/landing)
ARG VITE_BASE=/
ENV VITE_BASE=$VITE_BASE

RUN npm run build

# Output stage — built files copied by docker-compose into nginx
FROM alpine:3.19 AS output
COPY --from=build /app/dist /dist
