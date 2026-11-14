from src.domain.texto_plano import a_texto_plano


def test_una_tabla_se_convierte_en_frases():
    tabla = (
        "Estas son tus reservas:\n\n"
        "| Servicio | Fecha | Personas | Estado |\n"
        "|----------|-------|----------|--------|\n"
        "| Buceo recreativo en Taganga | 8 noviembre 2026 | 2 | Confirmada |\n"
        "| Tour de café en Minca | 14 septiembre 2026 | 2 | Finalizada |\n"
        "\n¿Quieres algo más?"
    )

    assert a_texto_plano(tabla) == (
        "Estas son tus reservas:\n\n"
        "• Servicio: Buceo recreativo en Taganga · Fecha: 8 noviembre 2026 · Personas: 2 · "
        "Estado: Confirmada\n"
        "• Servicio: Tour de café en Minca · Fecha: 14 septiembre 2026 · Personas: 2 · "
        "Estado: Finalizada\n\n"
        "¿Quieres algo más?"
    )


def test_quita_negritas_titulos_codigo_y_enlaces():
    texto = (
        "## Opciones\n"
        "Te sugiero **Avistamiento de aves** en *Minca* (`BAJO`).\n"
        "Más en [la ficha](https://ejemplo.com)."
    )

    assert a_texto_plano(texto) == (
        "Opciones\nTe sugiero Avistamiento de aves en Minca (BAJO).\nMás en la ficha."
    )


def test_las_vinetas_se_vuelven_puntos():
    assert a_texto_plano("Opciones:\n- Buceo\n* Tubing\n+ Café") == (
        "Opciones:\n• Buceo\n• Tubing\n• Café"
    )


def test_una_tabla_sin_encabezado_valido_deja_las_celdas():
    assert a_texto_plano("| Buceo | 2 |\n| Tubing | 4 |") == "• Buceo · 2\n• Tubing · 4"


def test_el_texto_normal_no_cambia():
    texto = (
        "Para el 20 de noviembre te sugiero Minca: tranquila y con cupos (2 * 3 = 6).\n\nSuerte."
    )

    assert a_texto_plano(texto) == texto
