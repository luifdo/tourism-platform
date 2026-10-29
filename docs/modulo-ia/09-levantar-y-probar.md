# Levantar, probar y verificar

> Módulo 5 · [Índice](./README.md)

Requisito: Docker y Docker Compose instalados, y tu usuario en el grupo `docker` (si `docker ps` da "permission denied", cierra sesión y vuelve a entrar).

```bash
cd services/recommendation-service
cp .env.example .env
docker compose up --build -d   # construye la imagen y levanta servicio, PostgreSQL y Valkey
docker compose logs -f         # ver los logs (Ctrl+C para salir)
docker compose down            # apaga los contenedores
docker compose down -v         # además borra los datos (reinicia la base y las sesiones)
```

El compose levanta el servicio, PostgreSQL (`localhost:5434`), Valkey (`localhost:6380`) y el `mock-plataforma` (`localhost:9000`). Los puertos se publican para las pruebas de integración y no chocan con los de iam-service.

## Verificación (fases 0 a 2)

| Comprobación | Comando | Resultado esperado |
|---|---|---|
| Servicio vivo | `curl localhost:8005/health` | `{"status":"ok","checks":{"database":"up","valkey":"up"}}` con código 200; 503 y `"degraded"` si PostgreSQL o Valkey no responden |
| Métricas | `curl localhost:8005/metrics` | Texto en formato Prometheus |
| Estado | `docker compose ps` | `Up ... (healthy)` |
| Usuario | `docker compose exec recommendation-service id` | `uid=1000(recommendation)`, sin privilegios |
| Tabla | `docker compose exec postgres psql -U turismo -d recommendation_db -c '\d recomendacion_log'` | Las 8 columnas de [07-base-de-datos.md](./07-base-de-datos.md) |
| Mock (Fase 2) | `curl "localhost:9000/api/catalog/buscar?zona=minca"` | Dos servicios de Minca con el formato de `catalog.yaml` |
| Mock con identidad | `curl localhost:9000/api/catalog/analitica/capacidad -H "X-Usuario-Id: 7c0e7a52-6f4b-4d65-9a3e-2f1d8b0c4e11" -H "X-Usuario-Rol: Turista"` | Las 5 zonas con su nivel, sin cifras; 401 sin los encabezados |

Chat (Fase 3), sin proveedor de IA configurado:

| Comprobación | Comando | Resultado esperado |
|---|---|---|
| Chat sin proveedor | `curl -X POST localhost:8005/api/recommendations/chat -H "X-Usuario-Id: 7c0e7a52-6f4b-4d65-9a3e-2f1d8b0c4e11" -H "X-Usuario-Rol: Turista" -H "Content-Type: application/json" -d '{"mensaje":"¿Qué puedo hacer en Taganga?"}'` | 503 `ASISTENTE_NO_DISPONIBLE` hasta la Fase 5 (con Groq: respuesta con recomendaciones justificadas) |
| Chat sin identidad | El mismo `curl` sin `X-Usuario-Id` | 401 `NO_AUTENTICADO` |

La conversación completa (respuesta, fila en `recomendacion_log` y sesión que recuerda el contexto) se verifica con `tests/integration/test_chat_integracion.py`, que usa PostgreSQL, Valkey y el mock reales con un modelo con guion.

## Pruebas y calidad

Con `uv` (desde `services/recommendation-service/`):

```bash
uv sync                  # instala las dependencias, incluidas las de desarrollo
uv run pytest --cov      # pruebas con cobertura (mínimo 70 %)
uv run ruff check .      # revisión de estilo
```

`pytest` cubre las pruebas unitarias (dominio y casos de uso con los puertos simulados), la de contrato y, desde la Fase 1, las de integración (PostgreSQL y Valkey reales).

Las de integración necesitan `docker compose up -d postgres valkey mock-plataforma`; si no los encuentran, se **omiten** (`pytest -rs` muestra el motivo), así que revisa que no aparezcan como `skipped` antes de dar una fase por cerrada. Usan la base 15 de Valkey y la vacían al terminar, sin tocar las sesiones de desarrollo. Las direcciones se cambian con `TEST_DB_URL`, `TEST_VALKEY_URL` y `TEST_MOCK_URL`.

Las tools se prueban de dos formas: las unitarias (`tests/unit/test_herramientas.py`) corren contra el mock en el mismo proceso y simulan las fallas de red con `httpx.MockTransport`, sin necesitar contenedores; las de integración (`tests/integration/test_herramientas_integracion.py`) llaman al contenedor `mock-plataforma` por HTTP real. Además, `tests/unit/test_mock_contratos.py` valida el mock contra los contratos de catalog, booking y review.

En Windows, `tests/conftest.py` cambia el bucle de eventos de asyncio porque `psycopg` asíncrono no funciona con el bucle por defecto; en el contenedor no aplica.

La prueba de contrato (`tests/unit/test_contrato.py`) comprueba que el código no exponga ninguna ruta que `contracts/openapi/recommendation.yaml` no declare. El contrato manda: se cambia primero, y el código lo sigue.

---
[← Simulación y proveedor de IA](./08-simulacion.md) · [Plan por fases →](./10-plan-por-fases.md)
