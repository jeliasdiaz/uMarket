import { defineConfig, devices } from "@playwright/test";

// E2E del flujo critico con API y web reales. La base `umarket_e2e` se prepara
// antes con `python scripts/preparar_e2e.py` (backend). LLM_PROVIDER no se usa:
// la busqueda corre con el interprete por palabras (el default del producto).
const PYTHON = process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";
const BD_E2E = process.env.DATABASE_URL_E2E ?? "postgresql+psycopg://umarket:umarket@localhost:5433/umarket_e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    locale: "es-CO",
    timezoneId: "America/Bogota",
  },
  // Viewport de celular: el producto se usa en el campus, desde el telefono.
  projects: [{ name: "movil", use: { ...devices["Pixel 7"] } }],
  webServer: [
    {
      command: `${PYTHON} -m uvicorn umarket.arranque:app --factory --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/salud",
      reuseExistingServer: !process.env.CI,
      env: {
        ENTORNO: "local",
        DATABASE_URL: BD_E2E,
        CODIGO_ACCESO_FIJO: "123456",
        BUSQUEDA_INTERPRETE: "palabras",
        ORIGENES_PERMITIDOS: '["http://localhost:3000"]',
      },
    },
    {
      command: "npx next start -p 3000",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      env: { UMARKET_API_URL: "http://localhost:8000" },
    },
  ],
});
