import { Router } from "express";

import * as repositoryController from "../controllers/repository.controller.js";
import { requireAuth } from "../middleware/auth.middleware.js";
import { validate } from "../middleware/validation.middleware.js";
import {
  bugLocalizeSchema,
  createRepositorySchema,
  fetchGitHubIssueSchema,
  issueAnalysisSchema,
  ragQuerySchema,
  repositoryParamsSchema,
} from "../validators/repository.validator.js";

export const repositoryRouter = Router();
repositoryRouter.use(requireAuth);
repositoryRouter.post("/", validate(createRepositorySchema), repositoryController.createRepository);
repositoryRouter.get("/", repositoryController.listRepositories);
repositoryRouter.post("/:id/index", validate(repositoryParamsSchema), repositoryController.indexRepository);
repositoryRouter.post("/:id/architecture", validate(repositoryParamsSchema), repositoryController.analyzeArchitecture);
repositoryRouter.post("/:id/query", validate(ragQuerySchema), repositoryController.queryRepository);
repositoryRouter.post("/:id/issues/analyze", validate(issueAnalysisSchema), repositoryController.analyzeIssue);
repositoryRouter.post("/:id/issues/sync", validate(repositoryParamsSchema), repositoryController.syncRepositoryIssues);
repositoryRouter.get("/:id/issues", validate(repositoryParamsSchema), repositoryController.getRepositoryIssues);
repositoryRouter.post("/:id/triage", validate(repositoryParamsSchema), repositoryController.triageRepositoryIssues);
repositoryRouter.get("/:id/triage", validate(repositoryParamsSchema), repositoryController.getTriageData);
repositoryRouter.post("/:id/hotspots/calculate", validate(repositoryParamsSchema), repositoryController.calculateHotspots);
repositoryRouter.get("/:id/hotspots", validate(repositoryParamsSchema), repositoryController.getHotspots);
repositoryRouter.post("/:id/readme/generate", validate(repositoryParamsSchema), repositoryController.generateReadme);
repositoryRouter.get("/:id/readme", validate(repositoryParamsSchema), repositoryController.getReadme);
repositoryRouter.post("/:id/bugs/localize", validate(bugLocalizeSchema), repositoryController.localizeBug);
repositoryRouter.get("/:id/bugs/github-issue/:issueNumber", validate(fetchGitHubIssueSchema), repositoryController.fetchGitHubIssue);
repositoryRouter.get("/:id/bugs/history", validate(repositoryParamsSchema), repositoryController.getBugMappingsHistory);
repositoryRouter.get("/:id", validate(repositoryParamsSchema), repositoryController.getRepository);
repositoryRouter.delete("/:id", validate(repositoryParamsSchema), repositoryController.deleteRepository);

