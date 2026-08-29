import { prisma } from "../config/database.js";
import { ApiError } from "../utils/api-error.js";
import { createAccessToken, createRefreshToken } from "../utils/jwt.js";
import { hashPassword, verifyPassword } from "../utils/password.js";
import { findUserByEmail, toSafeUser } from "./user.service.js";

const refreshTokenLifetimeMs = 7 * 24 * 60 * 60 * 1000;

interface Credentials {
  email: string;
  password: string;
}

const createSession = async (user: { id: string; email: string }) => {
  const refreshToken = createRefreshToken();
  const refreshTokenHash = await hashPassword(refreshToken);
  const session = await prisma.authSession.create({
    data: { userId: user.id, refreshTokenHash, expiresAt: new Date(Date.now() + refreshTokenLifetimeMs) },
  });
  return {
    accessToken: createAccessToken({ sub: user.id, email: user.email, sid: session.id }),
    refreshToken,
  };
};

export const register = async (input: Credentials & { name: string }) => {
  const email = input.email.toLowerCase();
  if (await findUserByEmail(email)) {
    throw new ApiError(409, "An account with this email already exists", "EMAIL_ALREADY_EXISTS");
  }

  const user = await prisma.user.create({
    data: { name: input.name.trim(), email, passwordHash: await hashPassword(input.password) },
  });
  return { user: toSafeUser(user), ...(await createSession(user)) };
};

export const login = async (input: Credentials) => {
  const user = await findUserByEmail(input.email.toLowerCase());
  if (!user || !(await verifyPassword(input.password, user.passwordHash))) {
    throw new ApiError(401, "Invalid email or password", "INVALID_CREDENTIALS");
  }
  return { user: toSafeUser(user), ...(await createSession(user)) };
};

export const revokeSession = (sessionId: string) =>
  prisma.authSession.updateMany({ where: { id: sessionId, revokedAt: null }, data: { revokedAt: new Date() } });
