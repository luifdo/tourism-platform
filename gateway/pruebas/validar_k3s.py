#!/usr/bin/env python3
"""Valida gateway/config/k3s sin necesitar un clúster.

    pip install -r requirements.txt                # y tener `kustomize` (brew install kustomize)
    python validar_k3s.py                           # baja los CRD de Traefik v3.3
    python validar_k3s.py --crd ruta/al/crd.yml --version v3.5

1. `kustomize build` debe funcionar.
2. Cada Middleware, IngressRoute y ServersTransport se valida contra los CRD oficiales de Traefik: tipos, y campos
   que el esquema no conoce (Kubernetes los descartaría en silencio, así que un error de escritura pasaría sin avisar).
3. config/compose y config/k3s declaran las mismas rutas, prioridades, middlewares y servicios.
"""
import argparse
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import jsonschema
import yaml

RAIZ = Path(__file__).resolve().parents[2]
DOMINIO_PROVISIONAL = "3-141-142-12.sslip.io"  # el de infra/.env.example; en k3s va escrito en almacenamiento.yaml
CRD_URL = "https://raw.githubusercontent.com/traefik/traefik/{version}/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml"
fallos = []


def verificar(nombre, condicion, detalle=""):
    print(("  ✓ " if condicion else "  ✗ ") + nombre + ("" if condicion else f"  → {detalle}"))
    if not condicion:
        fallos.append(nombre)


def desconocidos(instancia, esquema, ruta=""):
    salida = []
    if isinstance(instancia, dict) and esquema.get("properties") is not None:
        for clave, valor in instancia.items():
            if clave not in esquema["properties"]:
                if not esquema.get("x-kubernetes-preserve-unknown-fields"):
                    salida.append(f"{ruta}/{clave}")
            else:
                salida += desconocidos(valor, esquema["properties"][clave], f"{ruta}/{clave}")
    elif isinstance(instancia, dict) and isinstance(esquema.get("additionalProperties"), dict):
        for clave, valor in instancia.items():
            salida += desconocidos(valor, esquema["additionalProperties"], f"{ruta}/{clave}")
    elif isinstance(instancia, list) and isinstance(esquema.get("items"), dict):
        for i, valor in enumerate(instancia):
            salida += desconocidos(valor, esquema["items"], f"{ruta}[{i}]")
    return salida


def cargar_esquemas(ruta_crd):
    esquemas = {}
    for doc in yaml.safe_load_all(ruta_crd.read_text()):
        if doc and doc.get("kind") == "CustomResourceDefinition":
            for version in doc["spec"]["versions"]:
                esquemas[(doc["spec"]["names"]["kind"], f"{doc['spec']['group']}/{version['name']}")] = version["schema"]["openAPIV3Schema"]
    return esquemas


def normalizar(regla):
    return re.sub(r"\s+", " ", regla).replace("( ", "(").replace(" )", ")").strip()


def rutas_de_compose():
    rutas = set()
    for archivo in sorted((RAIZ / "gateway/config/compose").glob("*.yml")):
        for router in (yaml.safe_load(archivo.read_text()).get("http", {}).get("routers") or {}).values():
            rutas.add((normalizar(router["rule"]), router["priority"], tuple(router.get("middlewares", [])), router["service"]))
    return rutas


def rutas_de_k3s(documentos):
    rutas = set()
    for doc in documentos:
        if doc["kind"] == "IngressRoute":
            for ruta in doc["spec"]["routes"]:
                rutas.add((normalizar(ruta["match"]), ruta["priority"], tuple(m["name"] for m in ruta.get("middlewares", [])),
                           ruta["services"][0]["name"]))
    return rutas


def middlewares_de_compose():
    todos = {}
    for archivo in sorted((RAIZ / "gateway/config/compose").glob("*.yml")):
        todos.update(yaml.safe_load(archivo.read_text()).get("http", {}).get("middlewares") or {})
    return todos


def servicios_de_k8s():
    """{(namespace, nombre): {puertos}} de los Service que declaran los manifiestos de cada servicio y de infra/k8s."""
    encontrados = {}
    for carpeta in sorted(RAIZ.glob("services/*/k8s/base")) + [RAIZ / "infra/k8s"]:
        r = subprocess.run(["kustomize", "build", str(carpeta)], capture_output=True, text=True)
        if r.returncode:
            continue
        for doc in (d for d in yaml.safe_load_all(r.stdout) if d and d["kind"] == "Service"):
            meta = doc["metadata"]
            encontrados[(meta.get("namespace", "default"), meta["name"])] = {p["port"] for p in doc["spec"]["ports"]}
    return encontrados


def destinos_de_k3s(documentos):
    """(namespace, servicio, puerto) a los que apunta cada ruta."""
    return sorted({(doc["metadata"]["namespace"], srv["name"], srv["port"])
                   for doc in documentos if doc["kind"] == "IngressRoute"
                   for ruta in doc["spec"]["routes"] for srv in ruta["services"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crd", help="archivo con los CRD de Traefik (si no, se descargan)")
    parser.add_argument("--version", default="v3.3", help="versión de Traefik de los CRD (la del compose es v3.3)")
    args = parser.parse_args()

    print("kustomize build gateway/config/k3s")
    construido = subprocess.run(["kustomize", "build", str(RAIZ / "gateway/config/k3s")], capture_output=True, text=True)
    verificar("kustomize construye los manifiestos", construido.returncode == 0, construido.stderr[:300])
    if construido.returncode:
        sys.exit(1)
    documentos = [d for d in yaml.safe_load_all(construido.stdout) if d]

    ruta_crd = Path(args.crd) if args.crd else Path(tempfile.mkdtemp()) / "crd.yml"
    if not args.crd:
        urllib.request.urlretrieve(CRD_URL.format(version=args.version), ruta_crd)
    esquemas = cargar_esquemas(ruta_crd)

    print("\nRecursos contra los CRD de Traefik")
    for doc in documentos:
        clave = (doc["kind"], doc["apiVersion"])
        if clave not in esquemas:
            print(f"  – {doc['kind']} {doc['metadata']['name']}: no es un recurso de Traefik, no se valida")
            continue
        esquema = esquemas[clave]
        problemas = [f"{e.message} en /{'/'.join(map(str, e.absolute_path))}" for e in jsonschema.Draft7Validator(esquema).iter_errors(doc)]
        problemas += [f"campo desconocido {p}" for p in desconocidos(doc.get("spec", {}), esquema["properties"]["spec"], "/spec")]
        verificar(f"{doc['kind']} {doc['metadata']['namespace']}/{doc['metadata']['name']}", not problemas, "; ".join(problemas))

    print("\nCompose y k3s declaran lo mismo")
    en_compose, en_k3s = rutas_de_compose(), rutas_de_k3s(documentos)
    verificar(f"las {len(en_compose)} rutas son iguales (regla, prioridad, middlewares y servicio)", en_compose == en_k3s,
              f"solo en compose: {sorted(en_compose - en_k3s)[:2]} · solo en k3s: {sorted(en_k3s - en_compose)[:2]}")
    mw_compose = middlewares_de_compose()
    for doc in (d for d in documentos if d["kind"] == "Middleware" and d["metadata"]["namespace"] == "turismo-app"):
        nombre, spec = doc["metadata"]["name"], dict(doc["spec"])
        original = mw_compose.get(nombre)
        if original is None:
            verificar(f"middleware {nombre} existe también en compose", False)
            continue
        original = yaml.safe_load(yaml.safe_dump(original))
        if "chain" in spec:
            original["chain"] = {"middlewares": [{"name": n} for n in original["chain"]["middlewares"]]}
        if "forwardAuth" in spec:  # solo cambia el nombre del host (compose: iam-service:8001; k3s: iam-service.turismo-app.svc:8001)
            spec["forwardAuth"]["address"] = spec["forwardAuth"]["address"].replace("iam-service.turismo-app.svc", "iam-service")
        verificar(f"middleware {nombre} igual en compose y k3s", spec == original, f"k3s={spec} compose={original}")

    print("\nCORS del almacenamiento: compose (con plantilla) y k3s (valor fijo) permiten los mismos orígenes")
    cors_k3s = next((d for d in documentos if d["kind"] == "Middleware" and d["metadata"]["name"] == "almacenamiento-cors"), None)
    cors_compose = middlewares_de_compose().get("almacenamiento-cors")
    if cors_k3s and cors_compose:
        # La plantilla {{ env "DOMINIO_PUBLICO" }} solo existe en compose (los CRD no admiten plantillas): se rellena con el dominio provisional
        desde_compose = {re.sub(r'\{\{\s*env "DOMINIO_PUBLICO"\s*\}\}', DOMINIO_PROVISIONAL, o) for o in cors_compose["headers"]["accessControlAllowOriginList"]}
        verificar("orígenes CORS iguales (con el dominio provisional)", desde_compose == set(cors_k3s["spec"]["headers"]["accessControlAllowOriginList"]),
                  f"compose={sorted(desde_compose)} k3s={sorted(cors_k3s['spec']['headers']['accessControlAllowOriginList'])}")
    else:
        verificar("el middleware almacenamiento-cors existe en compose y en k3s", False)

    print("\nCada ruta apunta a un Service que existe")
    existentes = servicios_de_k8s()
    for ns, nombre, puerto in destinos_de_k3s(documentos):
        if nombre == "frontend":
            print(f"  – {nombre}:{puerto}: todavía no tiene manifiestos (ver gateway/README.md)")
            continue
        puertos = existentes.get((ns, nombre))
        verificar(f"{ns}/{nombre}:{puerto}", puertos is not None and puerto in puertos,
                  "no hay ningún Service con ese nombre" if puertos is None else f"el Service expone {sorted(puertos)}")

    print(f"\n{'sin problemas' if not fallos else str(len(fallos)) + ' con problemas'}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
