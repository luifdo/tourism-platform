import asyncio
import sys

# psycopg en modo asíncrono no funciona con el bucle Proactor, que es el de Windows por
# defecto. En el contenedor (Linux) no hace falta.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
