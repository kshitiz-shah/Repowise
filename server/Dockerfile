# ===============================================================
# Multi-Stage Production Dockerfile for RepoWise Server (PBL)
# ===============================================================

# ----------------- Stage 1: Build & Compile -----------------
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies needed for native modules (if any)
RUN apk add --no-cache libc6-compat

# Copy package manifests & prisma schema first (layer caching)
COPY package*.json ./
COPY prisma ./prisma/

# Install full dependencies (including devDependencies like typescript & prisma)
RUN npm ci

# Copy TypeScript configuration and source code
COPY tsconfig.json ./
COPY src ./src/

# Generate Prisma ORM client and compile TypeScript to JavaScript
RUN npx prisma generate && npm run build

# Prune devDependencies to keep final image minimal
RUN npm prune --production

# ----------------- Stage 2: Minimal Production Runtime -----------------
FROM node:22-alpine AS runner

WORKDIR /app

# Run as non-root user for security compliance (Principle of Least Privilege)
ENV NODE_ENV=production
ENV PORT=5000

# Copy runtime node_modules, generated Prisma client, and compiled dist
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/dist ./dist
COPY --from=builder --chown=node:node /app/prisma ./prisma
COPY --from=builder --chown=node:node /app/package*.json ./

USER node

EXPOSE 5000

# Container healthcheck probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

# Start production server
CMD ["node", "dist/server.js"]
