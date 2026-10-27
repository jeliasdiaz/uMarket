"""Campus, puntos de encuentro y franjas.

Los identificadores de puntos y franjas son textos legibles ("b19-entrada",
"f-1200"), no UUID: viajan al modelo de lenguaje como contexto de la busqueda, y
un identificador legible cuesta menos tokens y se confunde menos.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Campus:
    id: str
    nombre: str
    zona_horaria: str
    dominios_correo: tuple[str, ...]

    @property
    def zona(self) -> ZoneInfo:
        return ZoneInfo(self.zona_horaria)

    def admite_correo(self, correo: str) -> bool:
        dominio = correo.rpartition("@")[2].lower()
        return dominio in {d.lower() for d in self.dominios_correo}


@dataclass(frozen=True)
class PuntoEncuentro:
    """Un lugar publico y predefinido del campus. Nunca un salon de clase."""

    id: str
    campus_id: str
    nombre: str
    descripcion: str = ""
    foto_url: str | None = None
    alias: tuple[str, ...] = ()
    activo: bool = True


@dataclass(frozen=True)
class Franja:
    """Un intervalo del dia en que se hacen entregas (p. ej. 12:00 a 12:30)."""

    id: str
    campus_id: str
    hora_inicio: time
    hora_fin: time

    def __post_init__(self) -> None:
        if self.hora_fin <= self.hora_inicio:
            raise ValueError(f"La franja {self.id} termina antes de empezar.")

    def inicio_en(self, fecha: date, zona: ZoneInfo) -> datetime:
        return datetime.combine(fecha, self.hora_inicio, tzinfo=zona)

    def fin_en(self, fecha: date, zona: ZoneInfo) -> datetime:
        return datetime.combine(fecha, self.hora_fin, tzinfo=zona)

    def ha_pasado(self, fecha: date, ahora: datetime, zona: ZoneInfo) -> bool:
        """Una franja pasa cuando termina: hasta el ultimo minuto se puede pedir para ella."""
        return ahora >= self.fin_en(fecha, zona)

    @property
    def etiqueta(self) -> str:
        return f"{self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"
