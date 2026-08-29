import type { RequestHandler } from "express";
import jwt from "jsonwebtoken";

import { prisma } from "../config/database.js";
import { ApiError } from "../utils/api-error.js";
import { verifyAccessToken } from "../utils/jwt.js";

export const requireAuth: RequestHandler = async (req, _res, next) => {
  try {
    const authorization = req.header("authorization");
    if (!authorization?.startsWith("Bearer ")) {
      throw new ApiError(401, "Authentication required", "UNAUTHORIZED");
    }
    const token = authorization.slice(7);
    const payload = verifyAccessToken(token);
    const session = await prisma.authSession.findFirst({
      where: { id: payload.sid, userId: payload.sub, revokedAt: null, expiresAt: { gt: new Date() } },
    });
    if (!session) throw new ApiError(401, "Session is no longer active", "UNAUTHORIZED");
    req.user = { id: payload.sub, email: payload.email, sessionId: payload.sid };
    next();
  } catch (error) {
    if (error instanceof ApiError) return next(error);
    if (error instanceof jwt.JsonWebTokenError) {
      return next(new ApiError(401, "Invalid or expired access token", "UNAUTHORIZED"));
    }
    return next(error);
  }
};
