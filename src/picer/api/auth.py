"""HTTP Basic Auth dependency.

Set PICER_USER and PICER_PASSWORD environment variables to enable auth.
If PICER_PASSWORD is empty, all authenticated requests are accepted without
credentials (suitable for local-only use; set a password for LAN deployment).
"""
from __future__ import annotations

import os
import secrets
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)

_USER = os.environ.get("PICER_USER", "picer")
_PASS = os.environ.get("PICER_PASSWORD", "")


def require_auth(
    credentials: Annotated[Optional[HTTPBasicCredentials], Depends(_security)],
) -> str:
    if not _PASS:
        # Auth disabled — accept any request
        return credentials.username if credentials else "anonymous"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username.encode(), _USER.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), _PASS.encode())

    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
