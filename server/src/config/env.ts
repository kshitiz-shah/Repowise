import "dotenv/config";

import { z } from "zod";

const environmentSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().url(),
  JWT_ACCESS_SECRET: z.string().min(12),
  JWT_REFRESH_SECRET: z.string().min(12),
  ACCESS_TOKEN_EXPIRES_IN: z.string().default("15m"),
  REFRESH_TOKEN_EXPIRES_IN: z.string().default("7d"),
  CORS_ORIGIN: z.string().default("http://localhost:5173"),
  GITHUB_API_URL: z.string().url().default("https://api.github.com"),
  GITHUB_TOKEN: z
    .string()
    .transform((val) => val.trim())
    .transform((val) => (val.length > 0 ? val : undefined))
    .optional(),
  AI_SERVICE_URL: z
    .string()
    .transform((val) => {
      const trimmed = val.trim();
      if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
        return `https://${trimmed}`;
      }
      return trimmed;
    })
    .pipe(z.string().url())
    .default("http://localhost:5000"),
  AI_SERVICE_API_KEY: z
    .string()
    .transform((val) => val.trim())
    .refine((val) => val.length === 0 || val.length >= 16, {
      message: "AI_SERVICE_API_KEY must be at least 16 characters if provided",
    })
    .transform((val) => (val.length > 0 ? val : undefined))
    .optional(),
});

const parsed = environmentSchema.safeParse(process.env);

if (!parsed.success) {
  console.error("Invalid environment configuration", parsed.error.flatten().fieldErrors);
  throw new Error("Invalid environment configuration");
}

export const env = parsed.data;
