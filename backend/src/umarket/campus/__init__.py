"""API publica del modulo campus: lo unico que otros modulos pueden importar."""

from umarket.campus.aplicacion.consultas import ObtenerCampus, VistaCampus
from umarket.campus.dominio.modelos import Campus, Franja, PuntoEncuentro

__all__ = ["Campus", "Franja", "ObtenerCampus", "PuntoEncuentro", "VistaCampus"]
