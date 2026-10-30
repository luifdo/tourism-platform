# Infraestructura del clúster (k3s)

Responsable: Luis Fernando Barraza Sanchez (@luifdo). Lo que todos los servicios necesitan en el clúster (Plan §7.2, §7.4 y §7.6): namespaces, PostgreSQL con CloudNativePG, RabbitMQ, Valkey, SeaweedFS, políticas de red y respaldos.

Cada servicio trae sus propios manifiestos en `services/<servicio>/k8s/`. **Aquí no están** Traefik con sus rutas (`gateway/`), Prometheus, Grafana y Loki (`infra/observabilidad/`, de Juan Francisco) ni cert-manager.

| Componente | Service en `turismo-datos` | Notas |
|---|---|---|
| PostgreSQL + PostGIS 16 | `postgres-rw:5432` | Cinco bases, cada una con su usuario. Una instancia en el Escenario A; para el B, subir `instances` |
| RabbitMQ 4 | `rabbitmq:5672` | Métricas en `:15692` |
| Valkey 8 | `valkey:6379` | Con contraseña y AOF. Bases: catalog 0, booking 1, iam 2, recommendation 3 |
| SeaweedFS | `seaweedfs:8333` | Buckets `catalogo-imagenes`, `documentos-verificacion` y `respaldos-postgres` |

## Desplegar

Desde la raíz del repositorio, con `kubectl` apuntando al clúster:

```bash
# 1. Operador de PostgreSQL (versión fija en operador/)
kubectl apply --server-side -k infra/k8s/operador
kubectl -n cnpg-system rollout status deploy/cnpg-controller-manager

# 2. Secrets: genera infra/k8s/secretos/secretos.yaml (no se sube) con contraseñas aleatorias.
#    Si se usa correo real o el chat, poner SMTP_* y LLM_API_KEY antes de aplicarlo.
python infra/k8s/generar_secretos.py
kubectl apply -f infra/k8s/namespaces.yaml
kubectl apply -f infra/k8s/secretos/secretos.yaml

# 3. Infraestructura
kubectl apply -k infra/k8s
kubectl -n turismo-datos wait --for=condition=Ready cluster/postgres --timeout=10m
kubectl -n turismo-datos wait database --all --for=jsonpath='{.status.applied}'=true --timeout=5m

# 4. Llaves JWT de iam (se crean aparte para no dejarlas en ningún archivo del repositorio)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
kubectl -n turismo-app create secret generic iam-jwt-keys \
  --from-file=private.pem=private.pem --from-file=public.pem=public.pem
rm private.pem public.pem

# 5. Servicios. Primero los que declaran colas que otros usan: RabbitMQ descarta lo que se
#    publique sin una cola enlazada. En un clúster nuevo no hay tráfico hasta abrir el gateway.
kubectl apply -k services/iam-service/k8s/base
kubectl apply -k services/review-service/k8s/base
kubectl apply -k services/catalog-service/k8s/base
kubectl apply -k services/booking-service/k8s/base

# 6. Primer Admin de iam (el script no va en la imagen)
kubectl -n turismo-app exec -i deploy/iam-service -c api -- \
  env ADMIN_EMAIL=... ADMIN_PASSWORD=... ADMIN_NOMBRE=... python - < services/iam-service/scripts/seed_admin.py
```

Los manifiestos de cada servicio apuntan a imágenes de `ghcr.io/turismo-santa-marta/` y a los dominios de producción de sus ConfigMap, que hay que confirmar antes de desplegar. Todavía ningún flujo de GitHub Actions publica esas imágenes (Plan §7.2).

## Secrets que espera cada servicio

`generar_secretos.py` crea en `turismo-app` los Secrets `iam-secretos`, `catalog-secretos`, `booking-service-secretos`, `review-secretos` y `recommendation-secretos`, con las URL ya armadas. Si el archivo ya existe no lo cambia: otras contraseñas dejarían a los servicios sin acceso a sus bases.

recommendation-service aún no tiene `k8s/`. Cuando la tenga, debe crear `recomendacion_log` con su propio usuario: el script está en `services/recommendation-service/db/` y el servicio no tiene migraciones.

## Red

La entrada se niega por defecto en `turismo-app` y `turismo-datos`, y cada componente abre lo suyo. A `turismo-datos` solo entran `turismo-app`, Prometheus (`observabilidad`, etiqueta `app.kubernetes.io/name: prometheus`) y Traefik a SeaweedFS, porque el navegador usa las URL firmadas. **El frontend, cuando se despliegue, necesita su propia NetworkPolicy** para que Traefik le llegue.

## Respaldos y restauración (RNF-09, ESC-06)

Respaldo base diario a las 03:00 UTC y WAL continuo en `respaldos-postgres`, con retención de 14 días.

```bash
# Respaldo a mano, y su estado
kubectl -n turismo-datos apply -f - <<EOF
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata: { name: manual }
spec: { cluster: { name: postgres } }
EOF
kubectl -n turismo-datos get backup

# Restaurar en un clúster nuevo; postgres-rw no se toca
kubectl apply -f infra/k8s/datos/restaurar/postgres-restaurado.yaml
kubectl -n turismo-datos wait --for=condition=Ready cluster/postgres-restaurado --timeout=30m
```

Luego se apunta el servicio afectado a `postgres-restaurado-rw` en su Secret y se reinician sus pods. Para volver a un momento anterior a la corrupción, usar `recoveryTarget` en ese archivo.

**Antes de pasar de CloudNativePG 1.28:** el respaldo nativo con Barman que se usa aquí se elimina en la 1.29, y habrá que migrar al plugin Barman Cloud.

## Qué se probó (2026-10-30)

En un k3s v1.31.5 dentro de un contenedor, en una VM de 4 GB, con los servicios a una réplica y rutas temporales de Traefik:

| Prueba | Resultado |
|---|---|
| Despliegue de todo desde cero: cinco bases con su dueño, extensiones, buckets y Secrets | ✅ |
| Desde otro namespace, bases, RabbitMQ, Valkey, SeaweedFS y servicios | ✅ los 8 destinos bloqueados |
| Reinicio de RabbitMQ con su volumen; los workers se reconectan y redeclaran sus colas | ✅ |
| Respaldo y restauración con WAL: dos marcas escritas después del respaldo llegaron | ✅ 140 s, con muy pocos datos: falta medir ESC-06 con volumen real |
| Flujo completo por Traefik con JWT | ⚠️ sin terminar: la VM se saturó. Pasaron 49 comprobaciones seguidas, hasta finalizar la reserva. El resto se comprobó en el compose |

**Falta probar en un nodo de 8 GB:** el flujo completo, los HPA y los CronJobs con carga real. También queda sin probar el acceso real desde fuera del clúster.

**Traefik:** el k3s v1.31.5 usado trae Traefik **2.11.18**, y el Plan dice v3. Las reglas no son iguales en las dos versiones: `PathRegexp` no existe en v2. Hay que fijar la versión de k3s del clúster y escribir las rutas para la que traiga.

## Dimensionamiento

Pensado para el Escenario A (1 nodo de 4 vCPU y 8 GB). En un portátil con Docker Desktop y una VM de 4 GB no alcanza con todas las réplicas: los HPA escalan al arrancar, porque importar FastAPI supera el `request` de CPU, y el nodo se satura. Para probar ahí, quitar los HPA y dejar una réplica de cada servicio.

`-volume.max=30` de SeaweedFS y el `fsGroupChangePolicy: OnRootMismatch` de RabbitMQ no son ajustes opcionales: sin el primero una colección puede dejar sin espacio a las demás (F-10 de iam), y sin el segundo RabbitMQ no arranca después de un reinicio.
