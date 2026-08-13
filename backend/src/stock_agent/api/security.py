"""Authentication + authorization primitives.

Two mechanisms supported by default:
  * Bearer JWT — for the React front-end (issued by an external identity
    provider or the `POST /auth/token` route in the future).
  * `X-Admin-Key` header — for the scheduler and CLI to invoke privileged
    endpoints. This is a shared secret loaded from env, rotated externally.

Any endpoint that mutates state MUST depend on `require_actor()`.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, Request
from jose import JWTError, jwt

from stock_agent.config import get_settings
from stock_agent.errors import ForbiddenError, UnauthorizedError


@dataclass(frozen=True, slots=True)
class Actor:
    subject: str
    role: str


def _decode_bearer(authorization: str) -> Actor:
    settings = get_settings()
    if not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("缺少 Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise UnauthorizedError("Bearer token 无效", details={"cause": str(exc)}) from exc
    return Actor(subject=str(claims.get("sub", "unknown")), role=str(claims.get("role", "viewer")))


def require_actor(
    request: Request,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> Actor:
    del request  # kept for signature consistency; may be used to log request_id
    settings = get_settings()
    if x_admin_key is not None:
        if x_admin_key == settings.admin_api_key.get_secret_value():
            return Actor(subject="admin", role="admin")
        raise UnauthorizedError("X-Admin-Key 无效")
    if authorization is not None:
        return _decode_bearer(authorization)
    raise UnauthorizedError("缺少认证凭证")


def require_admin(actor: Actor = Depends(require_actor)) -> Actor:
    if actor.role != "admin":
        raise ForbiddenError("需要 admin 权限")
    return actor
