import type { User } from "@prisma/client";

import { prisma } from "../config/database.js";

export const toSafeUser = (user: User) => ({
  id: user.id,
  name: user.name,
  email: user.email,
  createdAt: user.createdAt,
  updatedAt: user.updatedAt,
});

export const findUserByEmail = (email: string) => prisma.user.findUnique({ where: { email } });
export const findUserById = (id: string) => prisma.user.findUnique({ where: { id } });
