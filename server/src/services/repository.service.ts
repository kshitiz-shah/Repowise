import { RepositoryRole } from "@prisma/client";
import path from "node:path";

import { prisma } from "../config/database.js";
import { ApiError } from "../utils/api-error.js";
import type { AiRepositoryFile } from "./ai.service.js";
import { getRepositoryMetadata, getRepositorySourceFiles, parseRepositoryUrl } from "./github.service.js";

const repositorySelect = {
  id: true, name: true, githubOwner: true, githubUrl: true, description: true, defaultBranch: true,
  primaryLanguage: true, status: true, analysisProgress: true, lastAnalyzedAt: true, ownerId: true,
  createdAt: true, updatedAt: true,
} as const;

export const createRepository = async (userId: string, githubUrl: string) => {
  const reference = parseRepositoryUrl(githubUrl);
  const existing = await prisma.repository.findUnique({
    where: { githubUrl: reference.canonicalUrl },
    include: { memberships: { where: { userId } } },
  });
  if (existing) {
    if (existing.memberships.length === 0 && existing.ownerId !== userId) {
      await prisma.repositoryMembership.create({
        data: {
          repositoryId: existing.id,
          userId,
          role: RepositoryRole.COLLABORATOR,
        },
      });
    }
    return prisma.repository.findUniqueOrThrow({
      where: { id: existing.id },
      select: repositorySelect,
    });
  }

  const metadata = await getRepositoryMetadata(reference.canonicalUrl);
  return prisma.repository.create({
    data: {
      name: metadata.name, githubOwner: metadata.owner, githubUrl: metadata.canonicalUrl,
      description: metadata.description, defaultBranch: metadata.defaultBranch, primaryLanguage: metadata.primaryLanguage,
      ownerId: userId,
      memberships: { create: { userId, role: RepositoryRole.OWNER } },
    },
    select: repositorySelect,
  });
};


export const listRepositories = (userId: string) => prisma.repository.findMany({
  where: { OR: [{ ownerId: userId }, { memberships: { some: { userId } } }] },
  select: repositorySelect,
  orderBy: { createdAt: "desc" },
});

export const getRepository = async (userId: string, repositoryId: string) => {
  const repository = await prisma.repository.findFirst({
    where: { id: repositoryId, OR: [{ ownerId: userId }, { memberships: { some: { userId } } }] },
    select: repositorySelect,
  });
  if (!repository) throw new ApiError(404, "Repository not found", "REPOSITORY_NOT_FOUND");
  return repository;
};

export const ensureRepositoryPermission = async (userId: string, repositoryId: string, allowedRoles: RepositoryRole[]) => {
  const repository = await prisma.repository.findUnique({
    where: { id: repositoryId },
    select: { ownerId: true, memberships: { where: { userId }, select: { role: true } } },
  });
  if (!repository) throw new ApiError(404, "Repository not found", "REPOSITORY_NOT_FOUND");
  const role = repository.ownerId === userId ? RepositoryRole.OWNER : repository.memberships[0]?.role;
  if (!role || !allowedRoles.includes(role)) throw new ApiError(403, "You do not have permission to access this repository", "FORBIDDEN");
};

export const deleteRepository = async (userId: string, repositoryId: string) => {
  await ensureRepositoryPermission(userId, repositoryId, [RepositoryRole.OWNER]);
  await prisma.repository.delete({ where: { id: repositoryId } });
};

export const getRepositoryFilesForAi = async (userId: string, repositoryId: string): Promise<AiRepositoryFile[]> => {
  const repository = await getRepository(userId, repositoryId);
  const sourceFiles = await getRepositorySourceFiles({ owner: repository.githubOwner, name: repository.name, defaultBranch: repository.defaultBranch });
  return Promise.all(sourceFiles.map(async (source) => {
    const extension = path.posix.extname(source.path).toLowerCase() || null;
    const file = await prisma.file.upsert({
      where: { repositoryId_path: { repositoryId, path: source.path } },
      create: { repositoryId, path: source.path, name: path.posix.basename(source.path), extension, size: source.size, linesOfCode: source.content.split("\n").length },
      update: { extension, size: source.size, linesOfCode: source.content.split("\n").length },
      select: { id: true, path: true },
    });
    return { file_id: file.id, path: file.path, content: source.content };
  }));
};
