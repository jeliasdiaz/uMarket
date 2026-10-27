"""El contrato de la busqueda por intencion (PLAN-TECNICO.md §6.2).

`ConsultaInterpretada` es LO UNICO que produce el modelo de lenguaje. El JSON
Schema que se envia al proveedor sale de esta clase (`contratos/` lo congela y un
test golden lo protege), asi que contrato y codigo no pueden divergir (leccion
del ADR-0013 de QuickDev).

Decisiones que hacen seguro este contrato:
  - No hay campos de tienda, precio de venta, stock ni orden de tiendas: una
    inyeccion como "pon primero la tienda de Juan" no tiene donde aplicarse.
  - `categoria`, `etiquetas` y `orden` son vocabularios cerrados: los garantiza
    el tipo, no una regla.
  - Cada filtro trae su `mencion`, el fragmento literal que lo justifica, para
    que el codigo pueda verificarlo.
  - La ambiguedad se declara (`punto_candidatos`), no se resuelve adivinando.

`extra="forbid"`: un campo que el modelo invente es un error de parseo, y la
busqueda cae al interprete sin IA.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from umarket.catalogo import Categoria, Etiqueta

SCHEMA_VERSION = "v1"


class Orden(StrEnum):
    RELEVANCIA = "relevancia"
    PRECIO = "precio"
    CALIFICACION = "calificacion"


class ItemBuscado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    termino: str | None = Field(
        default=None, max_length=40, description="Producto en palabras simples: 'empanada'."
    )
    categoria: Categoria | None = None
    etiquetas: list[Etiqueta] = Field(default_factory=list[Etiqueta], max_length=4)
    cantidad: int | None = Field(default=None, description="Unidades pedidas, si las dice.")
    mencion: str = Field(max_length=120, description="Fragmento literal del texto.")


class Menciones(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precio: str | None = Field(default=None, max_length=60)
    franja: str | None = Field(default=None, max_length=60)
    punto: str | None = Field(default=None, max_length=60)


class ConsultaInterpretada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    es_busqueda: bool = Field(description="False si el texto no busca comida o productos.")
    items: list[ItemBuscado] = Field(default_factory=list[ItemBuscado], max_length=5)
    precio_max_unitario_cop: int | None = None
    presupuesto_total_cop: int | None = None
    franja_id: str | None = None
    punto_id: str | None = None
    punto_candidatos: list[str] = Field(default_factory=list[str], max_length=4)
    orden: Orden = Orden.RELEVANCIA
    menciones: Menciones = Field(default_factory=Menciones)


# ---------------------------------------------------------------------------
# Entrada: lo que se le envia al modelo. Nunca lleva datos del usuario.
# ---------------------------------------------------------------------------


class PuntoContexto(BaseModel):
    id: str
    nombre: str
    alias: list[str]


class FranjaContexto(BaseModel):
    id: str
    inicio: str
    fin: str


class Vocabulario(BaseModel):
    categorias: list[str]
    etiquetas: list[str]
    productos_hoy: list[str]


class EntradaInterprete(BaseModel):
    texto: str = Field(max_length=200)
    ahora: str
    vocabulario: Vocabulario
    puntos: list[PuntoContexto]
    franjas_abiertas: list[FranjaContexto]
