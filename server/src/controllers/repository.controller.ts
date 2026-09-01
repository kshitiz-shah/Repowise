import type { RequestHandler } from "express";

import * as repositoryService from "../services/repository.service.js";
import * as aiService from "../services/ai.service.js";

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
