import logging

import uvicorn

from app.config import get_settings


import os

def main() -> None:
    settings = get_settings()
    port = int(os.environ.get("PORT", settings.ai_service_port))
    is_prod = settings.environment.lower() == "production"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=not is_prod)


if __name__ == "__main__":
    main()
