# Evals de la búsqueda por intención

Miden **el pipeline desplegado** (`Buscar`, armado por la raíz de composición real) contra el
catálogo fixture (`datos/catalogo_fixture.json`) en un Postgres de evals, con el reloj fijo en las
11:20 del 3 de noviembre de 2026. Es la disciplina de QuickDev: hipótesis escrita antes, baseline
y after, n corridas y resultados versionados que nunca se pisan.

| | Regresiones | Evals |
| --- | --- | --- |
| Qué prueban | Que el **validador** siga detectando lo mismo | Si el **interprete** encuentra lo que la gente busca |
| ¿Llaman al modelo? | No | Sí, o reproducen corridas grabadas (`--replay`) |
| Dónde | `regresiones.py` → `regresiones_esperadas.csv` | `datos/consultas.jsonl` (30 consultas) |
| Comando | `python scripts/gate_regresiones.py` | `python -m evals correr ...` |

## Comandos

```bash
# Baseline sin IA (determinista, n = 1)
python -m evals correr --interprete palabras

# Gemini en vivo (necesita GEMINI_API_KEY; sin cache: medir es muestrear)
python -m evals correr --interprete intencion --n 3 --timeout 30

# Reproducir una corrida sin red ni cuota (solo cambió la validación, p. ej.)
python -m evals correr --interprete intencion --reglas consulta-v2 \
  --replay evals/resultados/2026-10-27-busqueda-intencion-v1-consulta-v1/crudo.json

# La puerta de entrada de Gemini (PLAN-Y-DECISIONES §4.3); sale con 1 si no pasa
python -m evals comparar <dir_baseline> <dir_after>
```

Cada corrida escribe `resultados/<fecha>-busqueda-<interprete>-<reglas>[-replay]/` con
`manifiesto.json` (versiones, modelo, git, resumen), `crudo.json` (para replay),
`resultados.csv` (una fila por corrida) y `resumen.md`.

## Métricas

- **acierto@5**: algún producto relevante entre los 5 primeros resultados.
- **filtros ok**: los filtros esperados coinciden con la consulta final.
- **inventados**: filtros que el dataset dice que no deberían estar. Se cuentan en la consulta
  final y en el **crudo** del modelo: la diferencia separa "falló el prompt" de "lo salvó el
  validador".
- **respaldo**: % de búsquedas en que el modelo falló y respondió el baseline.
- **latencia p50/p95, tokens, costo**. Un replay no tiene latencia real: `comparar` usa la de la
  corrida en vivo que reproduce.

## Estado al 2026-10-27

| | palabras | intención (Gemini 3.5 Flash-Lite, prompt v1) |
| --- | --: | --: |
| acierto@5 global | 73 % | 97 % con `consulta-v2` (93 % con v1) |
| acierto@5 intención | 42 % | 92 % |
| acierto@5 conjunto test | 83 % | 92 % |
| filtros inventados | 0 | 0 |
| p95 interpretación | ~0 s | 23 s |

**Gemini no entra todavía** (D-22): +8 pp en el conjunto de prueba (el umbral pide +15) y p95 de
23 s (pide ≤ 2 s). **El dataset es SINTÉTICO**: se reemplaza con consultas reales de la Fase 0
antes de decidir en serio.

## Agregar una consulta

1. Una línea en `datos/consultas.jsonl` con `relevantes` (claves `tienda/producto` del fixture),
   `filtros` esperados e **hipótesis escrita antes de correr**. `conjunto: test` solo para reportar.
2. Corre el baseline y el after. El replay commiteado no la tiene: medirla requiere la API.
