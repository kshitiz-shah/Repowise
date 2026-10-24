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
  server.close(async () => {
    await prisma.$disconnect();
    process.exit(0);
  });
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

process.on("unhandledRejection", (reason) => {
  console.error("[UNHANDLED REJECTION]", reason);
});

process.on("uncaughtException", (error) => {
  console.error("[UNCAUGHT EXCEPTION]", error);
  process.exit(1);
});
