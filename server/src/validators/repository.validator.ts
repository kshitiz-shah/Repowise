import { z } from "zod";

const repositoryId = z.string().uuid();

export const createRepositorySchema = z.object({
  body: z.object({ githubUrl: z.string().trim().url().max(2048) }),
  query: z.object({}),
  params: z.object({}),
});

export const repositoryParamsSchema = z.object({
  body: z.object({}),
  query: z.object({}),
  params: z.object({ id: repositoryId }),
});

export const ragQuerySchema = z.object({
  body: z.object({ question: z.string().trim().min(3).max(10_000), topK: z.number().int().min(1).max(20).optional() }),
  query: z.object({}), params: z.object({ id: repositoryId }),
});

export const issueAnalysisSchema = z.object({
  body: z.object({ number: z.number().int().positive(), title: z.string().trim().min(1).max(500), body: z.string().max(50_000).optional() }),
  query: z.object({}), params: z.object({ id: repositoryId }),
});
