# uMarket · web

Next.js 16 (App Router, Cache Components, Partial Prefetching) + Tailwind 4, instalable como PWA.
Ver el [README del repo](../README.md) y [`PLAN-TECNICO.md` §10](../PLAN-TECNICO.md).

- **El frontend muestra; no decide.** Precios, totales, stock y estados vienen del backend. El
  carrito envía solo productos y cantidades (`src/modulos/carrito/carrito.ts`).
- **Tipos generados:** `npm run api:tipos` regenera `src/api/esquema.d.ts` desde
  `backend/contratos/openapi.json`. No se escriben tipos de la API a mano.
- **Mismo sitio:** el navegador llama `/api/*` y `next.config.ts` lo reenvía a FastAPI
  (`UMARKET_API_URL`), así la cookie de sesión es de primera parte.
- **Datos por sesión** en componentes cliente con TanStack Query. **Metadatos públicos** de la
  tienda (Open Graph para WhatsApp) en servidor, con `"use cache"` y `cacheLife("minutes")`.

```bash
npm run dev        # desarrollo
npm run tipos      # tsc (antes: npx next typegen)
npm run lint
npm test           # Vitest
npm run build
npm run e2e        # Playwright (levanta API y web; ver playwright.config.ts)
```
