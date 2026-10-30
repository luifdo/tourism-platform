import uuid

from app.domain.exceptions import TokenInvalidoError
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.token_service import TokenService
from app.domain.value_objects.token import ClaimsToken


class VerificarAcceso:
    """RF-09: valida el access token (firma, expiración, tipo y revocación). Sin PostgreSQL.

    Lo usan el ForwardAuth del Gateway, require_role y el logout.
    """

    def __init__(self, tokens: TokenService, revocacion: RevocacionTokens) -> None:
        self._tokens = tokens
        self._revocacion = revocacion

    async def execute(self, token: str | None) -> ClaimsToken:
        if token is None:
            raise TokenInvalidoError(motivo="sin_token")
        claims = self._tokens.verificar(token)
        try:
            usuario_id = uuid.UUID(claims.sub)
        except ValueError as exc:
            raise TokenInvalidoError(motivo="invalido") from exc
        if await self._revocacion.esta_revocado_token(claims.jti, usuario_id, claims.iat):
            raise TokenInvalidoError(motivo="revocado", usuario_id=usuario_id)
        return claims
