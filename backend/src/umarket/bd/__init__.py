"""Plataforma de base de datos: motor, metadatos, unidad de trabajo y outbox.

Como `ia/`, no es un modulo de negocio: es infraestructura que usan los
adaptadores SQL de cada modulo. El dominio y la aplicacion no la importan
(import-linter, reglas 1 y 2).
"""
