import { type Browser, expect, type Page, test } from "@playwright/test";

/**
 * El flujo critico de punta a punta (puerta de la Fase 1, PLAN-Y-DECISIONES §7):
 * buscar en lenguaje natural -> agregar -> entrar -> pedir -> la vendedora aprueba,
 * llega y entrega -> el comprador califica.
 */

const CODIGO = "123456";

async function entrar(page: Page, correo: string, nombre?: string) {
  await page.getByLabel("Tu correo institucional").fill(correo);
  await page.getByRole("button", { name: "Enviarme un código" }).click();
  await page.getByLabel("Código").fill(CODIGO);
  if (nombre) {
    await page.getByLabel(/Tu nombre/).fill(nombre);
    await page.getByLabel(/Autorizo el tratamiento/).check();
  }
  await page.getByRole("button", { name: "Entrar" }).click();
}

async function nuevaPagina(browser: Browser): Promise<Page> {
  const contexto = await browser.newContext();
  return contexto.newPage();
}

test("comprador y vendedora completan un pedido de punta a punta", async ({ page, browser }) => {
  const comprador = `e2e-${Date.now()}@demo.edu.co`;

  // 1. Buscar como se le diria a un amigo.
  await page.goto("/");
  await page.getByLabel("¿Qué se te antoja?").fill("2 empanadas de pollo pa las 12");
  await page.getByRole("button", { name: "Buscar" }).click();
  await expect(page.getByLabel("Filtros entendidos")).toContainText("12:00");
  await expect(page.getByRole("link", { name: "Empanadas Doña Rosa" })).toBeVisible();

  // 2. Agregar con la cantidad sugerida por la busqueda.
  await page.getByRole("button", { name: /Agregar 2 Empanada de pollo/ }).click();
  await expect(page.getByText("Agregaste 2 × Empanada de pollo.")).toBeVisible();
  await page.getByRole("link", { name: "Ver carrito y elegir cómo recibirlo" }).click();
  await expect(page.getByRole("heading", { name: /Tu pedido a Empanadas Doña Rosa/ })).toBeVisible();

  // 3. Entrar con el correo institucional (primera vez: nombre y consentimiento).
  await page.getByRole("link", { name: /Entra con tu correo institucional/ }).click();
  await entrar(page, comprador, "Ana E2E");
  await expect(page).toHaveURL(/\/carrito/);

  // 4. Confirmar: el total lo pone el servidor.
  await page.getByRole("button", { name: "Confirmar pedido" }).click();
  await expect(page).toHaveURL(/\/pedido\//);
  await expect(page.getByText("Esperando al vendedor")).toBeVisible();
  await expect(page.getByText("$6.000").first()).toBeVisible();
  const urlPedido = page.url();

  // 5. La vendedora lo ve en su bandeja, lo aprueba, llega y entrega.
  const vendedora = await nuevaPagina(browser);
  await vendedora.goto("/entrar?volver=/vendedor");
  await entrar(vendedora, "empanadas-dona-rosa@demo.edu.co");
  await expect(vendedora).toHaveURL(/\/vendedor$/);
  await expect(vendedora.getByText("Para Ana E2E")).toBeVisible();
  await vendedora.getByRole("button", { name: "Aprobar" }).click();
  await vendedora.getByRole("button", { name: "Llegue" }).click();
  await vendedora.getByRole("button", { name: "Entregado" }).click();
  await expect(vendedora.getByText("No tienes pedidos por atender")).toBeVisible();

  // 6. El comprador ve el estado y califica (solo quien recibio puede hacerlo).
  await page.goto(urlPedido);
  await expect(page.getByText("¡Listo! Tu calificación ayuda")).toBeVisible();
  await page.getByRole("button", { name: "4 estrellas" }).click();
  await page.getByLabel("Comentario (opcional)").fill("Llegaron calienticas");
  await page.getByRole("button", { name: "Calificar" }).click();
  await expect(page.getByRole("button", { name: "Calificar" })).toBeHidden();
});

test("la busqueda pregunta el punto cuando es ambiguo", async ({ page }) => {
  await page.goto("/buscar?q=algo%20en%20el%2019");
  await expect(page.getByText("¿En cuál punto?")).toBeVisible();
  await page.getByRole("button", { name: "Bloque 19 - entrada" }).click();
  await expect(page.getByLabel("Filtros entendidos")).toContainText("Bloque 19 - entrada");
});

test("la pagina publica de la tienda trae metadatos para compartir en WhatsApp", async ({ page }) => {
  await page.goto("/t/dulces-de-caro");
  await expect(page.getByRole("heading", { name: "Dulces de Caro" })).toBeVisible();
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", /Dulces de Caro/);
});
