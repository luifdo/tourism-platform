from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.domain.value_objects.enums import Rol
from app.infrastructure.security.jwt_token_service import JwtTokenService
from tests.api.conftest import TOKEN_INVALIDO, bearer, emitir, unico_denegado, usuario
from tests.conftest import LlavesRsa, crear_token_service, generar_llaves_rsa
from tests.fakes import FakeRevocacion, FakeUnitOfWork

VERIFICAR = "/api/iam/auth/verificar"
# Lo que Traefik agrega a la petición de ForwardAuth.
TRAEFIK = {"X-Forwarded-Method": "POST", "X-Forwarded-Uri": "/api/bookings/reservas?pagina=2"}


def verificar(client: TestClient, token: str | None = None) -> httpx.Response:
    headers = {**TRAEFIK, **(bearer(token) if token is not None else {})}
    return client.get(VERIFICAR, headers=headers)


def assert_401(response: httpx.Response) -> None:
    assert response.status_code == 401
    assert response.json() == TOKEN_INVALIDO
    assert response.headers["WWW-Authenticate"] == "Bearer"


def assert_fila(uow: FakeUnitOfWork, motivo: str, usuario_id: object = None) -> None:
    registro = unico_denegado(uow)
    assert registro.usuario_id == usuario_id
    # El query string no llega a la bitácora.
    assert registro.detalles == {
        "motivo": motivo,
        "metodo": "POST",
        "uri": "/api/bookings/reservas",
    }
    assert uow.commits == 1


def test_token_valido_200_con_identidad_y_sin_postgresql(
    client: TestClient, uow: FakeUnitOfWork
) -> None:
    emitido, u = emitir(client, Rol.PRESTADOR)

    response = verificar(client, emitido.access_token)

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["X-Usuario-Id"] == str(u.id)
    assert response.headers["X-Usuario-Rol"] == "Prestador"
    assert response.headers["Cache-Control"] == "no-store"
    assert uow.entradas == 0
    assert uow.auditoria.registros == []


@pytest.mark.parametrize(
    "headers",
    [TRAEFIK, {**TRAEFIK, "Authorization": "Basic dXNlcjpwYXNz"}],
    ids=["sin_encabezado", "otro_esquema"],
)
def test_sin_token(client: TestClient, uow: FakeUnitOfWork, headers: dict[str, str]) -> None:
    assert_401(client.get(VERIFICAR, headers=headers))
    assert_fila(uow, "sin_token")


def test_token_mal_formado(client: TestClient, uow: FakeUnitOfWork) -> None:
    assert_401(verificar(client, "no-es-un-jwt"))
    assert_fila(uow, "invalido")


def test_firma_de_otra_llave(client: TestClient, uow: FakeUnitOfWork) -> None:
    privada, publica = generar_llaves_rsa()
    ajeno = JwtTokenService(
        privada,
        publica,
        issuer="iam-service",
        ttl=timedelta(minutes=15),
        reloj=lambda: datetime.now(UTC),
    ).emitir(usuario())

    assert_401(verificar(client, ajeno.access_token))
    # Firma no válida: no se confía en el sub.
    assert_fila(uow, "invalido")


def test_expirado(client: TestClient, uow: FakeUnitOfWork, llaves_rsa: LlavesRsa) -> None:
    hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    u = usuario()
    viejo = crear_token_service(llaves_rsa, reloj=hace_una_hora).emitir(u)

    assert_401(verificar(client, viejo.access_token))
    # Firma válida aunque expirado: la fila lleva al usuario.
    assert_fila(uow, "expirado", u.id)


def test_typ_distinto(client: TestClient, uow: FakeUnitOfWork, llaves_rsa: LlavesRsa) -> None:
    u = usuario()
    ahora = datetime.now(UTC)
    claims = {
        "sub": str(u.id),
        "rol": "Turista",
        "jti": "j-refresh",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=5),
        "iss": "iam-service",
        "typ": "refresh",
    }
    token = jwt.encode(claims, llaves_rsa.private_pem, algorithm="RS256")

    assert_401(verificar(client, token))
    assert_fila(uow, "tipo", u.id)


def test_revocado_por_jti(
    client: TestClient, uow: FakeUnitOfWork, revocacion: FakeRevocacion
) -> None:
    emitido, u = emitir(client)
    revocacion.revocados[emitido.jti] = emitido.expira_en

    assert_401(verificar(client, emitido.access_token))
    assert_fila(uow, "revocado", u.id)


@pytest.mark.parametrize("desfase", [0, 5], ids=["mismo_segundo_del_iat", "despues_del_iat"])
def test_revocado_por_revocado_desde(
    client: TestClient, uow: FakeUnitOfWork, revocacion: FakeRevocacion, desfase: int
) -> None:
    emitido, u = emitir(client)
    iat = emitido.expira_en - timedelta(minutes=15)
    assert u.id is not None
    # El cambio ocurre en el mismo segundo del iat (fracción incluida) o después.
    desde = iat + timedelta(seconds=desfase, microseconds=500_000)
    revocacion.revocados_desde[u.id] = int(desde.timestamp())

    assert_401(verificar(client, emitido.access_token))
    assert_fila(uow, "revocado", u.id)


def test_token_emitido_despues_de_revocado_desde_sigue_valido(
    client: TestClient, revocacion: FakeRevocacion
) -> None:
    emitido, u = emitir(client)
    iat = emitido.expira_en - timedelta(minutes=15)
    assert u.id is not None
    revocacion.revocados_desde[u.id] = int((iat - timedelta(seconds=1)).timestamp())

    assert verificar(client, emitido.access_token).status_code == 200


def test_valkey_caido_503(
    client: TestClient, uow: FakeUnitOfWork, revocacion: FakeRevocacion
) -> None:
    emitido, _ = emitir(client)
    revocacion.caida = True

    response = verificar(client, emitido.access_token)

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICIO_NO_DISPONIBLE"
    assert uow.auditoria.registros == []


def test_postgresql_caido_en_un_rechazo_sigue_siendo_401(
    client: TestClient, uow: FakeUnitOfWork
) -> None:
    uow.caida = True

    assert_401(verificar(client, "no-es-un-jwt"))
    assert uow.entradas == 1
    assert uow.auditoria.registros == []


def test_sin_encabezados_de_traefik_guarda_null(client: TestClient, uow: FakeUnitOfWork) -> None:
    assert_401(client.get(VERIFICAR))

    registro = unico_denegado(uow)
    assert registro.detalles == {"motivo": "sin_token", "metodo": None, "uri": None}
