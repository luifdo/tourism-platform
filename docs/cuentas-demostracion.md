# Cuentas de demostración

Cuentas cargadas el 13 de noviembre de 2026 en la plataforma pública https://3-141-142-12.sslip.io para la presentación del proyecto.

> **La contraseña no está en este archivo**, porque el repositorio es público. Es la misma para todas las cuentas de prestador y de turista. Pídesela a Luis Fernando, o léela en la VM:
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
| Turista | `luifsanchez+turista@gmail.com` | — | Reservar, ver y cancelar sus reservas y usar el asistente IA |
| Admin | `admin@turismo.local` | — | Contraseña en `ADMIN_PASSWORD` de `infra/.env` en la VM. Hoy no tiene pantallas en la PWA: se usa por la API |

Qué puede hacer cada rol en la web:

* **Turista:** buscar, ver el detalle, reservar y abrir "Mis reservas".
* **Prestador:** en **Mi panel**, confirmar o rechazar solicitudes y manejar el calendario de cupos.

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

## Después de la presentación

La plataforma es pública y la contraseña es compartida. Al terminar, desactiva estas cuentas desde la API de Admin o cámbiales la contraseña, y apaga la VM.
