FROM node:22-slim AS build
WORKDIR /srv
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:22-slim
WORKDIR /srv
# 512MB free instances: fail fast and cleanly instead of being OOM-strangled
ENV NODE_ENV=production NODE_OPTIONS=--max-old-space-size=384
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /srv/dist ./dist
EXPOSE 8100
CMD ["node", "dist/server.js"]