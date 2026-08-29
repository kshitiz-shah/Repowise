import { z } from "zod";

const password = z
  .string()
  .min(12, "Password must be at least 12 characters")
  .max(128)
  .regex(/[a-z]/, "Password must include a lowercase letter")
  .regex(/[A-Z]/, "Password must include an uppercase letter")
  .regex(/[0-9]/, "Password must include a number")
  .regex(/[^A-Za-z0-9]/, "Password must include a symbol");

export const registerSchema = z.object({
  body: z.object({
    name: z.string().trim().min(2).max(100),
    email: z.string().trim().email().max(320),
    password,
  }),
  query: z.object({}),
  params: z.object({}),
});

export const loginSchema = z.object({
  body: z.object({
    email: z.string().trim().email().max(320),
    password: z.string().min(1).max(128),
  }),
  query: z.object({}),
  params: z.object({}),
});
