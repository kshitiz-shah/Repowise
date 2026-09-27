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

export const syncRepositoryIssues: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const githubIssues = await githubService.getOpenIssues({ owner: repo.githubOwner, name: repo.name }, 50);

    const synced = await Promise.all(
      githubIssues.map(async (item) => {
        return prisma.issue.upsert({
          where: {
            repositoryId_githubIssueId: {
              repositoryId: repo.id,
              githubIssueId: String(item.number),
            },
          },
          create: {
            repositoryId: repo.id,
            githubIssueId: String(item.number),
            number: item.number,
            title: item.title,
            body: item.body,
            state: item.state,
            labels: item.labels,
            author: item.author,
            githubCreatedAt: item.createdAt ? new Date(item.createdAt) : null,
            githubUpdatedAt: item.updatedAt ? new Date(item.updatedAt) : null,
          },
          update: {
            title: item.title,
            body: item.body,
            state: item.state,
            labels: item.labels,
            author: item.author,
            githubUpdatedAt: item.updatedAt ? new Date(item.updatedAt) : null,
          },
        });
      })
    );

    res.status(200).json({ success: true, data: { synced_count: synced.length, issues: synced } });
  } catch (error) {
    next(error);
  }
};

export const getRepositoryIssues: RequestHandler = async (req, res, next) => {
  try {
    await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const issues = await prisma.issue.findMany({
      where: { repositoryId: req.params.id as string },
      include: {
        fileMappings: {
          include: { file: { select: { path: true, name: true, language: true } } },
          orderBy: { rank: "asc" },
          take: 3,
        },
      },
      orderBy: [{ severity: "asc" }, { number: "desc" }],
    });
    res.status(200).json({ success: true, data: issues });
  } catch (error) {
    next(error);
  }
};

export const triageRepositoryIssues: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    let issues = await prisma.issue.findMany({
      where: { repositoryId: repo.id },
      orderBy: { number: "desc" },
    });

    if (issues.length === 0) {
      try {
        const ghIssues = await githubService.getOpenIssues({ owner: repo.githubOwner, name: repo.name }, 50);
        if (ghIssues.length > 0) {
          await Promise.all(
            ghIssues.map((item) =>
              prisma.issue.upsert({
                where: {
                  repositoryId_githubIssueId: {
                    repositoryId: repo.id,
                    githubIssueId: String(item.number),
                  },
                },
                create: {
                  repositoryId: repo.id,
                  githubIssueId: String(item.number),
                  number: item.number,
                  title: item.title,
                  body: item.body,
                  state: item.state,
                  labels: item.labels,
                  author: item.author,
                  githubCreatedAt: item.createdAt ? new Date(item.createdAt) : null,
                  githubUpdatedAt: item.updatedAt ? new Date(item.updatedAt) : null,
                },
                update: {
                  title: item.title,
                  body: item.body,
                  state: item.state,
                  labels: item.labels,
                  author: item.author,
                  githubUpdatedAt: item.updatedAt ? new Date(item.updatedAt) : null,
                },
              })
            )
          );
          issues = await prisma.issue.findMany({
            where: { repositoryId: repo.id },
            orderBy: { number: "desc" },
          });
        }
      } catch (err) {
        console.warn("Could not auto-sync GitHub issues before triage:", err);
      }
    }

    if (issues.length === 0) {
      res.status(200).json({
        success: true,
        data: {
          summary: {
            total_issues: 0,
            critical_count: 0,
            high_count: 0,
            medium_count: 0,
            low_count: 0,
            unknown_count: 0,
            duplicate_groups_count: 0,
            categories_breakdown: {},
          },
          issues: [],
        },
      });
      return;
    }

    const files = await prisma.file.findMany({
      where: { repositoryId: repo.id },
      select: { path: true },
      take: 100,
    });
    const componentNames = Array.from(new Set(files.map((f) => f.path.split("/")[0]).filter(Boolean)));

    const triageResult = await aiService.triageIssuesWithAi(
      repo.id,
      issues.map((i) => ({
        number: i.number,
        title: i.title,
        body: i.body,
        labels: Array.isArray(i.labels) ? (i.labels as string[]) : [],
      })),
      componentNames
    );

    for (const item of triageResult.issues) {
      await prisma.issue.updateMany({
        where: {
          repositoryId: repo.id,
          number: item.number,
        },
        data: {
          severity: item.severity,
          category: item.category,
          triageReason: item.reason,
          triageConfidence: item.confidence,
          relatedIssueIds: item.related_issues.map((r) => r.number),
        },
      });
    }

    await prisma.analysis.create({
      data: {
        repositoryId: repo.id,
        type: "BUG_TRIAGE",
        status: "COMPLETED",
        progress: 100,
        startedAt: new Date(),
        completedAt: new Date(),
      },
    });

    const updatedIssues = await prisma.issue.findMany({
      where: { repositoryId: repo.id },
      include: {
        fileMappings: {
          include: { file: { select: { path: true, name: true, language: true } } },
          orderBy: { rank: "asc" },
          take: 3,
        },
      },
      orderBy: [{ severity: "asc" }, { number: "desc" }],
    });

    res.status(200).json({
      success: true,
      data: {
        summary: triageResult.summary,
        issues: updatedIssues,
        triaged_details: triageResult.issues,
      },
    });
  } catch (error) {
    next(error);
  }
};

export const getTriageData: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const issues = await prisma.issue.findMany({
      where: { repositoryId: repo.id },
      include: {
        fileMappings: {
          include: { file: { select: { path: true, name: true, language: true } } },
          orderBy: { rank: "asc" },
          take: 3,
        },
      },
      orderBy: [{ severity: "asc" }, { number: "desc" }],
    });

    const summary = {
      total_issues: issues.length,
      critical_count: issues.filter((i) => i.severity === "CRITICAL").length,
      high_count: issues.filter((i) => i.severity === "HIGH").length,
      medium_count: issues.filter((i) => i.severity === "MEDIUM").length,
      low_count: issues.filter((i) => i.severity === "LOW").length,
      unknown_count: issues.filter((i) => !i.severity || i.severity === "UNKNOWN").length,
      duplicate_groups_count: issues.filter((i) => Array.isArray(i.relatedIssueIds) && i.relatedIssueIds.length > 0).length,
      categories_breakdown: issues.reduce<Record<string, number>>((acc, i) => {
        const cat = i.category || "Uncategorized";
        acc[cat] = (acc[cat] || 0) + 1;
        return acc;
      }, {}),
    };

    res.status(200).json({
      success: true,
      data: {
        summary,
        issues,
      },
    });
  } catch (error) {
    next(error);
  }
};

export const calculateHotspots: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const files = await prisma.file.findMany({
      where: { repositoryId: repo.id },
    });

    if (files.length === 0) {
      res.status(200).json({
        success: true,
        data: {
          repository_id: repo.id,
          components: [],
          files: [],
          high_risk_count: 0,
          medium_risk_count: 0,
          low_risk_count: 0,
        },
      });
      return;
    }

    let commits: githubService.GitHubCommit[] = [];
    try {
      commits = await githubService.getRecentCommits({ owner: repo.githubOwner, name: repo.name }, 50);
    } catch (err) {
      console.warn("Could not fetch recent commits for hotspots:", err);
    }

    const bugMappings = await prisma.issueFileMapping.findMany({
      where: { repositoryId: repo.id },
      include: { file: { select: { path: true } }, issue: { select: { number: true } } },
    });

    const dependencies = await prisma.dependency.findMany({
      where: { repositoryId: repo.id },
      include: { sourceFile: { select: { path: true } }, targetFile: { select: { path: true } } },
    });

    const hotspotResult = await aiService.calculateHotspotsWithAi(repo.id, {
      files: files.map((f) => ({
        id: f.id,
        path: f.path,
        name: f.name,
        language: f.language,
        lines_of_code: f.linesOfCode || 0,
        size: f.size || 0,
      })),
      commits: commits.map((c) => ({
        sha: c.sha,
        message: c.message,
        author: c.author,
        date: c.date,
        files: c.files.map((cf) => cf.filename),
      })),
      bug_mappings: bugMappings.map((bm) => ({
        file_id: bm.fileId,
        file_path: bm.file.path,
        issue_number: bm.issue.number,
        score: bm.score,
      })),
      dependencies: dependencies.map((d) => ({
        source_path: d.sourceFile.path,
        target_path: d.targetFile.path,
        type: d.type,
      })),
    });

    for (const f of hotspotResult.files) {
      await prisma.file.updateMany({
        where: { id: f.id },
        data: {
          churnScore: f.churn_score,
          riskScore: f.risk_score,
          hotspotEvidence: f.evidence as any,
        },
      });
    }

    await prisma.analysis.create({
      data: {
        repositoryId: repo.id,
        type: "HOTSPOTS",
        status: "COMPLETED",
        progress: 100,
        startedAt: new Date(),
        completedAt: new Date(),
      },
    });

    res.status(200).json({ success: true, data: hotspotResult });
  } catch (error) {
    next(error);
  }
};

export const getHotspots: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const files = await prisma.file.findMany({
      where: { repositoryId: repo.id },
      orderBy: { riskScore: "desc" },
    });

    const hasCalculated = files.some((f) => f.riskScore !== null && f.riskScore !== undefined);
    if (!hasCalculated && files.length > 0) {
      return calculateHotspots(req, res, next);
    }

    const fileResults = files.map((f) => {
      const riskScore = f.riskScore || 0;
      const churnScore = f.churnScore || 0;
      let riskLevel: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" = "LOW";
      if (riskScore >= 0.65) riskLevel = "CRITICAL";
      else if (riskScore >= 0.45) riskLevel = "HIGH";
      else if (riskScore >= 0.25) riskLevel = "MEDIUM";

      const evidence = (f.hotspotEvidence as any) || {
        churn_commits: 0,
        bug_associations: 0,
        bug_fix_commits: 0,
        in_degree: 0,
        drivers: ["No risk telemetry recorded yet."],
      };

      const parts = f.path.split("/");
      const componentName = parts.length > 1 ? parts[0] : "root";

      return {
        id: f.id,
        path: f.path,
        name: f.name,
        language: f.language,
        lines_of_code: f.linesOfCode || 0,
        churn_score: churnScore,
        risk_score: riskScore,
        risk_level: riskLevel,
        bug_count: evidence.bug_associations || 0,
        component_name: componentName,
        evidence,
      };
    });

    const componentGroups = new Map<string, typeof fileResults>();
    for (const fr of fileResults) {
      const comp = fr.component_name || "root";
      const list = componentGroups.get(comp) || [];
      list.push(fr);
      componentGroups.set(comp, list);
    }

    const components = Array.from(componentGroups.entries()).map(([name, compFiles]) => {
      const avgRisk = compFiles.reduce((acc, cf) => acc + cf.risk_score, 0) / compFiles.length;
      const maxRisk = Math.max(...compFiles.map((cf) => cf.risk_score));
      const totalChurn = compFiles.reduce((acc, cf) => acc + (cf.evidence.churn_commits || 0), 0);
      const totalBugs = compFiles.reduce((acc, cf) => acc + cf.bug_count, 0);

      let riskLevel: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" = "LOW";
      if (maxRisk >= 0.7 || avgRisk >= 0.5) riskLevel = "CRITICAL";
      else if (maxRisk >= 0.5 || avgRisk >= 0.35) riskLevel = "HIGH";
      else if (avgRisk >= 0.2) riskLevel = "MEDIUM";

      return {
        name,
        risk_level: riskLevel,
        avg_risk_score: Number(avgRisk.toFixed(4)),
        max_risk_score: Number(maxRisk.toFixed(4)),
        file_count: compFiles.length,
        total_churn: totalChurn,
        total_bug_density: totalBugs,
      };
    });

    components.sort((a, b) => b.avg_risk_score - a.avg_risk_score);

    const highRiskCount = fileResults.filter((f) => f.risk_level === "CRITICAL" || f.risk_level === "HIGH").length;
    const medRiskCount = fileResults.filter((f) => f.risk_level === "MEDIUM").length;
    const lowRiskCount = fileResults.filter((f) => f.risk_level === "LOW").length;

    res.status(200).json({
      success: true,
      data: {
        repository_id: repo.id,
        components,
        files: fileResults,
        high_risk_count: highRiskCount,
        medium_risk_count: medRiskCount,
        low_risk_count: lowRiskCount,
      },
    });
  } catch (error) {
    next(error);
  }
};

export const generateReadme: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const sourceFiles = await repositoryService.getRepositoryFilesForAi(req.user!.id, req.params.id as string);
    const configFiles = await githubService.getRepositoryConfigFiles({
      owner: repo.githubOwner,
      name: repo.name,
      defaultBranch: repo.defaultBranch,
    });
    const existingReadme = await githubService.getExistingReadme({
      owner: repo.githubOwner,
      name: repo.name,
    });

    const configPaths = new Set(configFiles.map((c) => c.path));
    const allFiles = [...configFiles, ...sourceFiles.filter((s) => !configPaths.has(s.path))];

    const result = await aiService.generateReadmeWithAi(repo.id, {
      repository_name: repo.name,
      owner: repo.githubOwner,
      description: repo.description,
      primary_language: repo.primaryLanguage,
      files: allFiles,
      existing_readme: existingReadme,
    });

    await prisma.analysis.create({
      data: {
        repositoryId: repo.id,
        type: "DOCUMENTATION",
        status: "COMPLETED",
        progress: 100,
        startedAt: new Date(),
        completedAt: new Date(),
        metadata: result as any,
      },
    });

    res.status(200).json({ success: true, data: result });
  } catch (error) {
    next(error);
  }
};

export const getReadme: RequestHandler = async (req, res, next) => {
  try {
    const repo = await repositoryService.getRepository(req.user!.id, req.params.id as string);
    const analysis = await prisma.analysis.findFirst({
      where: {
        repositoryId: repo.id,
        type: "DOCUMENTATION",
        status: "COMPLETED",
      },
      orderBy: { createdAt: "desc" },
    });

    if (analysis && analysis.metadata) {
      res.status(200).json({ success: true, data: analysis.metadata });
      return;
    }

    const existing = await githubService.getExistingReadme({
      owner: repo.githubOwner,
      name: repo.name,
    });

    res.status(200).json({
      success: true,
      data: {
        existing_readme: existing,
      },
    });
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
