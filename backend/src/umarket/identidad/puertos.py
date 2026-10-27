from datetime import datetime
from typing import Protocol
from uuid import UUID

from umarket.compartido.aplicacion.puertos import UnidadDeTrabajo
from umarket.identidad.dominio.modelos import CodigoAcceso, Sesion, Usuario


class RepositorioUsuarios(Protocol):
    def por_correo(self, correo: str) -> Usuario | None: ...

    def por_id(self, usuario_id: UUID) -> Usuario | None: ...

    def agregar(self, usuario: Usuario, version_terminos: str) -> None:
        """Guarda el usuario y su consentimiento (Ley 1581), juntos."""
        ...


class RepositorioCodigos(Protocol):
    def agregar(self, codigo: CodigoAcceso) -> None: ...

    def ultimo_vigente(self, correo: str, ahora: datetime) -> CodigoAcceso | None: ...

    def guardar(self, codigo: CodigoAcceso) -> None: ...

    def emitidos_desde(self, correo: str, desde: datetime) -> int: ...


class RepositorioSesiones(Protocol):
    def agregar(self, sesion: Sesion) -> None: ...

    def vigente(self, token_huella: str, ahora: datetime) -> Sesion | None: ...

    def eliminar(self, token_huella: str) -> None: ...


class BuscadorCampus(Protocol):
    def por_dominio_de_correo(self, dominio: str) -> str | None:
        """El id del campus que admite ese dominio, o None."""
        ...


class UnidadIdentidad(UnidadDeTrabajo, Protocol):
    @property
    def usuarios(self) -> RepositorioUsuarios: ...

    @property
    def codigos(self) -> RepositorioCodigos: ...

    @property
    def sesiones(self) -> RepositorioSesiones: ...

    @property
    def campus(self) -> BuscadorCampus: ...


class EnviadorCorreo(Protocol):
    def enviar_codigo(self, correo: str, codigo: str) -> None: ...


class GeneradorSecretos(Protocol):
    def codigo(self) -> str:
        """Seis digitos."""
        ...

    def token(self) -> str: ...
