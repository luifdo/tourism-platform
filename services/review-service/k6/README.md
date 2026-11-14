# Prueba ESC-01 de review (k6 + caos)

Plan §8.4. **ESC-01:** una falla en el Módulo de Reseñas no interrumpe la navegación en el catálogo; Kubernetes retira la réplica caída del enrutamiento en **menos de 5 s** y la reinicia.

| Pieza | Qué hace |
|---|---|
| [`esc01.js`](./esc01.js) | k6 consulta a la vez la búsqueda de catalog (criterio: 0 errores, p95 < 2 s) y el resumen público de review (solo se mide: con 1 réplica, review no responde mientras se reinicia). Perfiles `humo` (local) y `completo` (k3s) |
| [`job.yaml`](./job.yaml) | Corre `esc01.js` como Job dentro del clúster; el script llega por el ConfigMap `k6-review` |
| [`../scripts/esc01_aislamiento.py`](../scripts/esc01_aislamiento.py) | Mientras k6 corre, tumba la API de review tres veces (`proceso`: termina el proceso; `pod`: borra el pod de golpe) y mide en el EndpointSlice del Service el tiempo de aislamiento y de recuperación |

## Cómo correrla

Con catalog y review desplegados en el clúster (sus overlays) y la infraestructura arriba:

```bash
cd services/review-service
kubectl -n turismo-app create configmap k6-review --from-file=k6/esc01.js \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n turismo-app delete job k6-review --ignore-not-found
# SERVICIO_ID: un servicio con reseñas, para que el resumen responda con datos
sed "s/00000000-0000-0000-0000-000000000000/<servicio_id>/" k6/job.yaml | kubectl apply -f -
uv run python scripts/esc01_aislamiento.py          # en otra terminal, a la vez
kubectl -n turismo-app logs -f job/k6-review        # umbrales al final
```

En k3s: perfil `completo`, `CATALOG_URL` y `REVIEW_URL` entrando por Traefik (comentados en `job.yaml`), y k6 en un nodo distinto al de catalog y review.

## Estado (2026-10-27): pendiente de medir en un entorno con capacidad

Se intentó en el Kubernetes de Docker Desktop de un PC y **la máquina no dio para medir**: el resultado no es evidencia de ESC-01. Lo que se vio, para retomarlo:

* **Catalog no respondió a nadie desde el primer segundo** (antes de tumbar review): con 20 rps la búsqueda en frío tardaba 3 s, catalog escaló a 6 réplicas y aun así todas las peticiones vencieron. No tiene que ver con review; el nodo estaba al 76 % de CPU en reposo.
* **Falla `pod`:** aislamiento de 4,0 s (cumple).
* **Falla `proceso`:** el log muestra que la API terminó a los 2,3 s de la señal, pero el script midió 17–30 s porque la orden de `kubectl exec` tardó 14 s y el script consulta los endpoints con `kubectl`, igual de lento con el plano de control saturado.
* **RabbitMQ gastaba 70–115 % de CPU sin trabajo** (espera activa de Erlang). Se agregó `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS` en `infra/docker-compose.yml`; aún quedan picos periódicos.

**Para retomarlo:**

1. Correrla en el clúster k3s del equipo (o en una máquina con CPU libre), no en un PC con el compose y el clúster a la vez.
2. Si se repite en local, bajar el perfil `humo` (unas 4 rps a catalog y 2 a review): ESC-01 pide que catalog siga atendiendo, no su capacidad máxima (eso es ESC-02).
3. Si `kubectl` sigue lento, medir el aislamiento con las marcas de tiempo de Kubernetes (el paso del pod a `Ready=False` frente al `finishedAt` del contenedor) en vez de consultar los endpoints en bucle.

Ya comprobado en el paso 11: con PostgreSQL caído, la API pasa a `0/1` sin bajar el worker y vuelve sola; y review no llama a ningún servicio, así que su caída no tiene cómo llegar a catalog.
