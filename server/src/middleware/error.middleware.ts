import type { ErrorRequestHandler, RequestHandler } from "express";
import { ZodError } from "zod";

import { env } from "../config/env.js";
import { ApiError } from "../utils/api-error.js";

export const notFoundHandler: RequestHandler = (req, _res, next) => {
  next(new ApiError(404, `Route ${req.method} ${req.originalUrl} not found`, "NOT_FOUND"));
};

export const errorHandler: ErrorRequestHandler = (error, _req, res, _next) => {
  if (error instanceof ZodError) {
    const issueMessages = error.issues.map((i) => i.message).filter(Boolean);
    const message = issueMessages.length > 0 ? issueMessages.join(". ") : "Invalid request";
    res.status(400).json({
      success: false,
      error: { code: "VALIDATION_ERROR", message, details: error.flatten() },
    });
    return;
  }

  if (error instanceof ApiError) {
    res.status(error.statusCode).json({
      success: false,
      error: { code: error.code, message: error.message, ...(error.details ? { details: error.details } : {}) },
    });
    return;
  }

  console.error("[ERROR HANDLER]", error);

  res.status(500).json({
    success: false,
    error: {
      code: "INTERNAL_SERVER_ERROR",
      message: env.NODE_ENV === "production" ? "An unexpected error occurred" : (error instanceof Error ? error.message : "Internal server error"),
      ...(env.NODE_ENV !== "production" && error instanceof Error ? { details: error.stack } : {}),
    },
  });
};
