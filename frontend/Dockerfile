# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=https://patrialta.fr/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# The built files are in /app/dist — they will be copied by docker-compose into nginx
FROM alpine:3.19 AS output
COPY --from=build /app/dist /dist
