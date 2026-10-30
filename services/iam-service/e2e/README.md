# Entorno e2e de iam-service

**Es un entorno de prueba, no de producción.** Las credenciales son falsas y evidentes (`solo-para-pruebas-e2e`), las dependencias no persisten nada y el gateway es mínimo. La configuración real del gateway es de Juan Francisco, en `gateway/`; la de las dependencias, de `infra/`.

Crea un clúster k3d `iam-e2e` con su kubeconfig en una carpeta temporal, sin tocar el tuyo. Las llaves JWT se generan en cada corrida y nunca se versionan.

```bash
uv run python -m scripts.e2e_k3d                 # prepara, ejecuta y borra todo
uv run python -m scripts.e2e_k3d --conservar     # no borra el clúster al terminar
uv run python -m scripts.e2e_k3d --solo-borrar   # borra lo que haya quedado
```

Necesita Docker, `k3d` y `kubectl`, y los puertos 18080 (Traefik), 25433, 25673, 28025 y 28333 libres. El reporte queda en `docs/evidencias/e2e-k3d.txt`. Tarda unos 10 minutos, porque el rate limiting del login obliga a esperar entre escenarios.
