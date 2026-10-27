# Eval de busqueda: intencion (prompt v1, replay)

- Fecha: 2026-10-27T15:42:05+00:00 · git: sin-commit · n = 1 · reglas: consulta-v2
- Dataset: SINTETICO (semilla del equipo); se reemplaza con consultas reales de la Fase 0

| Grupo | corridas | acierto@5 | filtros ok | inventados (final / crudo) | respaldo | p50 s | p95 s | costo USD |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| global | 30 | 97% | 100% | 0 / 0 | 3% | 0.0 | 0.001 | None |
| categoria:adversarial | 3 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | None |
| categoria:ambiguo | 1 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | None |
| categoria:edge | 4 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | None |
| categoria:happy | 5 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | None |
| categoria:incompleto | 2 | 100% | 100% | 0 / 0 | 50% | 0.001 | 0.001 | None |
| categoria:intencion | 12 | 92% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | None |
| categoria:multi | 3 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | None |
| conjunto:dev | 18 | 100% | 100% | 0 / 0 | 6% | 0.0 | 0.001 | None |
| conjunto:test | 12 | 92% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | None |

## Fallos

| caso | corrida | acierto@5 | filtros | inventados | top 5 |
| --- | --: | --- | --- | --- | --- |
| test-5 | 1 | NO | ok | - |  |
