import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_service_key(authorization: str | None = Header(default=None)) -> None:
    """Allow only the Node backend (or an explicitly configured trusted caller)."""
    expected = get_settings().ai_service_api_key.get_secret_value()
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Service authentication required")

    provided = authorization[len(prefix) :]
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service key")
