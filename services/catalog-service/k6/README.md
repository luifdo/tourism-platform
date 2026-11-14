# Pruebas de carga del catálogo (k6)

Plan §8.4. Dos scripts, cada uno con un perfil corto (`humo`, el de por defecto) para comprobar que todo funciona y el perfil `completo` del escenario de calidad:

| Script | Escenario | Perfil `completo` | Criterio |
|---|---|---|---|
| `buscar.js` | ESC-02 | 500 rps sobre `GET /buscar` durante 10 min | p95 < 2 s, 0 errores 5xx |
| `escalado.js` | ESC-08 | Rampa hasta 1000 rps (búsqueda 50 %, ficha 30 %, mapa 20 %), 30 min | p95 < 2 s, 0 errores 5xx; réplicas del HPA y tiempo hasta quedar listas |

El perfil `completo` se mide en el clúster k3s del Escenario A (Plan §7.2), no en un PC: la máquina virtual de Docker Desktop no tiene CPU ni memoria para 500-1000 rps y el resultado no diría nada del sistema real. En local se usa `humo`.

## 1. Datos de prueba

Con la base vacía la búsqueda no mide nada. Siembra 2000 servicios repartidos en las 6 zonas (con el compose de `infra/` arriba):

```bash
cd services/catalog-service
DATABASE_URL=postgresql+asyncpg://turismo:cambiar-en-local@localhost:5432/catalog_db \
VALKEY_URL=redis://localhost:6379/0 \
uv run python scripts/sembrar_datos_carga.py            # --servicios N para otra cantidad
# ... y para quitarlos al terminar:
uv run python scripts/sembrar_datos_carga.py --borrar    # (con las mismas variables)
```

## 2. Correr k6 dentro del clúster

k6 corre como un Job en el namespace `turismo-app`, así que no hay que instalar nada. Los scripts llegan por un ConfigMap:

```bash
cd services/catalog-service
kubectl -n turismo-app create configmap k6-scripts --from-file=k6/buscar.js --from-file=k6/escalado.js \
  --dry-run=client -o yaml | kubectl apply -f -          # crea o actualiza los scripts
kubectl -n turismo-app delete job k6 --ignore-not-found  # un Job no se puede volver a lanzar
kubectl apply -f k6/job.yaml
kubectl -n turismo-app logs -f job/k6                    # resultado al final
```

Para correr `escalado.js` o el perfil `completo`, cambia `SCRIPT` y `PERFIL` en `k6/job.yaml`. Al final k6 imprime `✓` o `✗` en cada umbral (`thresholds`); si alguno falla, el Job termina con error.

**Mientras corre `escalado.js`**, en otra terminal registra las réplicas y cuándo quedan listas (ESC-08):

```bash
kubectl -n turismo-app get hpa catalog-service -w                     # réplicas y CPU
kubectl -n turismo-app get pods -l app.kubernetes.io/component=api -w # cuándo pasa cada pod a 1/1
```

## 3. En el clúster k3s

* Medir entrando por Traefik, como un turista: descomenta `BASE_URL` en `k6/job.yaml` con la URL pública. Así entra en la medida el gateway, y la NetworkPolicy de catalog (que no deja entrar a un pod cualquiera, como el de k6) no estorba.
* Correr k6 en un nodo distinto al de catalog, o desde otra máquina (`k6 run k6/buscar.js` con `BASE_URL`), para que el generador de carga no le quite CPU a lo que se mide.
* Guardar la salida de k6 y del `get hpa -w` como evidencia del escenario.

## 4. Resultados en local (perfil `humo`, 2026-10-24)

Kubernetes de Docker Desktop en un PC, con los 2000 servicios sembrados. Indica que el sistema funciona bajo carga; **no** reemplaza la medición de ESC-02/ESC-08 en k3s.

| Script | Carga | Peticiones | 5xx | Mediana | p95 | Nota |
|---|---|---|---|---|---|---|
| `buscar.js` | 30 rps, 1 min | 1668 | 0 | 22 ms | 1,29 s | 133 iteraciones descartadas: picos de hasta 6,9 s con la caché fría y 2 réplicas dejaron a k6 sin VUs para sostener el ritmo |
| `escalado.js` | rampa a 60 rps, 3 min | 7276 | 0 | 30 ms | 228 ms | El HPA subió a 6 réplicas (CPU 124 % → 220 % del objetivo); todas quedaron listas |
