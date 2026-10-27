"""Prompts congelados (de QuickDev, ADR-0011).

Responsabilidad: servir el texto de sistema de un componente y una version. Los
textos viven en `prompts/<componente>/<version>.md`, no en el codigo, para que un
cambio de prompt se revise como lo que es: un cambio de comportamiento.

Cada archivo declara en su front matter el `sha256` de su texto y el registro lo
comprueba al cargar. Un editor que quite un salto de linea no puede cambiar un
prompt medido sin que se note. Si el cambio es intencionado, es una version
nueva: otro archivo, y se mide. `scripts/sellar_prompt.py` calcula el sha256.
"""

import hashlib
from pathlib import Path

CAMPOS_OBLIGATORIOS = (
    "version",
    "componente",
    "estado",
    "schema_version",
    "rules_version",
    "sha256",
)


class PromptIntegrityError(ValueError):
    """El texto de un prompt no coincide con su sha256, o le falta front matter."""


def leer_prompt(archivo: Path) -> tuple[dict[str, str], str]:
    """Separa el front matter del cuerpo. Normaliza `\\r\\n` (checkouts de Windows)."""
    texto = archivo.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if not texto.startswith("---\n"):
        raise PromptIntegrityError(f"{archivo.name}: falta el front matter inicial '---'.")
    fin = texto.find("\n---", 4)
    if fin == -1:
        raise PromptIntegrityError(f"{archivo.name}: el front matter no se cierra con '---'.")
    meta: dict[str, str] = {}
    for linea in texto[4:fin].splitlines():
        clave, sep, valor = linea.partition(":")
        if sep:
            meta[clave.strip()] = valor.strip()
    return meta, texto[fin + len("\n---") :]


def sha256_de(cuerpo: str) -> str:
    return hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()


class RegistroPrompts:
    def __init__(self, directorio: Path) -> None:
        self.directorio = Path(directorio)
        self._cuerpos: dict[tuple[str, str], str] = {}
        self._meta: dict[tuple[str, str], dict[str, str]] = {}
        for archivo in sorted(self.directorio.glob("*/*.md")):
            meta, cuerpo = leer_prompt(archivo)
            faltan = [c for c in CAMPOS_OBLIGATORIOS if not meta.get(c)]
            if faltan:
                raise PromptIntegrityError(f"{archivo}: faltan campos en el front matter: {faltan}")
            real = sha256_de(cuerpo)
            if meta["sha256"] != real:
                raise PromptIntegrityError(
                    f"{archivo}: el texto no coincide con su sha256 (declarado {meta['sha256']}, "
                    f"real {real}). Si el cambio es intencionado, es una version nueva."
                )
            clave = (meta["componente"], meta["version"])
            self._cuerpos[clave] = cuerpo
            self._meta[clave] = meta

    def versiones(self, componente: str) -> tuple[str, ...]:
        return tuple(v for (c, v) in self._cuerpos if c == componente)

    def texto(self, componente: str, version: str) -> str:
        self._comprobar(componente, version)
        return self._cuerpos[(componente, version)]

    def metadatos(self, componente: str, version: str) -> dict[str, str]:
        self._comprobar(componente, version)
        return dict(self._meta[(componente, version)])

    def _comprobar(self, componente: str, version: str) -> None:
        if (componente, version) not in self._cuerpos:
            raise KeyError(
                f"No existe el prompt {componente}/{version}. "
                f"Disponibles: {sorted(self.versiones(componente))}"
            )
