"""Usuarios, codigos de acceso y sesiones.

Acceso sin contrasenas: un codigo de 6 digitos llega al correo institucional y
abre una sesion. El correo institucional prueba que es estudiante (D-15).

Ni el codigo ni el token de sesion se guardan en claro: se guarda su HMAC. Quien
lea la base de datos no puede entrar con lo que ve.
"""

import hashlib
import hmac
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from umarket.compartido.dominio.errores import ReglaIncumplida


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def huella(secreto_servidor: str, valor: str) -> str:
    """HMAC-SHA256 del valor con el secreto del servidor."""
    return hmac.new(secreto_servidor.encode(), valor.encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Usuario:
    id: UUID
    campus_id: str
    correo: str
    nombre: str
    creado_en: datetime


@dataclass(frozen=True)
class CodigoAcceso:
    id: UUID
    correo: str
    codigo_huella: str
    creado_en: datetime
    expira_en: datetime
    intentos: int = 0
    usado_en: datetime | None = None

    def vigente(self, ahora: datetime, max_intentos: int) -> bool:
        return self.usado_en is None and ahora < self.expira_en and self.intentos < max_intentos

    def coincide(self, huella_recibida: str) -> bool:
        return hmac.compare_digest(self.codigo_huella, huella_recibida)

    def con_intento_fallido(self) -> "CodigoAcceso":
        return replace(self, intentos=self.intentos + 1)

    def usado(self, ahora: datetime) -> "CodigoAcceso":
        return replace(self, usado_en=ahora)


@dataclass(frozen=True)
class Sesion:
    token_huella: str
    usuario_id: UUID
    expira_en: datetime


def validar_nombre(nombre: str) -> str:
    limpio = " ".join(nombre.split())
    if not 2 <= len(limpio) <= 60:
        raise ReglaIncumplida("nombre_invalido", "El nombre debe tener entre 2 y 60 caracteres.")
    return limpio
