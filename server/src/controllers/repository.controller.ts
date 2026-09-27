import type { RequestHandler } from "express";

import * as repositoryService from "../services/repository.service.js";
import * as aiService from "../services/ai.service.js";
import * as githubService from "../services/github.service.js";
import { prisma } from "../config/database.js";
import { ApiError } from "../utils/api-error.js";

export const createRepository: RequestHandler = async (req, res, next) => {
  try { res.status(201).json({ success: true, data: await repositoryService.createRepository(req.user!.id, req.body.githubUrl) }); } catch (error) { next(error); }
};

export const listRepositories: RequestHandler = async (req, res, next) => {
  try { res.status(200).json({ success: true, data: await repositoryService.listRepositories(req.user!.id) }); } catch (error) { next(error); }
};

export const getRepository: RequestHandler = async (req, res, next) => {
  try { res.status(200).json({ success: true, data: await repositoryService.getRepository(req.user!.id, req.params.id as string) }); } catch (error) { next(error); }
};

export const deleteRepository: RequestHandler = async (req, res, next) => {
  try {
    await repositoryService.deleteRepository(req.user!.id, req.params.id as string);
    res.status(200).json({ success: true, data: { message: "Repository deleted successfully" } });
  } catch (error) { next(error); }
};

export const indexRepository: RequestHandler = async (req, res, next) => {
  try {
    const files = await repositoryService.getRepositoryFilesForAi(req.user!.id, req.params.id as string);
    res.status(200).json({ success: true, data: await aiService.indexRepositoryWithAi(req.params.id as string, files) });
  } catch (error) { next(error); }
};

export const analyzeArchitecture: RequestHandler = async (req, res, next) => {
  try {
    const files = await repositoryService.getRepositoryFilesForAi(req.user!.id, req.params.id as string);
    res.status(200).json({ success: true, data: await aiService.analyzeArchitectureWithAi(req.params.id as string, files) });
  } catch (error) { next(error); }
};

export const queryRepository: RequestHandler = async (req, res, next) => {
  try {
    const files = await repositoryService.getRepositoryFilesForAi(req.user!.id, req.params.id as string);
    res.status(200).json({ success: true, data: await aiService.queryRepositoryWithAi(req.params.id as string, req.body.question, files, req.body.topK) });
  } catch (error) { next(error); }
};

export const analyzeIssue: RequestHandler = async (req, res, next) => {
  try {
    await repositoryService.getRepository(req.user!.id, req.params.id as string);
    res.status(200).json({ success: true, data: await aiService.analyzeIssueWithAi(req.params.id as string, req.body) });
  } catch (error) { next(error); }
};

export const localizeBug: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const files = await repositoryService.getRepositoryFilesForAi(req.user!.id, req.params.id as string);

    // Optional commit history fetching
    let commits: githubService.GitHubCommit[] = [];
    try {
      commits = await githubService.getRecentCommits({ owner: repo.githubOwner, name: repo.name });
    } catch {
      // Proceed gracefully without commit history
    }

    const result = await aiService.localizeBugWithAi(
      req.params.id as string,
      { number: req.body.number, title: req.body.title, body: req.body.body },
      files,
      commits,
      req.body.topK,
      req.body.includeExplanation
    );

    // Persist to PostgreSQL database asynchronously
    await persistBugLocalization(req.params.id as string, req.body, result);

    res.status(200).json({ success: true, data: result });
  } catch (error) {
    next(error);
  }
};

export const fetchGitHubIssue: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const issue = await githubService.getGitHubIssue(
      { owner: repo.githubOwner, name: repo.name },
      Number(req.params.issueNumber)
    );
    if (!issue) {
      throw new ApiError(404, `Issue #${req.params.issueNumber} not found on GitHub`, "ISSUE_NOT_FOUND");
    }
    res.status(200).json({ success: true, data: issue });
  } catch (error) {
    next(error);
  }
};

export const getBugMappingsHistory: RequestHandler = async (req, res, next) => {
  try {
    await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const issues = await prisma.issue.findMany({
      where: { repositoryId: req.params.id as string },
      include: {
        fileMappings: {
          include: { file: { select: { path: true, name: true, language: true } } },
          orderBy: { rank: "asc" },
        },
      },
      orderBy: { createdAt: "desc" },
      take: 20,
    });
    res.status(200).json({ success: true, data: issues });
  } catch (error) {
    next(error);
  }
};

async function persistBugLocalization(
  repositoryId: string,
  issueInput: { number: number; title: string; body?: string },
  result: aiService.AiBugLocalizationResult
) {
  try {
    const issue = await prisma.issue.upsert({
      where: {
        repositoryId_githubIssueId: {
          repositoryId,
          githubIssueId: String(issueInput.number),
        },
      },
      create: {
        repositoryId,
        githubIssueId: String(issueInput.number),
        number: issueInput.number,
        title: issueInput.title,
        body: issueInput.body ?? null,
        state: "open",
      },
      update: {
        title: issueInput.title,
        body: issueInput.body ?? null,
      },
    });

    // Delete existing mappings for this issue to prevent rank constraint collision
    await prisma.issueFileMapping.deleteMany({
      where: { issueId: issue.id },
    });

    const existingFiles = await prisma.file.findMany({
      where: { repositoryId },
      select: { id: true, path: true },
    });
    const fileIdMap = new Map<string, string>(existingFiles.map((f) => [f.path, f.id]));

    for (const candidate of result.candidates) {
      const fileId = fileIdMap.get(candidate.file_path) || candidate.file_id;
      if (!fileId) continue;

      await prisma.issueFileMapping.create({
        data: {
          repositoryId,
          issueId: issue.id,
          fileId,
          score: candidate.final_score,
          confidence: candidate.confidence,
          rank: candidate.rank,
          semanticSimilarity: candidate.signals.semantic_similarity,
          keywordSimilarity: candidate.signals.keyword_score,
          dependencyScore: candidate.signals.dependency_score,
          historicalScore: candidate.signals.historical_score,
          explanation: candidate.explanation,
        },
      });
    }

    await prisma.analysis.create({
      data: {
        repositoryId,
        type: "BUG_FILE_MAPPING",
        status: "COMPLETED",
        progress: 100,
        startedAt: new Date(),
        completedAt: new Date(),
      },
    });
  } catch (err) {
    console.error("Failed to persist bug localization results:", err);
  }
}
