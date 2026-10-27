"""La configuracion, en un solo lugar.

Responsabilidad: leer las variables de entorno (o `backend/.env`) y validarlas al
arrancar. Es el UNICO modulo que lee el entorno: el resto recibe valores.

Lo que NO le corresponde: construir adaptadores. Eso es `arranque.py`.
"""

from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_BACKEND = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_BACKEND / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    entorno: Literal["local", "test", "preview", "produccion"] = "local"

    # --- base de datos -----------------------------------------------------
    # En Neon: la cadena *pooled* (-pooler) para la app y la directa para Alembic.
    database_url: str = "postgresql+psycopg://umarket:umarket@localhost:5433/umarket"
    database_url_directa: str = ""

    # --- LLM ---------------------------------------------------------------
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: str = ""
    llm_replay_path: Path | None = None
    llm_presupuesto_diario_usd: float = 1.0
    llm_cache_dir: Path | None = None

    # --- busqueda ----------------------------------------------------------
    # "palabras" por defecto: Gemini solo entra si supera el umbral en los evals
    # (PLAN-Y-DECISIONES.md §4.3). "ab" reparte por sesion.
    busqueda_interprete: Literal["palabras", "intencion", "ab"] = "palabras"
    busqueda_timeout_s: float = 3.0
    prompt_busqueda: str = "v1"
    # v2: un orden pedido cuenta como consulta utilizable (DECISIONES D-20).
    reglas_consulta: str = "consulta-v2"

    # --- pedidos y reputacion ----------------------------------------------
    minutos_para_aprobar: int = 30
    limite_pedidos_abiertos: int = 2
    max_inasistencias: int = 3
    max_unidades_por_item: int = 20
    reglas_pedido: str = "pedido-v1"
    ranking_version: str = "ranking-v1"
    minimo_resenas_ranking: int = 5

    # --- campus ------------------------------------------------------------
    # El MVP es un campus: quien entra sin sesion (desde un link de WhatsApp) ve este.
    campus_por_defecto: str = "campus-demo"
    zona_horaria_por_defecto: str = "America/Bogota"

    # --- acceso ------------------------------------------------------------
    # HMAC de codigos y tokens. En produccion es obligatorio y largo.
    secreto_servidor: str = "solo-para-desarrollo-cambiar"
    # Codigo conocido para tests y E2E. Prohibido fuera de local/test (ver abajo).
    codigo_acceso_fijo: str = ""
    minutos_codigo_acceso: int = 10
    intentos_codigo_acceso: int = 5
    dias_sesion: int = 30
    cookie_segura: bool = False
    origenes_permitidos: list[str] = ["http://localhost:3000"]
    correo_proveedor: Literal["consola"] = "consola"
    version_terminos: str = "2026-10"

    # --- avisos push -------------------------------------------------------
    vapid_clave_publica: str = ""
    vapid_clave_privada: str = ""
    vapid_contacto: str = "mailto:equipo@umarket.local"

    @field_validator("database_url", "database_url_directa")
    @classmethod
    def _driver_psycopg(cls, valor: str) -> str:
        """Neon entrega `postgresql://...`; SQLAlchemy necesita saber el driver."""
        for prefijo in ("postgresql://", "postgres://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg://" + valor.removeprefix(prefijo)
        return valor

    @model_validator(mode="after")
    def _seguro_fuera_de_local(self) -> "Settings":
        """Un despliegue real no arranca con secretos de juguete ni puertas traseras."""
        if self.entorno in ("preview", "produccion"):
            if self.codigo_acceso_fijo:
                raise ValueError("codigo_acceso_fijo solo se permite en local o test.")
            if len(self.secreto_servidor) < 32 or "desarrollo" in self.secreto_servidor:
                raise ValueError("secreto_servidor debe ser un secreto propio de 32+ caracteres.")
            if not self.cookie_segura:
                raise ValueError("cookie_segura debe ser true fuera de local.")
        return self

    @property
    def url_migraciones(self) -> str:
        """La conexion directa si existe: las migraciones no deben pasar por el pooler."""
        return self.database_url_directa or self.database_url
