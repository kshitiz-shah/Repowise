import crypto from "node:crypto";

import jwt from "jsonwebtoken";

import { env } from "../config/env.js";

export interface AccessTokenPayload {
  sub: string;
  email: string;
  sid: string;
}

export const createAccessToken = (payload: AccessTokenPayload): string =>
  jwt.sign(payload, env.JWT_ACCESS_SECRET, { expiresIn: env.ACCESS_TOKEN_EXPIRES_IN as jwt.SignOptions["expiresIn"] });

export const verifyAccessToken = (token: string): AccessTokenPayload =>
  jwt.verify(token, env.JWT_ACCESS_SECRET) as AccessTokenPayload;

export const createRefreshToken = (): string => crypto.randomBytes(48).toString("base64url");
