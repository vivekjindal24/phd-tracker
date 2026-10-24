# Self-hosted web container (ARCHITECTURE.md §4); Vercel builds web/ itself.
# NEXT_PUBLIC_* are inlined at build time, so each installation builds with its own URLs.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_EXPORT_URL
RUN test -n "$NEXT_PUBLIC_API_URL" -a -n "$NEXT_PUBLIC_EXPORT_URL" \
      || (echo "build args NEXT_PUBLIC_API_URL and NEXT_PUBLIC_EXPORT_URL are required" >&2; exit 1) \
    && npm run build \
    && chmod -R a+rX .next/standalone .next/static

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
