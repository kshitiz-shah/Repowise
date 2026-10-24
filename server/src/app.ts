import cors from "cors";
import express from "express";
import helmet from "helmet";
import pino from "pino";
import { pinoHttp } from "pino-http";

import { env } from "./config/env.js";
import { errorHandler, notFoundHandler } from "./middleware/error.middleware.js";
import { apiRateLimit } from "./middleware/rate-limit.middleware.js";
import { apiRouter } from "./routes/index.js";

const logger = pino({ level: env.NODE_ENV === "production" ? "info" : "debug", redact: ["req.headers.authorization", "req.body.password", "req.body.refreshToken"] });

export const app = express();
app.disable("x-powered-by");
app.use(pinoHttp({ logger }));
app.use(
  helmet({
    crossOriginResourcePolicy: { policy: "cross-origin" },
    crossOriginOpenerPolicy: { policy: "unsafe-none" },
  })
);

const envOrigins = env.CORS_ORIGIN.split(",").map((s) => s.trim()).filter(Boolean);
const allowedOrigins = new Set([
  ...envOrigins,
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:5174",
  "http://127.0.0.1:5174",
]);

app.use(
  cors({
    origin: (origin, callback) => {
      if (!origin || env.CORS_ORIGIN === "*" || allowedOrigins.has(origin)) {
        return callback(null, true);
      }
      return callback(null, false);
    },
    credentials: true,
  })
);
app.use(express.json({ limit: "100kb" }));
app.use("/api", apiRateLimit, apiRouter);
app.use(notFoundHandler);
app.use(errorHandler);
