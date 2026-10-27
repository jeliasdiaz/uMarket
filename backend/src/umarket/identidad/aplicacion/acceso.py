"""Casos de uso del acceso: pedir codigo, verificarlo, resolver y cerrar sesion."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from umarket.compartido.dominio.errores import (
    LimiteExcedido,
    NoAutenticado,
    ReglaIncumplida,
)
from umarket.compartido.dominio.reloj import Reloj
from umarket.identidad.dominio.modelos import (
    CodigoAcceso,
    Sesion,
    Usuario,
    huella,
    normalizar_correo,
    validar_nombre,
)
from umarket.identidad.puertos import EnviadorCorreo, GeneradorSecretos, UnidadIdentidad


@dataclass(frozen=True)
class PoliticaAcceso:
    secreto_servidor: str
    minutos_codigo: int = 10
    max_intentos: int = 5
    max_codigos_por_ventana: int = 3
    dias_sesion: int = 30
    version_terminos: str = "2026-10"


@dataclass(frozen=True)
class UsuarioSesion:
    id: UUID
    campus_id: str
    correo: str
    nombre: str


def _vista(usuario: Usuario) -> UsuarioSesion:
    return UsuarioSesion(usuario.id, usuario.campus_id, usuario.correo, usuario.nombre)


class SolicitarCodigo:
    def __init__(
        self,
        unidad: Callable[[], UnidadIdentidad],
        correo: EnviadorCorreo,
        secretos: GeneradorSecretos,
        reloj: Reloj,
        politica: PoliticaAcceso,
    ) -> None:
        self._unidad = unidad
        self._correo = correo
        self._secretos = secretos
        self._reloj = reloj
        self._politica = politica

    def ejecutar(self, correo: str) -> None:
        correo = normalizar_correo(correo)
        ahora = self._reloj.ahora()
        ventana = timedelta(minutes=self._politica.minutos_codigo)
        with self._unidad() as u:
            if u.campus.por_dominio_de_correo(correo.rpartition("@")[2]) is None:
                raise ReglaIncumplida(
                    "correo_no_institucional",
                    "Usa el correo de tu universidad: ese dominio no esta habilitado.",
                )
            if u.codigos.emitidos_desde(correo, ahora - ventana) >= (
                self._politica.max_codigos_por_ventana
            ):
                raise LimiteExcedido(
                    "demasiados_codigos", "Ya pediste varios codigos. Espera unos minutos."
                )
            codigo = self._secretos.codigo()
            u.codigos.agregar(
                CodigoAcceso(
                    id=uuid4(),
                    correo=correo,
                    codigo_huella=huella(self._politica.secreto_servidor, codigo),
                    creado_en=ahora,
                    expira_en=ahora + ventana,
                )
            )
            u.confirmar()
        self._correo.enviar_codigo(correo, codigo)


@dataclass(frozen=True)
class SesionIniciada:
    token: str
    usuario: UsuarioSesion
    es_nuevo: bool


class VerificarCodigo:
    def __init__(
        self,
        unidad: Callable[[], UnidadIdentidad],
        secretos: GeneradorSecretos,
        reloj: Reloj,
        politica: PoliticaAcceso,
    ) -> None:
        self._unidad = unidad
        self._secretos = secretos
        self._reloj = reloj
        self._politica = politica

    def ejecutar(
        self, correo: str, codigo: str, nombre: str | None = None, acepta_terminos: bool = False
    ) -> SesionIniciada:
        correo = normalizar_correo(correo)
        ahora = self._reloj.ahora()
        with self._unidad() as u:
            vigente = u.codigos.ultimo_vigente(correo, ahora)
            if vigente is None or not vigente.vigente(ahora, self._politica.max_intentos):
                raise NoAutenticado("codigo_vencido", "El codigo vencio o ya se uso. Pide otro.")
            if not vigente.coincide(huella(self._politica.secreto_servidor, codigo.strip())):
                u.codigos.guardar(vigente.con_intento_fallido())
                u.confirmar()
                raise NoAutenticado("codigo_invalido", "Ese codigo no es correcto.")

            usuario = u.usuarios.por_correo(correo)
            es_nuevo = usuario is None
            if usuario is None:
                if not acepta_terminos:
                    raise ReglaIncumplida(
                        "falta_consentimiento",
                        "Para crear tu cuenta debes aceptar el tratamiento de datos.",
                    )
                campus_id = u.campus.por_dominio_de_correo(correo.rpartition("@")[2])
                if campus_id is None:
                    raise ReglaIncumplida("correo_no_institucional", "Dominio no habilitado.")
                usuario = Usuario(
                    id=uuid4(),
                    campus_id=campus_id,
                    correo=correo,
                    nombre=validar_nombre(nombre or correo.partition("@")[0]),
                    creado_en=ahora,
                )
                u.usuarios.agregar(usuario, self._politica.version_terminos)

            u.codigos.guardar(vigente.usado(ahora))
            token = self._secretos.token()
            u.sesiones.agregar(
                Sesion(
                    token_huella=huella(self._politica.secreto_servidor, token),
                    usuario_id=usuario.id,
                    expira_en=ahora + timedelta(days=self._politica.dias_sesion),
                )
            )
            u.confirmar()
        return SesionIniciada(token=token, usuario=_vista(usuario), es_nuevo=es_nuevo)


class ResolverSesion:
    def __init__(
        self, unidad: Callable[[], UnidadIdentidad], reloj: Reloj, politica: PoliticaAcceso
    ) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._politica = politica

    def ejecutar(self, token: str) -> UsuarioSesion | None:
        with self._unidad() as u:
            sesion = u.sesiones.vigente(
                huella(self._politica.secreto_servidor, token), self._reloj.ahora()
            )
            if sesion is None:
                return None
            usuario = u.usuarios.por_id(sesion.usuario_id)
            return None if usuario is None else _vista(usuario)


class CerrarSesion:
    def __init__(self, unidad: Callable[[], UnidadIdentidad], politica: PoliticaAcceso) -> None:
        self._unidad = unidad
        self._politica = politica

    def ejecutar(self, token: str) -> None:
        with self._unidad() as u:
            u.sesiones.eliminar(huella(self._politica.secreto_servidor, token))
            u.confirmar()
