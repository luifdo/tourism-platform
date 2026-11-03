# API Gateway

**Capa transversal** · Responsable: Juan Francisco Gonzalez Pacheco (@JuanFranG)

Punto de entrada único con **Traefik**, el Ingress que trae k3s (ADR-007). Enruta por prefijo a cada servicio, valida el token con ForwardAuth contra iam-service, impide que el cliente se haga pasar por otro usuario, limita la tasa de los endpoints sensibles y sirve la PWA.

```
gateway/
├── config/compose/   Traefik con el proveedor de archivos (lo monta infra/docker-compose.yml)
├── config/k3s/       Lo mismo como recursos de Kubernetes (IngressRoute, Middleware, ServersTransport, HelmChartConfig)
└── pruebas/          Pruebas con un Traefik real y servicios falsos; validación de los manifiestos de k3s
```

Las dos configuraciones declaran **las mismas rutas** y una prueba lo comprueba (`validar_k3s.py`).

## Qué es público y qué exige sesión

La fuente de verdad es el `security` de cada contrato de `contracts/openapi/`; una prueba recorre **todas** las operaciones (82) y falla si el gateway no coincide.

| Prefijo → destino (sin quitar el prefijo) | Públicas (sin ForwardAuth) |
|---|---|
| `/api/iam` → `iam-service:8001` | `POST register`, `POST login`, `POST auth/refresh`, `POST auth/recuperar`, `POST auth/restablecer`, `GET .well-known/jwks.json` |
| `/api/catalog` → `catalog-service:8002` | `GET servicios`, `GET servicios/{id}`, `GET buscar`, `GET zonas`, `GET alertas`, `GET mapa/*`, `POST servicios/{id}/intencion-visita` |
| `/api/bookings` → `booking-service:8003` | `GET disponibilidad` |
| `/api/reviews` → `review-service:8004` | `GET servicios/{id}/resenas`, `GET servicios/{id}/resumen`, `GET resenas/{id}` |
| `/api/recommendations` → `recommendation-service:8005` | ninguna (el chat puede tardar hasta 45 s: espera de 60 s) |
| `Host(s3.localhost)` → `seaweedfs:8333` | todo (la autenticación es la firma de la URL) |
| `/` (lo demás) → frontend | todo |

Todo lo demás pasa por ForwardAuth (`GET /api/iam/auth/verificar`). **Nunca se enrutan** `/internal`, `/health` ni `/metrics`: caen en el frontend. Prometheus y Blackbox consultan los Services por dentro del clúster.

## Reglas de seguridad (las pide el IAM y lo repiten catálogo y reservas)

* **`X-Usuario-Id` y `X-Usuario-Rol` se borran en todas las peticiones**, también en las públicas. En las protegidas solo llegan los que devuelve ForwardAuth (`authResponseHeaders`), sin `trustForwardHeader`. Los servicios confían en esos encabezados, así que esto es lo que impide hacerse pasar por otro usuario.
* El orden de las rutas protegidas es *borrar identidad → validar token*. En `POST /api/iam/prestador/documentos` el tope de 6 MB va **después** de validar el token, para que un anónimo no haga almacenar un cuerpo grande (el overlay `e2e` del IAM los pone al revés; ambos son válidos).
* **Límites de tasa por IP:** login y recuperar comparten 5 por minuto; `auth/refresh` tiene el suyo (20 por minuto, ráfaga de 10) para no gastar el cupo del login. El registro y el restablecimiento no tienen límite en el gateway (el IAM responde `SERVICIO_OCUPADO`).
* `X-Forwarded-For` del cliente no se acepta: Traefik pone el suyo.
* **Registro de acceso en JSON sin la ruta ni la línea de la petición**, porque incluyen el query string y el enlace de `/restablecer-contrasena?token=...` lleva el token. Se conservan router, servicio, método y estado; para seguir una petición se usa el `correlation_id` de los servicios.

## Probarlo

```bash
brew install traefik kustomize          # Traefik 3 y kustomize
pip install -r gateway/pruebas/requirements.txt
cd gateway/pruebas
python probar_gateway.py                # levanta Traefik + servicios falsos: 54 comprobaciones
python validar_k3s.py                   # kustomize + CRD de Traefik + igualdad compose/k3s
```

`probar_gateway.py` no necesita Docker ni Kubernetes. Comprueba, entre otras cosas, que sin token las rutas protegidas dan 401 y no llegan al servicio, que una identidad falsa nunca llega, que el login da 429 al 6.º intento, que 7 MB dan 413 y que el token de recuperación no queda en el log. Se probó rompiendo la configuración a propósito (una ruta pública sin borrar identidad, un `POST` sin sesión, un middleware compartido, sin tope de cuerpo, sin ocultar la ruta en el log) y cada rotura falla.

## Usarlo

* **docker compose** (`infra/`): `docker compose up -d`. Traefik escucha en el puerto 80 y recarga `config/compose/` solo. El frontend todavía no está en el compose: la ruta `/` apunta al servidor de desarrollo del anfitrión (`npm run dev`, puerto 5173).
* **k3d / k3s:** `kubectl apply -k gateway/config/k3s` (namespaces `turismo-app`, `turismo-datos` y `kube-system`, ya definidos en `infra/k8s/`).

## Lo que no está hecho o no se pudo comprobar

* **No se aplicó en un clúster** (no hay k3d en el equipo de desarrollo): `k3s/` se validó contra los CRD de Traefik v3.3, no contra un Traefik en ejecución. La lógica de rutas sí se probó con un Traefik real, pero la 3.7 y por `compose/`; el compose usa `traefik:v3.3` y k3s trae su propia versión.
* **`externalTrafficPolicy: Local`** (F-08 del IAM) está configurado en `k3s/sistema/traefik.yaml`, pero hay que comprobar en el clúster real que la IP del cliente llega. El balanceador de k3d no la conserva aunque se configure; mientras no llegue, el límite de tasa por IP se comparte entre todos los usuarios.
* **TLS** (cert-manager, ACME) y los **dominios**: faltan hasta que exista la VM (`sslip.io`). El host de SeaweedFS (`s3.localhost`) y el origen de CORS de la PWA se cambian entonces, y deben coincidir con `S3_ENDPOINT_PUBLICO` e `IMAGENES_URL_PUBLICA` de los servicios.
* **`X-Correlation-ID`:** Traefik lo reenvía pero no lo genera (haría falta un plugin). Los servicios generan uno si falta (catalog lo hace; confirmar los demás).
* **SeaweedFS expuesto:** el gateway publica todo el S3. Antes de abrirlo hay que limitar el acceso anónimo a `Read:catalogo-imagenes` (C-46, `infra/seaweedfs/s3.json`) o los documentos de verificación quedan legibles sin firma.
* **Frontend en k3s:** falta el Service `frontend` (puerto 80), su Dockerfile y su NetworkPolicy.
* Una ruta `/api/...` que no existe cae en el frontend y devuelve su HTML con 200, no un 404 en JSON.
* `GET /api/iam/auth/verificar` es alcanzable desde fuera (con token válido); solo devuelve la identidad que ya tiene el usuario.
* No hay CORS en la API: la PWA entra por el mismo origen (en desarrollo, el proxy de Vite envía `/api` al puerto 80).
