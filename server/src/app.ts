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
app.use(helmet());
app.use(cors({ origin: env.CORS_ORIGIN, credentials: true }));
app.use(express.json({ limit: "100kb" }));
app.use("/api", apiRateLimit, apiRouter);
app.use(notFoundHandler);
app.use(errorHandler);
