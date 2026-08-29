import type { RequestHandler } from "express";
import type { ZodType } from "zod";

export const validate = (schema: ZodType): RequestHandler => (req, _res, next) => {
  const result = schema.safeParse({ body: req.body, query: req.query, params: req.params });
  if (!result.success) return next(result.error);
  req.body = result.data.body;
  req.params = result.data.params;
  return next();
};
