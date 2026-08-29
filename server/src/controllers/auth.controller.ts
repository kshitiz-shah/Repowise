import type { RequestHandler, Response } from "express";

import { env } from "../config/env.js";
import * as authService from "../services/auth.service.js";
import { findUserById, toSafeUser } from "../services/user.service.js";
import { ApiError } from "../utils/api-error.js";

const sendSession = (res: Response, result: Awaited<ReturnType<typeof authService.login>>) => {
  res.cookie("repowise_refresh", result.refreshToken, {
    httpOnly: true,
    secure: env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 7 * 24 * 60 * 60 * 1000,
    path: "/api/auth",
  });
  res.json({ success: true, data: { user: result.user, accessToken: result.accessToken } });
};

export const register: RequestHandler = async (req, res, next) => {
  try {
    const result = await authService.register(req.body);
    res.status(201);
    sendSession(res, result);
  } catch (error) { next(error); }
};

export const login: RequestHandler = async (req, res, next) => {
  try { sendSession(res, await authService.login(req.body)); } catch (error) { next(error); }
};

export const logout: RequestHandler = async (req, res, next) => {
  try {
    await authService.revokeSession(req.user!.sessionId);
    res.clearCookie("repowise_refresh", { path: "/api/auth" });
    res.status(200).json({ success: true, data: { message: "Logged out successfully" } });
  } catch (error) { next(error); }
};

export const me: RequestHandler = async (req, res, next) => {
  try {
    const user = await findUserById(req.user!.id);
    if (!user) throw new ApiError(401, "User no longer exists", "UNAUTHORIZED");
    res.status(200).json({ success: true, data: { user: toSafeUser(user) } });
  } catch (error) { next(error); }
};
