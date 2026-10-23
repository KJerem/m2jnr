FROM node:22.20-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
# Même version de npm que celle qui a produit package-lock.json.
RUN npm install -g npm@11.6.2 --no-audit --no-fund

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Développement : sources montées en volume, rechargement à chaud.
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

# Production : build standalone, image minimale.
FROM deps AS build
COPY . .
RUN npm run build

FROM base AS prod
ENV NODE_ENV=production
RUN addgroup -S app && adduser -S app -G app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER app
EXPOSE 3000
CMD ["node", "server.js"]
