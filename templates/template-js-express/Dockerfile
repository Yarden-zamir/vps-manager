FROM oven/bun:1-alpine AS dependencies
WORKDIR /app
COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile --production

FROM oven/bun:1-alpine AS runtime
WORKDIR /app
RUN apk add --no-cache dumb-init
RUN addgroup -g 1001 -S bunuser && adduser -S bunuser -u 1001

COPY --from=dependencies --chown=bunuser:bunuser /app/node_modules ./node_modules
COPY --chown=bunuser:bunuser package.json ./
COPY --chown=bunuser:bunuser src ./src

USER bunuser
EXPOSE 3000

ENTRYPOINT ["dumb-init", "--"]
CMD ["bun", "src/index.js"]

ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD bun -e "require('http').get('http://localhost:3000/health', (res) => process.exit(res.statusCode === 200 ? 0 : 1))"
