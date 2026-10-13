"""Genera Diagrama_Distribucion_Presupuesto.svg, Diagrama_Cronograma_Gantt.svg y Diagrama_Trazabilidad_Global.svg.

Uso: python3 generar_svg_gestion.py <carpeta_destino>
"""
import math
import sys
from xml.sax.saxutils import escape

OUT = sys.argv[1]
FONT = "'Segoe UI', -apple-system, Helvetica, Arial, sans-serif"

STYLE = f"""<defs>
  <style>
    .title {{ font-family: {FONT}; font-size: 17px; font-weight: bold; fill: #0f172a; }}
    .sub {{ font-family: {FONT}; font-size: 12px; fill: #475569; }}
    .h {{ font-family: {FONT}; font-size: 14px; font-weight: bold; fill: #0f172a; }}
    .b {{ font-family: {FONT}; font-size: 13px; font-weight: bold; fill: #0f172a; }}
    .t {{ font-family: {FONT}; font-size: 12px; fill: #334155; }}
    .s {{ font-family: {FONT}; font-size: 11px; fill: #475569; }}
    .v {{ font-family: {FONT}; font-size: 13px; font-weight: bold; fill: #065f46; }}
    .w {{ font-family: {FONT}; font-size: 12px; font-weight: bold; fill: #ffffff; }}
    .big {{ font-family: {FONT}; font-size: 22px; font-weight: bold; fill: #0f172a; }}
  </style>
  <filter id="sh" x="-5%" y="-5%" width="110%" height="120%"><feDropShadow dx="0" dy="1.5" stdDeviation="1.5" flood-opacity="0.12"/></filter>
  <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker>
</defs>"""


def t(x, y, s, cls, anchor="start", fill=None):
    f = f' fill="{fill}"' if fill else ""
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{f}>{escape(s)}</text>'


def svg(w, h, body):
    return "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">',
                      STYLE, f'<rect width="{w}" height="{h}" fill="#ffffff"/>'] + body + ["</svg>"])


def miles(n):
    return f"{n:,}".replace(",", ".")


# ---------------------------------------------------------------- Presupuesto
def donut(cx, cy, r_out, r_in, items, total):
    out, ang = [], -math.pi / 2
    for _, _, val, color in items:
        a2 = ang + 2 * math.pi * val / total
        large = 1 if a2 - ang > math.pi else 0
        p = lambda r, a: (cx + r * math.cos(a), cy + r * math.sin(a))
        x1, y1 = p(r_out, ang); x2, y2 = p(r_out, a2); x3, y3 = p(r_in, a2); x4, y4 = p(r_in, ang)
        out.append(f'<path d="M {x1:.1f} {y1:.1f} A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} '
                   f'L {x3:.1f} {y3:.1f} A {r_in} {r_in} 0 {large} 0 {x4:.1f} {y4:.1f} Z" fill="{color}" stroke="#ffffff" stroke-width="2"/>')
        ang = a2
    return out


def presupuesto():
    A = ("Escenario A — Prototipo académico (13 semanas)", 6900, [
        ("Infraestructura cloud", "VM Linux para k3s, almacenamiento y dominio", 4500, "#3b82f6"),
        ("Servicios de terceros y notificaciones", "API de Gemini, servidor SMTP", 1200, "#10b981"),
        ("Herramientas de desarrollo", "Colaboración y licencias educativas", 300, "#8b5cf6"),
        ("Contingencia (15%)", "Reserva técnica", 900, "#f59e0b"),
    ])
    B = ("Escenario B — Piloto institucional (12 meses)", 20000, [
        ("Infraestructura cloud en alta disponibilidad", "Clúster k3s de 3 nodos, PostgreSQL replicado, S3, CDN", 7200, "#3b82f6"),
        ("Levantamiento de datos y cartografía SIG", "Georreferenciación de 100+ prestadores", 3600, "#10b981"),
        ("Ciberseguridad y cumplimiento Ley 1581", "Pentesting OWASP Top 10, Habeas Data", 3200, "#8b5cf6"),
        ("Alfabetización digital e inclusión MiPyMEs", "Talleres comunitarios y materiales", 3200, "#f59e0b"),
        ("Observabilidad, dominios y certificados", "Prometheus/Grafana, TLS", 1200, "#06b6d4"),
        ("Contingencia (8%)", "Reserva técnica", 1600, "#94a3b8"),
    ])
    W = 1180
    body = [t(30, 36, "Distribución del Presupuesto por Escenario", "title"),
            t(30, 56, "Techo presupuestal: USD 20.000 (SRS, Apéndice D.3). Valores en USD.", "sub")]
    y0 = 80
    for title, total, items in (A, B):
        h = 70 + max(len(items) * 50, 250)
        body.append(f'<rect x="20" y="{y0}" width="{W-40}" height="{h}" rx="10" fill="#f8fafc" stroke="#e2e8f0"/>')
        body.append(t(40, y0 + 30, title, "h"))
        cx, cy = 175, y0 + 50 + (h - 50) / 2
        body += donut(cx, cy, 105, 62, items, total)
        body.append(t(cx, cy + 4, f"${miles(total)}", "big", "middle"))
        body.append(t(cx, cy + 24, "USD total", "s", "middle"))
        ly = y0 + 55
        for name, det, val, color in items:
            body += [f'<rect x="330" y="{ly}" width="790" height="42" rx="6" fill="#ffffff" stroke="#e2e8f0" filter="url(#sh)"/>',
                     f'<rect x="342" y="{ly+11}" width="18" height="20" rx="3" fill="{color}"/>',
                     t(372, ly + 18, name, "b"), t(372, ly + 34, det, "s"),
                     t(1105, ly + 26, f"${miles(val)}  ({val*100/total:.0f}%)", "v", "end")]
            ly += 50
        y0 += h + 20
    open(f"{OUT}/Diagrama_Distribucion_Presupuesto.svg", "w").write(svg(W, y0 + 10, body))


# ----------------------------------------------------------------- Cronograma
def cronograma():
    semanas = ["24 ago", "31 ago", "7 sep", "14 sep", "21 sep", "28 sep", "5 oct", "12 oct", "19 oct",
               "26 oct", "2 nov", "9 nov", "16 nov"]
    fases = [
        ("1. Requerimientos y dominio", "24 ago – 6 sep · SRS ISO/IEC/IEEE 29148", 1, 2, "#3b82f6", "Fase 1"),
        ("2. Comparación arquitectónica", "7 sep – 20 sep · Alternativas y selección", 3, 4, "#6366f1", "Fase 2"),
        ("3. Diseño arquitectónico", "21 sep – 4 oct · Interfaces, datos, ADR", 5, 6, "#8b5cf6", "Fase 3"),
        ("4. Construcción del prototipo", "5 oct – 1 nov · ≥ 60% de casos de uso Must", 7, 10, "#10b981", "Fase 4: Construcción y despliegue en k3s"),
        ("5. Validación y cierre", "2 nov – 14 nov · Pruebas de calidad e informe", 11, 12, "#f59e0b", "Fase 5"),
    ]
    L, cw, top, rh = 360, 62, 118, 58
    W = L + cw * len(semanas) + 30
    H = top + rh * (len(fases) + 1) + 70
    body = [t(30, 36, "Cronograma General de Ejecución (13 semanas · 6 sprints + sustentación)", "title"),
            t(30, 56, "24 de agosto – 17 de noviembre de 2026 · Sustentación: 15, 16 y 17 de noviembre", "sub"),
            f'<rect x="20" y="72" width="{W-40}" height="40" rx="6" fill="#e2e8f0"/>',
            t(36, 97, "FASE Y ENTREGABLE", "b")]
    for i, d in enumerate(semanas):
        x = L + i * cw
        body.append(t(x + cw / 2, 89, f"S{i+1}", "b", "middle"))
        body.append(t(x + cw / 2, 105, d, "s", "middle"))
        body.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{H-60}" stroke="#e2e8f0" stroke-dasharray="3,3"/>')
    for k in range(6):
        x = L + k * 2 * cw
        body.append(f'<rect x="{x+3}" y="{H-56}" width="{2*cw-6}" height="20" rx="4" fill="#f1f5f9" stroke="#cbd5e1"/>')
        body.append(t(x + cw, H - 42, f"Sprint {k+1}", "s", "middle"))
    for j, (name, det, s0, s1, color, label) in enumerate(fases):
        y = top + j * rh
        body += [t(36, y + 24, name, "b"), t(36, y + 42, det, "s"),
                 f'<rect x="{L + (s0-1)*cw + 3}" y="{y+12}" width="{(s1-s0+1)*cw - 6}" height="32" rx="6" fill="{color}" filter="url(#sh)"/>',
                 t(L + (s0 - 1 + (s1 - s0 + 1) / 2) * cw, y + 33, label, "w", "middle")]
    # Sustentación: domingo 15 (fin de S12) a martes 17 (S13)
    y = top + len(fases) * rh
    x0 = L + 11 * cw + cw * 6 / 7
    x1 = L + 12 * cw + cw * 2 / 7 + cw / 7
    body += [t(36, y + 24, "6. Sustentación", "b"), t(36, y + 42, "15, 16 y 17 de noviembre", "s"),
             f'<rect x="{x0:.1f}" y="{y+12}" width="{x1-x0:.1f}" height="32" rx="6" fill="#dc2626" filter="url(#sh)"/>',
             t(x0 - 8, y + 33, "Sustentación 15–17 nov", "b", "end", "#b91c1c")]
    open(f"{OUT}/Diagrama_Cronograma_Gantt.svg", "w").write(svg(W, H, body))


# --------------------------------------------------------------- Trazabilidad
def trazabilidad():
    nodos = [("Stakeholders", ["Turista, Prestador,", "Entidad, Admin"], "#eff6ff", "#3b82f6", "#1e40af"),
             ("Casos de Uso", ["UC1 a UC39", "Alcance funcional"], "#f5f3ff", "#7c3aed", "#5b21b6"),
             ("Requerimientos", ["RF-01 a RF-14", "RNF-01 a RNF-13"], "#f0fdf4", "#10b981", "#065f46"),
             ("Microservicios", ["Módulos 1 a 5", "+ API Gateway y PWA"], "#fffbeb", "#f59e0b", "#92400e"),
             ("Escenarios de Calidad", ["ESC-01 a ESC-09", "Pruebas medibles"], "#ecfdf5", "#059669", "#064e3b")]
    verbos = ["Originan", "Especifican", "Se implementan en", "Se validan con"]
    bw, gap, x0, y = 180, 150, 30, 60
    W = x0 * 2 + bw * 5 + gap * 4
    body = [t(W / 2, 32, "Trazabilidad Global: de las necesidades a la validación", "title", "middle")]
    for i, (name, ds, fill, st, tc) in enumerate(nodos):
        x = x0 + i * (bw + gap)
        body += [f'<rect x="{x}" y="{y}" width="{bw}" height="96" rx="10" fill="{fill}" stroke="{st}" stroke-width="2" filter="url(#sh)"/>',
                 t(x + bw / 2, y + 36, name, "h", "middle", tc),
                 t(x + bw / 2, y + 60, ds[0], "t", "middle", tc),
                 t(x + bw / 2, y + 78, ds[1], "t", "middle", tc)]
        if i < 4:
            ax = x + bw
            body += [f'<path d="M {ax+6} {y+48} L {ax+gap-6} {y+48}" stroke="#334155" stroke-width="2" marker-end="url(#ar)"/>',
                     t(ax + gap / 2, y + 38, verbos[i], "b", "middle", "#0f172a")]
    open(f"{OUT}/Diagrama_Trazabilidad_Global.svg", "w").write(svg(W, 180, body))


presupuesto()
cronograma()
trazabilidad()
