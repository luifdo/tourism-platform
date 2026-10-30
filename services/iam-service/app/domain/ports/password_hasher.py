from typing import Protocol


class PasswordHasher(Protocol):
    """Deriva y verifica hashes de contraseñas.

    `hash` y `verify` bloquean mientras calculan. Los casos de uso, que corren en el bucle de
    eventos, usan siempre las versiones `_limitado`, que lanzan ServicioOcupadoError si la
    espera por un cupo se agota (C-53).
    """

    def hash(self, plain: str) -> str: ...

    def verify(self, plain: str, hashed: str) -> bool: ...

    async def hash_limitado(self, plain: str) -> str:
        """`hash` fuera del bucle de eventos y con los cálculos simultáneos acotados."""
        ...

    async def verify_limitado(self, plain: str, hashed: str) -> bool:
        """`verify` fuera del bucle de eventos y con los cálculos simultáneos acotados."""
        ...

    def needs_rehash(self, hashed: str) -> bool:
        """True si el hash se generó con parámetros distintos a los actuales."""
        ...
