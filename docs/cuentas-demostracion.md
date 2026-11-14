# Cuentas de demostración

Cuentas cargadas el 13 de noviembre de 2026 en la plataforma pública https://3-141-142-12.sslip.io para la presentación del proyecto.

> **La contraseña no está en este archivo**, porque el repositorio es público. Es la misma para todas las cuentas de prestador, turista y Entidad. Pídesela a Luis Fernando, o léela en la VM:
>
> ```bash
> ssh -i ~/.ssh/tourism-aws.pem ubuntu@3.141.142.12 cat ~/semilla-credenciales.txt
> ```

## Cómo entrar

* Escribe el correo **completo, con el `+` y lo que sigue**. Cada dirección es una cuenta distinta: `luifsanchez@gmail.com` sin el `+` no existe en la plataforma.
* Los avisos de todas las cuentas llegan a un mismo buzón de Gmail, que ignora lo que va después del `+`. El campo "Para:" del correo dice a qué cuenta va dirigido.
* Para tener dos sesiones a la vez (turista y prestador), usa una ventana normal y otra de incógnito.

## Cuentas

| Rol | Correo | Empresa (ficticia) | Servicios |
|---|---|---|---|
| Prestador | `luifsanchez+senderos@gmail.com` | Senderos de la Sierra SAS | Trekking a Ciudad Perdida (Teyuna), 4 días · Caminata guiada al Cabo San Juan, Parque Tayrona · Avistamiento de aves en la cuchilla de San Lorenzo |
| Prestador | `luifsanchez+marcaribe@gmail.com` | Mar Caribe Experiencias SAS | Bautizo de buceo en Taganga · Lancha Taganga – Playa Cristal · Alquiler de kayak en El Rodadero |
| Prestador | `luifsanchez+casaminca@gmail.com` | Casa Montaña Minca SAS | Hostal en Minca con vista a la Sierra · Tour de café y cacao en Minca |
| Prestador | `luifsanchez+memoriasamaria@gmail.com` | Memoria Samaria Tours SAS | Tour cultural: Centro Histórico y Quinta de San Pedro Alejandrino · Hotel boutique en el Centro Histórico · Restaurante de cocina samaria |
| Prestador | `luifsanchez+palomino@gmail.com` | Río Palomino Ecoturismo SAS | Ecohotel de cabañas en Palomino · Tubing por el río Palomino |
| Turista | `luifsanchez+turista@gmail.com` | — | Cuenta limpia para el ciclo de demostración (abajo) |
| Entidad | `luifsanchez+entidad@gmail.com` | — | Daniela Rojas. Panel de la Entidad con analítica, zonas y alertas |
| Admin | `admin@turismo.local` | — | Contraseña en `ADMIN_PASSWORD` de `infra/.env` en la VM |

### Turistas con historial

Ocho turistas con reservas en todos los estados (confirmadas, pendientes, rechazadas y canceladas) y reseñas ya escritas. Sirven para mostrar "Mis reservas" y "Mis reseñas" con datos.

| Correo | Nombre | Idioma |
|---|---|---|
| `luifsanchez+viajero1@gmail.com` | Camila Restrepo | Español |
| `luifsanchez+viajero2@gmail.com` | Andrés Felipe Ortiz | Español |
| `luifsanchez+viajero3@gmail.com` | Valeria Gómez | Español |
| `luifsanchez+viajero4@gmail.com` | Sebastián Muñoz | Español |
| `luifsanchez+viajero5@gmail.com` | Laura Jiménez | Español |
| `luifsanchez+viajero6@gmail.com` | Emma Schneider | Inglés |
| `luifsanchez+viajero7@gmail.com` | Lucas Martin | Inglés |
| `luifsanchez+viajero8@gmail.com` | Sofía Herrera | Español |

### Qué puede hacer cada rol en la web

* **Turista:** buscar, ver el detalle, reservar, abrir **Mis reservas**, escribir reseñas en **Mis reseñas** y usar el asistente IA.
* **Prestador:** en **Mi panel**, confirmar o rechazar solicitudes, manejar el calendario de cupos, crear y editar servicios, responder reseñas, ver métricas y editar el perfil del negocio.
* **Entidad:** en **Panel de la Entidad**, tablero de planificación, demanda por día, mapa de calor por zona, intenciones de visita, reporte CSV y publicar, editar o retirar alertas oficiales.
* **Admin:** en **Administración**, usuarios y roles, aprobación de prestadores (RNT y RUT), moderación de reseñas y bitácora de auditoría. También entra al panel de la Entidad.
* **Todos:** en **Mi perfil** (menú de la cuenta), nombre, idioma, contraseña y borrado de la cuenta.

## Ciclo de demostración

1. Como **turista**, abre un servicio (por ejemplo, *Alquiler de kayak en El Rodadero*), elige fecha y personas y solicita la reserva.
2. Llega un correo de nueva solicitud dirigido a `+marcaribe`.
3. Como **marcaribe**, entra en **Mi panel → Solicitudes** y pulsa **Confirmar** (o **Rechazar** con un motivo).
4. Llega el correo de confirmación dirigido a `+turista`, y la reserva aparece confirmada en **Mis reservas**.

## Sobre los datos

* **Lugares, coordenadas y precios:** reales o aproximados (COP, 2026).
* **Empresas:** ficticias, para no suplantar a negocios reales. Los sitios oficiales (Parque Tayrona, Quinta de San Pedro Alejandrino) se ofrecen como **tours guiados**, no como venta de la entrada.
* **Calendarios:** cada servicio tiene 90 días de cupos abiertos, hasta el 11 de febrero de 2027.
* **Fotos:** de [Wikimedia Commons](https://commons.wikimedia.org), con licencia libre (CC BY, CC BY-SA o dominio público). Cada descripción termina con el crédito del autor y la licencia, que la licencia exige; no se debe quitar.
* **Cuentas de prueba:** las cuentas `@example.com` que dejan las pruebas automáticas (`gateway/pruebas/flujo_completo.py`) están **desactivadas** con el motivo "Datos de prueba". No se borraron, porque la bitácora de auditoría es inmutable.
* **Documentos RNT y RUT:** los de los prestadores son PDF de relleno, aprobados por el Admin.
* **Zonas:** 9, con polígonos aproximados: Centro Histórico, El Rodadero, Taganga, Bahía Concha, Minca, Parque Tayrona, Palomino, Ciudad Perdida (Teyuna) y Cuchilla de San Lorenzo. Bahía Concha no tiene servicios, por eso sale sin nivel en el mapa.
* **Alertas oficiales:** 7, publicadas por la Entidad: una crítica (corrientes en Palomino), tres preventivas (normas de ingreso a Tayrona, lluvias en el sendero a Teyuna y estado del mar para la lancha de Taganga) y tres informativas (vía a Minca, temporada alta en el Centro Histórico y operadores con RNT en Taganga). Son recomendaciones generales: no anuncian cierres con fecha ni hablan en nombre de una autoridad real.
* **Reservas futuras:** unas 300 en los próximos 45 días, hechas por el flujo normal. Hay 12 solicitudes pendientes para mostrar el panel del prestador.
* **Historial:** los 45 días anteriores al 13 de noviembre se cargaron directamente en la base de la analítica (reservas finalizadas e intenciones de visita), porque la plataforma no deja reservar en fechas pasadas. Ese historial alimenta el panel de la Entidad y las métricas del prestador, pero no aparece en "Mis reservas" de los turistas.
* **Reseñas:** 32, con calificación por aspectos, y 19 respuestas de los prestadores.

## Después de la presentación

La plataforma es pública y la contraseña es compartida. Al terminar, desactiva estas cuentas desde **Administración → Usuarios** o cámbiales la contraseña, borra el historial cargado en la analítica y apaga la VM.
