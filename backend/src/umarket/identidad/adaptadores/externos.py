"""Adaptadores de identidad que no son SQL: correo y generacion de secretos."""

import logging
import secrets

log = logging.getLogger("umarket.correo")


class EnviadorCorreoConsola:
    """Para desarrollo: escribe el codigo en el log en vez de enviarlo.

    Un proveedor real (Resend, SES) es otro adaptador de `EnviadorCorreo`,
    registrado en `arranque.py`. Ningun caso de uso cambia.
    """

    def __init__(self) -> None:
        self.enviados: list[tuple[str, str]] = []

    def enviar_codigo(self, correo: str, codigo: str) -> None:
        self.enviados.append((correo, codigo))
        log.warning("CODIGO DE ACCESO para %s: %s", correo, codigo)


class GeneradorSecretosSeguro:
    def codigo(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def token(self) -> str:
        return secrets.token_urlsafe(32)


class GeneradorSecretosFijo:
    """Solo para tests y E2E: el codigo es conocido. `config.py` lo prohibe en produccion."""

    def __init__(self, codigo: str) -> None:
        self._codigo = codigo

    def codigo(self) -> str:
        return self._codigo

    def token(self) -> str:
        return secrets.token_urlsafe(32)
