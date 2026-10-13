"""Genera Diagrama_Arquitectura_Microservicios.svg y Diagrama_Modulos_Responsabilidades.svg.

Uso: python3 generar_svg_arquitectura.py <carpeta_destino>
"""
import sys
from xml.sax.saxutils import escape

OUT = sys.argv[1]
FONT = "'Segoe UI', -apple-system, Helvetica, Arial, sans-serif"


def t(x, y, s, cls, anchor="start", fill=None):
    f = f' fill="{fill}"' if fill else ""
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{f}>{escape(s)}</text>'


def box(x, y, w, h, fill, stroke, rx=8, dash=None, sw=1.8):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d} filter="url(#sh)"/>')


def cyl(cx, y, w, h, fill, stroke):
    rx, ry = w / 2, 9
    x0, x1 = cx - rx, cx + rx
    return (f'<path d="M {x0} {y+ry} A {rx} {ry} 0 0 1 {x1} {y+ry} L {x1} {y+h-ry} '
            f'A {rx} {ry} 0 0 1 {x0} {y+h-ry} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.6" filter="url(#sh)"/>'
            f'<path d="M {x0} {y+ry} A {rx} {ry} 0 0 0 {x1} {y+ry}" fill="none" stroke="{stroke}" stroke-width="1.6"/>')


def line(x1, y1, x2, y2, cls, marker=None):
    m = f' marker-end="url(#{marker})"' if marker else ""
    return f'<path d="M {x1} {y1} L {x2} {y2}" class="{cls}"{m}/>'


DEFS = f"""<defs>
  <style>
    .title {{ font-family: {FONT}; font-size: 17px; font-weight: bold; fill: #0f172a; }}
    .sub {{ font-family: {FONT}; font-size: 12px; fill: #64748b; }}
    .nt {{ font-family: {FONT}; font-size: 13px; font-weight: bold; }}
    .nd {{ font-family: {FONT}; font-size: 11px; font-style: italic; }}
    .gt {{ font-family: {FONT}; font-size: 13px; font-weight: bold; fill: #334155; }}
    .lbl {{ font-family: {FONT}; font-size: 10.5px; fill: #475569; }}
    .lev {{ font-family: {FONT}; font-size: 10.5px; fill: #b45309; }}
    .ci {{ font-family: {FONT}; font-size: 12px; }}
    .ct {{ font-family: {FONT}; font-size: 14px; font-weight: bold; }}
    .wire {{ stroke: #64748b; stroke-width: 1.6; fill: none; }}
    .wdb {{ stroke: #047857; stroke-width: 1.4; fill: none; }}
    .wev {{ stroke: #d97706; stroke-width: 1.6; stroke-dasharray: 5,3; fill: none; }}
    .wai {{ stroke: #c026d3; stroke-width: 1.6; stroke-dasharray: 3,3; fill: none; }}
    .wext {{ stroke: #334155; stroke-width: 2.2; fill: none; }}
  </style>
  <filter id="sh" x="-5%" y="-5%" width="110%" height="120%"><feDropShadow dx="0" dy="1.5" stdDeviation="1.5" flood-opacity="0.12"/></filter>
  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker>
  <marker id="ae" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#d97706"/></marker>
  <marker id="ai" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#c026d3"/></marker>
  <marker id="ax" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker>
</defs>"""


def arquitectura():
    W, H = 1290, 960
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="100%">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         t(645, 30, "Arquitectura de Microservicios — Plataforma Digital de Turismo Santa Marta", "title", "middle"),
         t(645, 50, "5 microservicios Python + FastAPI en contenedores, desplegados en Kubernetes (k3s)", "sub", "middle")]

    # Clientes
    o += [box(380, 66, 420, 54, "#eff6ff", "#2563eb"),
          t(590, 88, "Clientes web y móviles — PWA (Vue 3)", "nt", "middle", "#1e40af"),
          t(590, 106, "Turistas · Prestadores · Entidades · Administradores · caché sin conexión", "nd", "middle", "#2563eb")]
    # Clúster
    o += [f'<rect x="18" y="138" width="1052" height="800" rx="12" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="7,4"/>',
          t(32, 160, "Clúster Kubernetes (k3s) — Escenario A: 1 nodo · Escenario B: varios nodos", "gt")]
    o.append(line(590, 120, 590, 170, "wext", "ax"))
    o.append(t(600, 150, "HTTPS / REST (JSON)", "lbl"))

    # Gateway
    o += [box(300, 172, 580, 58, "#f5f3ff", "#7c3aed"),
          t(590, 195, "API Gateway — Traefik (Ingress de k3s)", "nt", "middle", "#5b21b6"),
          t(590, 214, "Terminación TLS · ForwardAuth (JWT validado por M1) · Rate Limiting · CORS · enrutamiento por prefijo", "nd", "middle", "#7c3aed")]

    xs = [35, 241, 447, 653, 859]
    wbox = 196
    cx = [x + wbox / 2 for x in xs]
    mods = [
        ("Módulo 1", "Seguridad & IAM", ["Auth JWT · RBAC", "Auditoría · RNT/RUT"], "#f0fdf4", "#16a34a", "#14532d", "#15803d", "/api/iam"),
        ("Módulo 2", "Catálogo, GIS & Destino", ["Atractivos · PostGIS · OSM", "Analítica · Alertas · Correos"], "#f0fdf4", "#16a34a", "#14532d", "#15803d", "/api/catalog"),
        ("Módulo 3", "Reservas & Cupos", ["Cupos · Solicitudes", "Máquina de estados"], "#f0fdf4", "#16a34a", "#14532d", "#15803d", "/api/bookings"),
        ("Módulo 4", "Reseñas & Moderación", ["Reseñas · Respuestas", "Reportes · Moderación"], "#f0fdf4", "#16a34a", "#14532d", "#15803d", "/api/reviews"),
        ("Módulo 5", "IA & Recomendación", ["Chatbot · Herramientas", "Gemini · RNF-08"], "#fdf4ff", "#c026d3", "#701a75", "#a21caf", "/api/recommendations"),
    ]
    MY, MH = 290, 100
    MB = MY + MH + 12
    for i, (n, name, ds, fill, st, tc, dc, route) in enumerate(mods):
        x0 = 590 + (cx[i] - 590) * 0.55
        o.append(line(x0, 230, cx[i], MY, "wire", "a"))
        mx, my = (x0 + cx[i]) / 2, (230 + MY) / 2
        if i == 2:
            o.append(t(mx + 8, my + 4, route, "lbl", "start"))
        else:
            o.append(t(mx + (-8 if i < 2 else 8), my - 4, route, "lbl", "end" if i < 2 else "start"))
        o += [box(xs[i], MY, wbox, MH + 12, fill, st),
              t(cx[i], MY + 20, n, "nt", "middle", tc),
              t(cx[i], MY + 38, name, "nt", "middle", tc),
              t(cx[i], MY + 60, ds[0], "nd", "middle", dc),
              t(cx[i], MY + 77, ds[1], "nd", "middle", dc),
              t(cx[i], MY + 100, "contenedor · HPA · /health · /metrics", "lbl", "middle")]

    # Bases de datos (líneas primero, detrás del broker)
    DBY = 600
    dbs = [("PostgreSQL", "iam_db"), ("PostgreSQL + PostGIS", "catalog_db"), ("PostgreSQL", "booking_db"),
           ("PostgreSQL (JSONB)", "review_db"), ("PostgreSQL", "recommendation_db")]
    for i in range(5):
        o.append(line(cx[i], MB, cx[i], DBY, "wdb"))

    # Herramientas del chatbot (M5 -> M2, M3, M4)
    ty = MB + 20
    o.append(f'<path d="M {cx[4]-30} {MB} L {cx[4]-30} {ty} L {cx[1]+30} {ty}" class="wai"/>')
    for i in (1, 2, 3):
        o.append(line(cx[i] + 30, ty, cx[i] + 30, MB + 2, "wai", "ai"))
    o.append(t(cx[3] + 34, ty - 5, "herramientas (solo lectura)", "lbl", "start", "#a21caf"))

    # Broker
    BY = 462
    o += [box(35, BY, 1020, 90, "#fffbeb", "#d97706"),
          t(545, BY + 22, "RabbitMQ — exchange turismo.eventos (topic) · cola por consumidor · reintentos y DLQ", "nt", "middle", "#78350f"),
          t(545, BY + 42, "Publican: M1 prestador.aprobado · M3 reserva.solicitada / confirmada / rechazada / cancelada / finalizada · M4 resena.publicada", "lev", "middle"),
          t(545, BY + 59, "M2, M3 y M4 publican además auditoria.registrada", "lev", "middle"),
          t(545, BY + 77, "Consumen: M1 auditoria.registrada (bitácora) · M2 reservas, reseñas y prestadores (correos y métricas) · M4 reserva.finalizada (habilita reseña)", "lev", "middle")]
    # flechas de eventos
    for i, pub, con in [(0, True, True), (1, True, True), (2, True, False), (3, True, True)]:
        if pub:
            o.append(line(cx[i] - 26, MB + 2, cx[i] - 26, BY - 2, "wev", "ae"))
        if con:
            o.append(line(cx[i] - 50, BY - 2, cx[i] - 50, MB + 2, "wev", "ae"))

    for i, (a, b) in enumerate(dbs):
        o.append(cyl(cx[i], DBY, 176, 70, "#f8fafc", "#475569"))
        o.append(t(cx[i], DBY + 36, a, "nt", "middle", "#0f172a"))
        o.append(t(cx[i], DBY + 55, b, "nd", "middle", "#475569"))

    # Segunda fila: Valkey, SeaweedFS, Observabilidad
    RY = 708
    o += [box(35, RY, 300, 78, "#fff1f2", "#e11d48"),
          t(185, RY + 24, "Valkey (caché en memoria)", "nt", "middle", "#881337"),
          t(185, RY + 44, "Caché de catálogo · sesiones del chatbot", "nd", "middle", "#be123c"),
          t(185, RY + 62, "idempotencia de eventos — usado por M1, M2, M3 y M5", "nd", "middle", "#be123c"),
          box(350, RY, 300, 78, "#f8fafc", "#475569"),
          t(500, RY + 24, "SeaweedFS (almacenamiento S3)", "nt", "middle", "#0f172a"),
          t(500, RY + 44, "Documentos RNT / RUT (M1)", "nd", "middle", "#475569"),
          t(500, RY + 62, "Respaldos de PostgreSQL (CloudNativePG)", "nd", "middle", "#475569"),
          box(665, RY, 390, 78, "#f0f9ff", "#0284c7"),
          t(860, RY + 24, "Observabilidad — Prometheus · Grafana · Loki", "nt", "middle", "#0c4a6e"),
          t(860, RY + 44, "Métricas /metrics y sondas /health de cada servicio", "nd", "middle", "#0369a1"),
          t(860, RY + 62, "Logs con X-Correlation-ID · tableros de latencia p95", "nd", "middle", "#0369a1")]

    o.append(t(545, 818, "Persistencia políglota consolidada: un clúster PostgreSQL con una base lógica por servicio (Database-per-Service) + Valkey + almacenamiento S3.", "lbl", "middle"))
    o.append(t(545, 834, "Ningún servicio accede a la base de datos de otro; los datos ajenos se obtienen por REST o por eventos.", "lbl", "middle"))

    # Leyenda
    LY = 866
    o += [line(40, LY, 80, LY, "wire", "a"), t(88, LY + 4, "REST síncrono", "lbl"),
          line(200, LY, 240, LY, "wev", "ae"), t(248, LY + 4, "Evento asíncrono (publica ↓ / consume ↑)", "lbl"),
          line(480, LY, 520, LY, "wai", "ai"), t(528, LY + 4, "Herramienta del chatbot", "lbl"),
          line(680, LY, 720, LY, "wdb"), t(728, LY + 4, "Acceso a su propia base de datos", "lbl"),
          line(920, LY, 960, LY, "wext", "ax"), t(968, LY + 4, "Llamada externa", "lbl")]
    o.append(t(40, 906, "Fuera del clúster: servicios externos (columna derecha). Gemini es la única dependencia propietaria (excepción justificada a la prioridad FOSS, SRS §2.4.1).", "lbl"))

    # Externos
    ex = [(300, "Google Gemini API", ["Servicio externo de IA", "consumido por M5"], cx[4] + wbox / 2, MY + 50),
          (470, "Servidor SMTP", ["Postal o institucional", "correos de M1 y M2"], None, None),
          (620, "OpenStreetMap / Nominatim", ["Geocodificación (M2)", "teselas del mapa (PWA)"], None, None)]
    for y, name, ds, fx, fy in ex:
        o += [box(1088, y, 186, 76, "#f1f5f9", "#64748b", dash="4,3"),
              t(1181, y + 24, name, "nt", "middle", "#0f172a"),
              t(1181, y + 44, ds[0], "nd", "middle", "#475569"),
              t(1181, y + 62, ds[1], "nd", "middle", "#475569")]
        if fx:
            o.append(line(fx, y + 38, 1086, y + 38, "wext", "ax"))
            o.append(t(1071, y + 31, "HTTPS", "lbl", "middle"))
    o.append("</svg>")
    open(f"{OUT}/Diagrama_Arquitectura_Microservicios.svg", "w").write("\n".join(o))


def modulos():
    W, H = 1060, 560
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="100%">', DEFS,
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         t(530, 30, "Responsabilidades por Módulo", "title", "middle"),
         t(530, 50, "5 microservicios (Bounded Contexts) y capa transversal", "sub", "middle")]
    cards = [
        ("Módulo 1: Seguridad & IAM", "#eff6ff", "#3b82f6", "#dbeafe", "#1e3a8a",
         ["Autenticación JWT (RS256) y ForwardAuth", "Control de acceso RBAC (4 roles)", "Verificación de prestadores (UC37, UC28)",
          "Bitácora de auditoría inmutable (RNF-10)", "Consume auditoria.registrada de todos"]),
        ("Módulo 2: Catálogo, GIS & Destino", "#f0fdf4", "#10b981", "#d1fae5", "#064e3b",
         ["Atractivos, eventos y perfiles de prestador", "Búsqueda espacial con PostGIS y OSM", "Demanda y capacidad de carga por eventos",
          "Tableros, reportes CSV/PDF y alertas", "Correos transaccionales (UC36)", "Consultas para el chatbot"]),
        ("Módulo 3: Reservas & Cupos", "#fefce8", "#eab308", "#fef9c3", "#713f12",
         ["Cupos con bloqueo transaccional", "Máquina de estados de la reserva", "Expiración de solicitudes sin respuesta (48 h)",
          "Historial del turista y panel del prestador", "Consultas para el chatbot"]),
        ("Módulo 4: Reseñas & Moderación", "#fff1f2", "#f43f5e", "#ffe4e6", "#881337",
         ["Reseñas de reservas finalizadas (RF-14)", "Respuestas públicas de prestadores", "Reporte de contenido inapropiado (UC39)",
          "Moderación manual del Administrador (UC29)", "Consultas para el chatbot"]),
        ("Módulo 5: IA & Recomendación", "#fdf4ff", "#d946ef", "#fae8ff", "#701a75",
         ["Chatbot en español e inglés", "Integración con Gemini (API externa)", "Herramientas de solo lectura",
          "Respuestas justificadas (RNF-08)", "Registro en RECOMENDACION_LOG"]),
        ("Capa transversal", "#f8fafc", "#64748b", "#e2e8f0", "#0f172a",
         ["PWA con caché sin conexión (RNF-13)", "Traefik: TLS, ForwardAuth, rate limiting", "RabbitMQ: eventos y auditoría",
          "Prometheus, Grafana y Loki", "Despliegue en k3s con HPA (RNF-12)"]),
    ]
    cw, ch = 320, 215
    for i, (title, fill, st, head, tc, items) in enumerate(cards):
        x = 25 + (i % 3) * (cw + 25)
        y = 70 + (i // 3) * (ch + 25)
        o += [box(x, y, cw, ch, fill, st),
              f'<path d="M {x} {y+36} L {x} {y+8} Q {x} {y} {x+8} {y} L {x+cw-8} {y} Q {x+cw} {y} {x+cw} {y+8} L {x+cw} {y+36} Z" fill="{head}"/>',
              t(x + 16, y + 24, title, "ct", "start", tc)]
        for j, it in enumerate(items):
            o.append(t(x + 18, y + 62 + j * 25, "• " + it, "ci", "start", tc))
    o.append("</svg>")
    open(f"{OUT}/Diagrama_Modulos_Responsabilidades.svg", "w").write("\n".join(o))


arquitectura()
modulos()
