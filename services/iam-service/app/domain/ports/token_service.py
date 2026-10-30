from typing import Protocol

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.token import ClaimsToken, TokenEmitido


class TokenService(Protocol):
    def emitir(self, usuario: Usuario) -> TokenEmitido: ...

    def verificar(self, token: str) -> ClaimsToken:
        """Lanza TokenInvalidoError si la firma, el emisor, el algoritmo o la expiración fallan."""
        ...
