# Eval de busqueda: palabras

- Fecha: 2026-10-27T15:41:59+00:00 · git: sin-commit · n = 1 · reglas: consulta-v2
- Dataset: SINTETICO (semilla del equipo); se reemplaza con consultas reales de la Fase 0

| Grupo | corridas | acierto@5 | filtros ok | inventados (final / crudo) | respaldo | p50 s | p95 s | costo USD |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| global | 30 | 73% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |
| categoria:adversarial | 3 | 67% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |
| categoria:ambiguo | 1 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | 0 |
| categoria:edge | 4 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |
| categoria:happy | 5 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.002 | 0 |
| categoria:incompleto | 2 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.0 | 0 |
| categoria:intencion | 12 | 42% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |
| categoria:multi | 3 | 100% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |
| conjunto:dev | 18 | 67% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |
| conjunto:test | 12 | 83% | 100% | 0 / 0 | 0% | 0.0 | 0.001 | 0 |

## Fallos

| caso | corrida | acierto@5 | filtros | inventados | top 5 |
| --- | --: | --- | --- | --- | --- |
| intencion-2 | 1 | NO | ok | - | empanadas-dona-rosa/empanada-de-carne |
| intencion-3 | 1 | NO | ok | - |  |
| intencion-4 | 1 | NO | ok | - |  |
| intencion-5 | 1 | NO | ok | - |  |
| intencion-6 | 1 | NO | ok | - |  |
| adversarial-1 | 1 | NO | ok | - |  |
| test-4 | 1 | NO | ok | - |  |
| test-5 | 1 | NO | ok | - |  |
