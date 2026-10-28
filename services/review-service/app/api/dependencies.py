"""Cableado de casos de uso con sus adaptadores.

Los adaptadores (engine, sesiones) se crean una vez en el lifespan de `main.py` y viven en
`app.state`; aquí solo se arman los casos de uso por petición. Las pruebas reemplazan estas
funciones con `app.dependency_overrides`.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.use_cases.check_health import CheckHealth
from app.config import Settings, get_settings
from app.infrastructure.persistence.database import SqlAlchemyDatabaseProbe


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_check_health(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckHealth:
    probe = SqlAlchemyDatabaseProbe(engine, settings.database_health_timeout_seconds)
    return CheckHealth(database=probe)
