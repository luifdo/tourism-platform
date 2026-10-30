from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["up", "down"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, CheckStatus]


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
