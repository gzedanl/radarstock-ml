import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, status


def verify_internal_token(x_internal_token: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("INTERNAL_SERVICE_TOKEN")
    # hmac.compare_digest en vez de != — comparación en tiempo
    # constante, no filtra el token byte a byte por timing.
    if (
        not expected
        or not x_internal_token
        or not hmac.compare_digest(x_internal_token, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token interno inválido o faltante",
        )
