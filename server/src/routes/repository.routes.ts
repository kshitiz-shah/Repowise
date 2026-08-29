import { Router } from "express";

import * as repositoryController from "../controllers/repository.controller.js";
import { requireAuth } from "../middleware/auth.middleware.js";
import { validate } from "../middleware/validation.middleware.js";
import { createRepositorySchema, issueAnalysisSchema, ragQuerySchema, repositoryParamsSchema } from "../validators/repository.validator.js";

export const repositoryRouter = Router();
repositoryRouter.use(requireAuth);
repositoryRouter.post("/", validate(createRepositorySchema), repositoryController.createRepository);
repositoryRouter.get("/", repositoryController.listRepositories);
repositoryRouter.post("/:id/index", validate(repositoryParamsSchema), repositoryController.indexRepository);
repositoryRouter.post("/:id/architecture", validate(repositoryParamsSchema), repositoryController.analyzeArchitecture);
repositoryRouter.post("/:id/query", validate(ragQuerySchema), repositoryController.queryRepository);
repositoryRouter.post("/:id/issues/analyze", validate(issueAnalysisSchema), repositoryController.analyzeIssue);
repositoryRouter.get("/:id", validate(repositoryParamsSchema), repositoryController.getRepository);
repositoryRouter.delete("/:id", validate(repositoryParamsSchema), repositoryController.deleteRepository);
