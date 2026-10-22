FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
# "Generated on" stamps in the university's local time; override per deployment.
ENV TZ=Asia/Kolkata
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY tsconfig.json ./
COPY src ./src
USER node
EXPOSE 8902
CMD ["npx", "tsx", "src/server.ts"]
