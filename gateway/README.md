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
| `HostRegexp(^s3\..+$)` → `seaweedfs:8333` | todo (la autenticación es la firma de la URL); sirve `s3.localhost` y `s3.<dominio>` |
| `/` (lo demás) → frontend | todo |

Todo lo demás pasa por ForwardAuth (`GET /api/iam/auth/verificar`). **Nunca se enrutan** `/internal`, `/health` ni `/metrics`: caen en el frontend, cuyo Nginx responde 404. Prometheus y Blackbox consultan los Services por dentro del clúster.

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

* **docker compose** (`infra/`): `docker compose up -d`. Traefik escucha en el puerto 80 y recarga `config/compose/` solo. La ruta `/` apunta al contenedor `frontend` del compose (Nginx, puerto 8080, `frontend/Dockerfile`), compilado con `VITE_API_MOCK=false`. Para desarrollar con recarga en caliente se usa `npm run dev` (puerto 5173), cuyo proxy de Vite manda `/api` a este gateway.
* **k3d / k3s:** `kubectl apply -k gateway/config/k3s` (namespaces `turismo-app`, `turismo-datos` y `kube-system`, ya definidos en `infra/k8s/`).

## Lo que no está hecho o no se pudo comprobar

* **No se aplicó en un clúster** (no hay k3d en el equipo de desarrollo): `k3s/` se validó contra los CRD de Traefik v3.3, no contra un Traefik en ejecución. La lógica de rutas sí se probó con un Traefik real, pero la 3.7 y por `compose/`; el compose usa `traefik:v3.3` y k3s trae su propia versión.
* **`externalTrafficPolicy: Local`** (F-08 del IAM) está configurado en `k3s/sistema/traefik.yaml`, pero hay que comprobar en el clúster real que la IP del cliente llega. El balanceador de k3d no la conserva aunque se configure; mientras no llegue, el límite de tasa por IP se comparte entre todos los usuarios.
* **TLS en k3s** (cert-manager o el resolver ACME de Traefik) falta: el HTTPS de abajo es del compose. En k3s los CRD no admiten plantillas: el origen CORS de `k3s/datos/almacenamiento.yaml` lleva el dominio provisional escrito y `validar_k3s.py` comprueba que coincida con el de compose.
* **`X-Correlation-ID`:** Traefik lo reenvía pero no lo genera (haría falta un plugin). Los servicios generan uno si falta (catalog lo hace; confirmar los demás).
* **SeaweedFS expuesto:** el gateway publica todo el S3, así que el acceso anónimo debe seguir limitado a `Read:catalogo-imagenes` (C-46) o los documentos de verificación quedan legibles sin firma. En compose lo escribe el servicio `seaweedfs` al arrancar, con las claves `S3_*` de `infra/.env`; en k3s, el Secret `seaweedfs-identidades`.
* **Frontend en k3s:** el Dockerfile ya existe, pero faltan el Deployment, el Service `frontend` (puerto 80 hacia el 8080 del contenedor) y su NetworkPolicy.
* Una ruta `/api/...` que no existe cae en el frontend, pero el Nginx del frontend responde 404 en JSON (no el HTML con 200). Igual `/internal`, `/health` y `/metrics`: 404.
* `GET /api/iam/auth/verificar` es alcanzable desde fuera (con token válido); solo devuelve la identidad que ya tiene el usuario.
* No hay CORS en la API: la PWA entra por el mismo origen (en desarrollo, el proxy de Vite envía `/api` al puerto 80).

## HTTPS (compose)

`infra/docker-compose.https.yml` se **suma** al compose base (`docker compose -f docker-compose.yml -f docker-compose.https.yml up -d`, o `COMPOSE_FILE` en `infra/.env`). Variables: `DOMINIO_PUBLICO` (obligatoria, por ejemplo `3-141-142-12.sslip.io`), `ACME_EMAIL` y `ACME_CA_SERVER`.

* Abre el 443; el 80 solo redirige a HTTPS (conserva la ruta y el query string, que lleva el token de recuperar contraseña; el log de acceso sigue sin registrarlos). Las rutas no declaran `entryPoints`, así que sirven igual por HTTP (local) y por HTTPS (servidor).
* Un certificado de Let's Encrypt para `DOMINIO_PUBLICO` y `s3.DOMINIO_PUBLICO` (reto HTTP-01), guardado en el volumen `traefik-acme` y renovado solo. HSTS de un día (`hsts`).
* **Los puertos 80 y 443 deben estar abiertos a todo internet** (Let's Encrypt valida desde fuera). Si el firewall solo deja pasar IPs autorizadas, el certificado no se emite.
* **Primero con staging** (`ACME_CA_SERVER=https://acme-staging-v02.api.letsencrypt.org/directory`): `sslip.io` no está en la lista de sufijos públicos, así que comparte el límite de certificados de Let's Encrypt con todos sus usuarios; un intento fallido con la CA real gasta cupo. Con staging el navegador marca el certificado como no confiable; después se quita la variable y se borra el volumen `traefik-acme`.
* El host de S3 es `HostRegexp(^s3\..+$)`: el dominio solo se define en `infra/.env` (`DOMINIO_PUBLICO`, `S3_ENDPOINT_PUBLICO`, `IMAGENES_URL_PUBLICA`, `PWA_URL`, que deben coincidir). El origen CORS de la PWA sale de `DOMINIO_PUBLICO` (plantilla del proveedor de archivos).
* **Compose reemplaza `command`, no lo suma:** el del archivo HTTPS repite los flags del base. `probar_gateway.py` comprueba que no se desincronicen. (Traefik tampoco mezcla variables `TRAEFIK_*` con flags: usa solo una fuente.)
* Probado con Traefik 3.3 real y un servidor ACME de prueba (Pebble): el certificado se emite con los dos nombres, la redirección no rompe el reto y HSTS, CORS y el reparto por host funcionan por HTTPS. **No probado** con Let's Encrypt real ni con el firewall de la VM.
* Traefik escribe un aviso por ruta ("No domain found in rule"): es informativo, las rutas por ruta (no por host) usan el SNI de la petición.

