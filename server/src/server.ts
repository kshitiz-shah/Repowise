import { prisma } from "./config/database.js";
import { env } from "./config/env.js";
import { app } from "./app.js";

const server = app.listen(env.PORT, () => {
  console.log(`RepoWise backend listening on port ${env.PORT}`);
});

const shutdown = async () => {
  server.close(async () => {
    await prisma.$disconnect();
    process.exit(0);
  });
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
