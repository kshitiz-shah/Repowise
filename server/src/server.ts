import { prisma } from "./config/database.js";
import { env } from "./config/env.js";
import { app } from "./app.js";

const server = app.listen(env.PORT, () => {
  console.log(`RepoWise backend listening on port ${env.PORT}`);
});

server.on("error", (error: NodeJS.ErrnoException) => {
  if (error.code === "EADDRINUSE") {
    console.error(`[SERVER ERROR] Port ${env.PORT} is already in use by another process. Run 'lsof -i :${env.PORT}' to identify and kill the existing process.`);
  } else if (error.code === "EACCES") {
    console.error(`[SERVER ERROR] Permission denied to bind to port ${env.PORT}.`);
  } else {
    console.error("[SERVER ERROR] Failed to start server:", error);
  }
  process.exit(1);
});

const shutdown = async () => {
  clearInterval(keepAliveTimer);
  server.close(async () => {
    await prisma.$disconnect();
    process.exit(0);
  });
};

// ---------------------------------------------------------------------------
// Keep-Alive Routine: Prevents Render free services and Neon DB from spinning down
// Pings DB, AI microservice, and itself every 5 minutes
// ---------------------------------------------------------------------------
const KEEP_ALIVE_INTERVAL_MS = 5 * 60 * 1000;

const runKeepAlive = async () => {
  try {
    // 1. Keep Neon PostgreSQL alive with a lightweight query
    await prisma.$queryRaw`SELECT 1`;
  } catch (err: any) {
    console.warn("[Keep-Alive] DB ping failed:", err?.message || err);
  }

  try {
    // 2. Keep Render AI service alive by pinging /api/health
    if (env.AI_SERVICE_URL) {
      await fetch(new URL("/api/health", env.AI_SERVICE_URL), {
        signal: AbortSignal.timeout(10_000),
      });
    }
  } catch (err: any) {
    console.warn("[Keep-Alive] AI Service ping failed:", err?.message || err);
  }

  try {
    // 3. Keep this backend gateway alive by pinging itself
    const selfUrl = env.NODE_ENV === "production" ? "https://repowise-server.onrender.com/api/health" : `http://localhost:${env.PORT}/api/health`;
    await fetch(selfUrl, { signal: AbortSignal.timeout(10_000) });
  } catch {
    // ignore self ping errors
  }
};

const keepAliveTimer = setInterval(runKeepAlive, KEEP_ALIVE_INTERVAL_MS);
keepAliveTimer.unref();
// Run initial keep-alive 10 seconds after startup
setTimeout(runKeepAlive, 10_000).unref();

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

process.on("unhandledRejection", (reason) => {
  console.error("[UNHANDLED REJECTION]", reason);
});

process.on("uncaughtException", (error) => {
  console.error("[UNCAUGHT EXCEPTION]", error);
  process.exit(1);
});
