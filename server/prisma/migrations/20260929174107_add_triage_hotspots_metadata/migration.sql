-- AlterTable
ALTER TABLE "Analysis" ADD COLUMN     "metadata" JSONB;

-- AlterTable
ALTER TABLE "File" ADD COLUMN     "hotspotEvidence" JSONB;

-- AlterTable
ALTER TABLE "Issue" ADD COLUMN     "category" TEXT,
ADD COLUMN     "relatedIssueIds" JSONB,
ADD COLUMN     "triageConfidence" DOUBLE PRECISION,
ADD COLUMN     "triageReason" TEXT;
