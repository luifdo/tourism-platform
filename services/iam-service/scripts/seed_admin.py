"""Crea el primer usuario Admin en iam_db. Es idempotente.

Uso: uv run python -m scripts.seed_admin
Lee ADMIN_EMAIL, ADMIN_PASSWORD y ADMIN_NOMBRE del entorno o del archivo .env.
"""

import asyncio
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.domain.value_objects.enums import Rol
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.persistence.models import Usuario
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher


class AdminSeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    admin_email: str = ""
    admin_password: str = ""
    admin_nombre: str = ""


async def seed_admin(email: str, password: str, nombre: str, database_url: str) -> bool:
    """Devuelve True si creó el usuario y False si ya existía uno con ese email."""
    engine = build_engine(database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            existente = await session.scalar(select(Usuario.id).where(Usuario.email == email))
            if existente is not None:
                return False

            session.add(
                Usuario(
                    email=email,
                    password_hash=Argon2PasswordHasher().hash(password),
                    nombre_completo=nombre,
                    rol=Rol.ADMIN,
                    email_verificado=True,
                    habeas_data_aceptado=True,
                    habeas_data_aceptado_en=func.now(),
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                # Otra ejecución lo creó entre el SELECT y el INSERT.
                return False
        return True
    finally:
        await engine.dispose()


def main() -> int:
    seed = AdminSeedSettings()
    faltantes = [
        nombre
        for nombre, valor in (
            ("ADMIN_EMAIL", seed.admin_email),
            ("ADMIN_PASSWORD", seed.admin_password),
            ("ADMIN_NOMBRE", seed.admin_nombre),
        )
        if not valor.strip()
    ]
    if faltantes:
        print(f"Faltan variables de entorno: {', '.join(faltantes)}", file=sys.stderr)
        return 1

    email = seed.admin_email.strip().lower()
    creado = asyncio.run(
        seed_admin(
            email, seed.admin_password, seed.admin_nombre.strip(), get_settings().database_url
        )
    )
    if creado:
        print(f"Usuario Admin creado: {email}")
    else:
        print(f"Ya existe un usuario con el email {email}; no se hizo ningún cambio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
