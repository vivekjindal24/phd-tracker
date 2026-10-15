FROM node:22-slim

WORKDIR /srv
# 512MB free instances: fail fast and cleanly instead of being OOM-strangled
ENV NODE_ENV=production NODE_OPTIONS=--max-old-space-size=384
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY tsconfig.json ./
COPY src ./src

EXPOSE 8100
# tsx is the runtime (typecheck-clean TS, no build step needed for a stateless service)
CMD ["npx", "tsx", "src/server.ts"]