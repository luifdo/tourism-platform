from datetime import datetime

from pydantic import BaseModel

from app.application.dto.subida_imagen import SubidaImagen


class SubidaImagenRespuesta(BaseModel):
    subida_url: str
    url_publica: str
    expira_en: datetime

    @classmethod
    def desde(cls, subida: SubidaImagen) -> "SubidaImagenRespuesta":
        return cls(
            subida_url=subida.subida_url, url_publica=subida.url_publica, expira_en=subida.expira_en
        )
