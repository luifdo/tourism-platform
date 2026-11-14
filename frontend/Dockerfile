# PWA de producción: se compila con Node y la sirve Nginx. Desde la raíz del repositorio:
#   docker build -t frontend:local frontend
# VITE_API_MOCK y VITE_BASE se fijan al COMPILAR: quedan dentro de los archivos que baja el navegador, así
# que aquí nunca van claves ni secretos (todo lo que empieza con VITE_ es público).

# ---------- Etapa 1: compilar ----------
FROM node:22-alpine AS build
WORKDIR /app

# Solo las dependencias, para que esta capa se reutilice mientras no cambie el lockfile.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# false = habla con el gateway real (iam, catalog, booking, review y recommendation) en vez de los servicios
# simulados del navegador. La base es "/" porque en el servidor la PWA cuelga de la raíz del dominio.
ARG VITE_API_MOCK=false
ARG VITE_BASE=/
ENV VITE_API_MOCK=$VITE_API_MOCK \
    VITE_BASE=$VITE_BASE
RUN npm run build

# ---------- Etapa 2: servir ----------
# Versión sin privilegios: corre como usuario "nginx" y escucha en el 8080 (como piden los manifiestos de k8s).
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
# nginx.conf es una plantilla: la imagen oficial sustituye variables de entorno al arrancar y escribe /etc/nginx/conf.d/default.conf.
# El filtro deja intactas las variables propias de nginx ($uri, $host...) y solo cambia las que empiezan con CSP_.
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER=^CSP_ \
    CSP_ALMACENAMIENTO=''
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/index.html"]
