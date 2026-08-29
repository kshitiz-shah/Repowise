import { describe, expect, it } from "vitest";

import { hashPassword, verifyPassword } from "../src/utils/password.js";
import { loginSchema, registerSchema } from "../src/validators/auth.validator.js";

describe("authentication foundation", () => {
  it("hashes a password and verifies it without storing plaintext", async () => {
    const password = "StrongPassword123!";
    const hash = await hashPassword(password);

    expect(hash).not.toContain(password);
    await expect(verifyPassword(password, hash)).resolves.toBe(true);
    await expect(verifyPassword("WrongPassword123!", hash)).resolves.toBe(false);
  });

  it("rejects registration passwords that do not meet the policy", () => {
    const result = registerSchema.safeParse({
      body: { name: "John", email: "john@example.com", password: "weakpassword" },
      query: {}, params: {},
    });
    expect(result.success).toBe(false);
  });

  it("rejects malformed login requests", () => {
    const result = loginSchema.safeParse({ body: { email: "not-an-email", password: "" }, query: {}, params: {} });
    expect(result.success).toBe(false);
  });
});
