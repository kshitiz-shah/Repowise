import { Router } from "express";

import { authRouter } from "./auth.routes.js";
import { repositoryRouter } from "./repository.routes.js";

export const apiRouter = Router();

apiRouter.get("/health", (_req, res) => {
  res.status(200).json({ success: true, data: { status: "ok", service: "repowise-backend" } });
});

apiRouter.use("/auth", authRouter);
apiRouter.use("/repositories", repositoryRouter);
