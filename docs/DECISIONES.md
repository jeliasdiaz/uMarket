# Decisiones de uMarket

Un solo archivo de decisiones, no un ADR por archivo (D-16). Cada entrada: contexto, decisión,
consecuencias y cuándo revisarla. Si cambia algo medido, enlaza la corrida que lo mide.

Las D-01 a D-18 vienen de [`PLAN-Y-DECISIONES.md`](../PLAN-Y-DECISIONES.md) (27 oct 2026) y ahí
está su justificación completa. Desde la D-19 son decisiones tomadas al implementar.

---

## Heredadas del plan (resumen)

| # | Decisión |
| --- | --- |
| D-01 | Web responsive (PWA), sin API de WhatsApp; el link de la tienda se comparte en los grupos. |
| D-02 | El pedido se arma con carrito (clics); sin chat de tienda. |
| D-03 | Sin agente de pedidos en el MVP; "convertir mensaje en pedido" queda en backlog. |
| D-04 | La búsqueda por intención es la puerta de entrada y el único componente de IA. |
| D-05 | La búsqueda tiene baseline sin IA; Gemini entra solo si supera el umbral. |
| D-06 | El modelo solo interpreta; resultados, stock, precios y orden los pone el código. |
| D-07 | Las búsquedas sin resultados se registran como señal de demanda. |
| D-08 | El vendedor aprueba o rechaza; editar pedidos queda fuera. |
| D-09 | Crear tienda desde texto primero; desde foto después, en dos pasos. |
| D-10 | Resumen de reseñas solo con 20 reseñas o más por tienda. |
| D-11 | Recordatorios, cancelación, ranking, % cumplido y reputación no son IA. |
| D-12 | Gemini detrás de `LlmPort`, intercambiable; tier pagado antes del primer dato real. |
| D-13 | FastAPI + Next.js + PostgreSQL en Neon; monolito modular hexagonal. |
| D-14 | El stock lo garantiza la base de datos (reserva atómica), no una regla. |
| D-15 | Acceso con código al correo institucional, sin contraseñas. |
| D-16 | Un solo archivo de decisiones (este). |
| D-17 | El cobro del plan fundador es manual, fuera del software. |
| D-18 | Un campus en el lanzamiento, datos listos para varios (`campus_id`). |

---

## Tomadas al implementar

### D-19 · Los tests de aplicación corren contra Postgres real, no contra repositorios en memoria
- **Fecha:** 2026-10-27 · **Cambia:** PLAN-TECNICO §12.1 ("casos de uso con adaptadores en memoria").
- **Contexto:** cada módulo necesitaría un repositorio en memoria además del SQL; con Postgres
  local en Docker y en CI la suite completa tarda ~40 s.
- **Decisión:** los casos de uso se prueban armados por la raíz de composición real
  (`tests/apoyo.py`) contra Postgres. Hay dobles solo para puertos externos: LLM (`FakeLlm`),
  reloj (`RelojFijo`), correo y push. La suite de contrato del puerto LLM corre sobre cada adaptador.
- **Consecuencia:** los tests detectan errores de SQL y de migración que un doble en memoria no ve
  (así apareció el bug de D-21b). Sin Docker, los tests de integración se *saltan* con motivo
  visible y la suite de dominio sigue sirviendo.
- **Revisar si:** la suite pasa de ~2 minutos.

### D-20 · `consulta-v2`: un orden pedido cuenta como consulta utilizable
- **Fecha:** 2026-10-27 · **Medición:** `backend/evals/resultados/2026-10-27-busqueda-intencion-v1-consulta-v2-replay/`.
- **Contexto:** en el primer eval con Gemini, ante "lo mas barato que haya" el modelo respondió
  bien (`orden: precio`, sin ítems), pero `consulta-v1` lo consideró inutilizable y lo mandó al
  respaldo, que no entiende "barato": cero resultados. Falló la validación, no el modelo.
- **Decisión:** nuevo conjunto `consulta-v2` (con `ConsultaUtilizableConOrden`); `consulta-v1` se
  conserva intacto porque es lo que se midió. `REGLAS_CONSULTA` por defecto pasa a `consulta-v2`.
- **Evidencia:** replay de las mismas respuestas grabadas: acierto@5 global 93 % → 97 %;
  intención 83 % → 92 %. Sin gastar llamadas.

### D-21 · Corrección del baseline antes de medir Gemini
- **Fecha:** 2026-10-27.
- **a) Palabras de cantidad.** "media docena de buñuelos" metía "media docena" como términos de
  búsqueda aunque el parser ya las leía como cantidad 6. Se corrigió *antes* de medir el modelo
  (no es ajustar el baseline a favor de nadie). Baseline: 70 % → 73 % global.
- **b) Dos relojes.** `codigos_acceso.creado_en` lo ponía Postgres (`now()`) y el límite de
  códigos comparaba con el `Reloj` de la aplicación: el límite nunca se disparaba. Ahora toda hora
  de negocio la pone la aplicación. Lo detectó un test de integración (D-19).

### D-22 · Primer resultado: Gemini todavía NO entra a la búsqueda
- **Fecha:** 2026-10-27 · **Mediciones:** `backend/evals/resultados/2026-10-27-*`.
- **Resultado** (`python -m evals comparar`, umbral de PLAN-Y-DECISIONES §4.3):

  | | baseline (palabras) | Gemini 3.5 Flash-Lite, prompt v1 |
  | --- | --: | --: |
  | acierto@5 global | 73 % | 97 % (consulta-v2) |
  | acierto@5 intención | 42 % | 92 % |
  | acierto@5 conjunto de prueba | 83 % | 92 % (**+8 pp; el umbral pide +15**) |
  | filtros inventados (final / crudo) | 0 / 0 | 0 / 0 |
  | p95 de interpretación | ~0 s | **23 s** (el umbral pide ≤ 2 s) |

- **Decisión:** `BUSQUEDA_INTERPRETE=palabras` sigue siendo el valor por defecto. El modelo
  está implementado, verificado y listo para `intencion` o `ab`.
- **Hallazgos para la siguiente hipótesis (Fase 3):**
  1. **Latencia:** con la clave actual, la misma llamada mínima tarda entre 0,9 y 26 s. Con
     razonamiento sin límite, "hola" tardó 20 s; con `MINIMAL`, 2 s. Hay que medir con el tier
     pagado antes de concluir nada sobre el modelo.
  2. **Prompt v2:** ante "algo calientico pa desayunar" el modelo usó la categoría `otros` como
     filtro y vació los resultados. Hipótesis: "no uses `otros` como filtro".
  3. **El dataset es sintético** (30 consultas escritas por el equipo, n = 1). Se reemplaza con
     consultas reales de la Fase 0 antes de decidir en serio.
- **Revisar:** con dataset real y tier pagado.

### D-23 · npm en lugar de pnpm
- **Contexto:** pnpm no venía instalado y habría que instalarlo de forma global. npm viene con
  Node 24 y `package-lock.json` da la misma reproducibilidad. Todas las versiones quedan exactas.

### D-24 · Dinero como entero COP con sufijo `_cop`, sin clase `Dinero`
- **Contexto:** el plan nombraba un objeto de valor `Dinero`. Con una sola moneda y sin centavos,
  un `int` con nombre explícito (`precio_cop`, `total_cop`) es igual de claro y no obliga a
  mapear en cada borde (SQL, JSON, contrato del modelo). Se revisa si aparece otra moneda.

### D-25 · Identificadores legibles para campus, puntos y franjas
- `campus-demo`, `b19-entrada`, `f-1200` en lugar de UUID: viajan al modelo como contexto, y un
  id legible cuesta menos tokens y se confunde menos. Tiendas, productos y pedidos usan UUID.

### D-26 · Una sola ruta para las acciones del pedido: `POST /v1/pedidos/{id}/{accion}`
- La acción es un enum validado y la tabla `TRANSICIONES` decide quién puede qué. Una acción nueva
  no necesita endpoint nuevo (abierto/cerrado). Las calificaciones van por `POST /v1/calificaciones`
  para no chocar con esa ruta.

### D-27 · La reputación entrega la clave de orden al catálogo
- El catálogo ordena tiendas por `reputacion.orden`, que calcula la `PoliticaRanking` vigente
  (`ranking-v1`: mínimo 5 reseñas). El catálogo no conoce la fórmula; cambiarla es una clase nueva.

### D-28 · Métricas recalculadas, no incrementadas; eventos por outbox
- Los manejadores del worker recalculan las métricas desde las tablas de origen: el outbox entrega
  "al menos una vez" y recalcular es idempotente. Un aviso push repetido se acepta.

### D-29 · Modelo por defecto `gemini-3.5-flash-lite`, razonamiento mínimo, precio sin verificar
- Era el Flash-Lite estable más reciente que listaba la API el 2026-10-27. La tabla de precios
  (`ia/precios.py`) **no tiene su precio verificado**, así que el costo sale "sin precio" (`None`)
  en vez de cero. **Pendiente:** agregar el precio desde la página oficial.
