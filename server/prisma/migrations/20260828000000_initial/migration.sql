-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "RepositoryRole" AS ENUM ('OWNER', 'MEMBER', 'VIEWER');

-- CreateEnum
CREATE TYPE "RepositoryStatus" AS ENUM ('PENDING', 'CLONING', 'ANALYZING', 'COMPLETED', 'FAILED');

-- CreateEnum
CREATE TYPE "DependencyType" AS ENUM ('IMPORT', 'REQUIRE', 'INHERITANCE', 'CALL', 'REFERENCE');

-- CreateEnum
CREATE TYPE "IssueSeverity" AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "AnalysisType" AS ENUM ('ARCHITECTURE', 'RAG', 'BUG_TRIAGE', 'BUG_FILE_MAPPING', 'HOTSPOTS', 'DOCUMENTATION');

-- CreateEnum
CREATE TYPE "AnalysisStatus" AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuthSession" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "refreshTokenHash" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuthSession_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Repository" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "githubOwner" TEXT NOT NULL,
    "githubUrl" TEXT NOT NULL,
    "description" TEXT,
    "defaultBranch" TEXT,
    "primaryLanguage" TEXT,
    "status" "RepositoryStatus" NOT NULL DEFAULT 'PENDING',
    "analysisProgress" INTEGER NOT NULL DEFAULT 0,
    "lastAnalyzedAt" TIMESTAMP(3),
    "ownerId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Repository_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RepositoryMembership" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "repositoryId" TEXT NOT NULL,
    "role" "RepositoryRole" NOT NULL DEFAULT 'VIEWER',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RepositoryMembership_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "File" (
    "id" TEXT NOT NULL,
    "repositoryId" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "extension" TEXT,
    "language" TEXT,
    "type" TEXT,
    "linesOfCode" INTEGER,
    "size" INTEGER,
    "churnScore" DOUBLE PRECISION,
    "riskScore" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "File_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Dependency" (
    "id" TEXT NOT NULL,
    "repositoryId" TEXT NOT NULL,
    "sourceFileId" TEXT NOT NULL,
    "targetFileId" TEXT NOT NULL,
    "type" "DependencyType" NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Dependency_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Issue" (
    "id" TEXT NOT NULL,
    "repositoryId" TEXT NOT NULL,
    "githubIssueId" TEXT NOT NULL,
    "number" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "body" TEXT,
    "state" TEXT NOT NULL,
    "labels" JSONB,
    "author" TEXT,
    "githubCreatedAt" TIMESTAMP(3),
    "githubUpdatedAt" TIMESTAMP(3),
    "severity" "IssueSeverity" NOT NULL DEFAULT 'UNKNOWN',
    "severityScore" DOUBLE PRECISION,
    "duplicateGroupId" TEXT,
    "isDuplicate" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Issue_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "IssueFileMapping" (
    "id" TEXT NOT NULL,
    "repositoryId" TEXT NOT NULL,
    "issueId" TEXT NOT NULL,
    "fileId" TEXT NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    "confidence" DOUBLE PRECISION,
    "rank" INTEGER NOT NULL,
    "semanticSimilarity" DOUBLE PRECISION,
    "keywordSimilarity" DOUBLE PRECISION,
    "dependencyScore" DOUBLE PRECISION,
    "historicalScore" DOUBLE PRECISION,
    "explanation" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "IssueFileMapping_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Analysis" (
    "id" TEXT NOT NULL,
    "repositoryId" TEXT NOT NULL,
    "type" "AnalysisType" NOT NULL,
    "status" "AnalysisStatus" NOT NULL DEFAULT 'PENDING',
    "progress" INTEGER NOT NULL DEFAULT 0,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "error" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Analysis_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE UNIQUE INDEX "AuthSession_refreshTokenHash_key" ON "AuthSession"("refreshTokenHash");

-- CreateIndex
CREATE INDEX "AuthSession_userId_idx" ON "AuthSession"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "Repository_githubUrl_key" ON "Repository"("githubUrl");

-- CreateIndex
CREATE INDEX "Repository_ownerId_idx" ON "Repository"("ownerId");

-- CreateIndex
CREATE INDEX "RepositoryMembership_repositoryId_idx" ON "RepositoryMembership"("repositoryId");

-- CreateIndex
CREATE UNIQUE INDEX "RepositoryMembership_userId_repositoryId_key" ON "RepositoryMembership"("userId", "repositoryId");

-- CreateIndex
CREATE UNIQUE INDEX "File_repositoryId_path_key" ON "File"("repositoryId", "path");

-- CreateIndex
CREATE INDEX "Dependency_repositoryId_idx" ON "Dependency"("repositoryId");

-- CreateIndex
CREATE UNIQUE INDEX "Dependency_sourceFileId_targetFileId_type_key" ON "Dependency"("sourceFileId", "targetFileId", "type");

-- CreateIndex
CREATE INDEX "Issue_repositoryId_number_idx" ON "Issue"("repositoryId", "number");

-- CreateIndex
CREATE UNIQUE INDEX "Issue_repositoryId_githubIssueId_key" ON "Issue"("repositoryId", "githubIssueId");

-- CreateIndex
CREATE INDEX "IssueFileMapping_repositoryId_idx" ON "IssueFileMapping"("repositoryId");

-- CreateIndex
CREATE UNIQUE INDEX "IssueFileMapping_issueId_fileId_key" ON "IssueFileMapping"("issueId", "fileId");

-- CreateIndex
CREATE UNIQUE INDEX "IssueFileMapping_issueId_rank_key" ON "IssueFileMapping"("issueId", "rank");

-- CreateIndex
CREATE INDEX "Analysis_repositoryId_status_idx" ON "Analysis"("repositoryId", "status");

-- AddForeignKey
ALTER TABLE "AuthSession" ADD CONSTRAINT "AuthSession_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Repository" ADD CONSTRAINT "Repository_ownerId_fkey" FOREIGN KEY ("ownerId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RepositoryMembership" ADD CONSTRAINT "RepositoryMembership_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RepositoryMembership" ADD CONSTRAINT "RepositoryMembership_repositoryId_fkey" FOREIGN KEY ("repositoryId") REFERENCES "Repository"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "File" ADD CONSTRAINT "File_repositoryId_fkey" FOREIGN KEY ("repositoryId") REFERENCES "Repository"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Dependency" ADD CONSTRAINT "Dependency_repositoryId_fkey" FOREIGN KEY ("repositoryId") REFERENCES "Repository"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Dependency" ADD CONSTRAINT "Dependency_sourceFileId_fkey" FOREIGN KEY ("sourceFileId") REFERENCES "File"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Dependency" ADD CONSTRAINT "Dependency_targetFileId_fkey" FOREIGN KEY ("targetFileId") REFERENCES "File"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Issue" ADD CONSTRAINT "Issue_repositoryId_fkey" FOREIGN KEY ("repositoryId") REFERENCES "Repository"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "IssueFileMapping" ADD CONSTRAINT "IssueFileMapping_repositoryId_fkey" FOREIGN KEY ("repositoryId") REFERENCES "Repository"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "IssueFileMapping" ADD CONSTRAINT "IssueFileMapping_issueId_fkey" FOREIGN KEY ("issueId") REFERENCES "Issue"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "IssueFileMapping" ADD CONSTRAINT "IssueFileMapping_fileId_fkey" FOREIGN KEY ("fileId") REFERENCES "File"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Analysis" ADD CONSTRAINT "Analysis_repositoryId_fkey" FOREIGN KEY ("repositoryId") REFERENCES "Repository"("id") ON DELETE CASCADE ON UPDATE CASCADE;

