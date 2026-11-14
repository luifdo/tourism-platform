#!/usr/bin/env bash
# Regenera los diagramas SVG de Documents/Pages a partir de las fuentes de esta carpeta.
# Requisitos: Python 3, Java 17+, Graphviz, Node.js 18+ y plantuml.jar (https://plantuml.com/download).
# Uso, desde Documents/Pages/fuentes:
#   PLANTUML_JAR=/ruta/plantuml.jar ./generar_diagramas.sh
set -euo pipefail
cd "$(dirname "$0")"
DEST=..
MMDC="npx -y @mermaid-js/mermaid-cli@11"

# 1. Arquitectura y responsabilidades por módulo (SVG con estilo propio)
python3 generar_svg_arquitectura.py "$DEST"
# Trazabilidad, cronograma y presupuesto
python3 generar_svg_gestion.py "$DEST"

# 2. Diagramas Mermaid (máquina de estados y modelo de datos)
render_mermaid() {
  $MMDC -q -i "$1" -o "$DEST/$2" -c mermaid-config.json -b white
  # Conserva los espacios entre palabras en visores SVG estrictos.
  sed -i.bak '1,3s/<svg /<svg xml:space="preserve" /' "$DEST/$2" && rm -f "$DEST/$2.bak"
}
render_mermaid maquina_estados_reserva.mmd Diagrama_Maquina_Estados_Reserva.svg
render_mermaid modelo_datos_er.mmd Diagrama_Modelo_Datos_ER.svg

# 3. Diagramas UML en PlantUML (casos de uso, despliegue y paquetes)
java -jar "${PLANTUML_JAR:?Defina PLANTUML_JAR}" -charset UTF-8 -tsvg -o "$(cd "$DEST" && pwd)" \
  casos_uso_general.puml casos_uso_turista.puml casos_uso_prestador.puml \
  casos_uso_entidad.puml casos_uso_administrador.puml \
  despliegue_k3s.puml despliegue_turista.puml despliegue_prestador.puml \
  despliegue_entidad.puml despliegue_administrador.puml paquetes_microservicio.puml

echo "Diagramas regenerados en Documents/Pages"
