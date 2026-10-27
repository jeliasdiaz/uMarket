# Eval de busqueda: intencion (prompt v1, gemini-3.5-flash-lite)

- Fecha: 2026-10-27T15:39:51+00:00 · git: sin-commit · n = 1 · reglas: consulta-v1
- Dataset: SINTETICO (semilla del equipo); se reemplaza con consultas reales de la Fase 0

| Grupo | corridas | acierto@5 | filtros ok | inventados (final / crudo) | respaldo | p50 s | p95 s | costo USD |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| global | 30 | 93% | 100% | 0 / 0 | 7% | 4.095 | 23.061 | None |
| categoria:adversarial | 3 | 100% | 100% | 0 / 0 | 0% | 4.082 | 15.79 | None |
| categoria:ambiguo | 1 | 100% | 100% | 0 / 0 | 0% | 3.667 | 3.667 | None |
| categoria:edge | 4 | 100% | 100% | 0 / 0 | 0% | 2.221 | 3.353 | None |
| categoria:happy | 5 | 100% | 100% | 0 / 0 | 0% | 14.205 | 17.573 | None |
| categoria:incompleto | 2 | 100% | 100% | 0 / 0 | 50% | 7.511 | 14.001 | None |
| categoria:intencion | 12 | 83% | 100% | 0 / 0 | 8% | 15.255 | 23.061 | None |
| categoria:multi | 3 | 100% | 100% | 0 / 0 | 0% | 1.472 | 22.993 | None |
| conjunto:dev | 18 | 94% | 100% | 0 / 0 | 11% | 15.098 | 23.061 | None |
| conjunto:test | 12 | 92% | 100% | 0 / 0 | 0% | 1.404 | 4.108 | None |

## Fallos

| caso | corrida | acierto@5 | filtros | inventados | top 5 |
| --- | --: | --- | --- | --- | --- |
| intencion-6 | 1 | NO | ok | - |  |
| test-5 | 1 | NO | ok | - |  |
