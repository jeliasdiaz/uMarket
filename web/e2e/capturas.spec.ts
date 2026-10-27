import { test } from "@playwright/test";

// Solo para revision visual manual: npx playwright test capturas --project=movil
test.skip(!process.env.CAPTURAS, "solo con CAPTURAS=1");

test("capturas de pantallas clave", async ({ page }) => {
  const dir = process.env.CAPTURAS!;
  await page.goto("/");
  await page.getByText("Empanadas Doña Rosa").waitFor();
  await page.screenshot({ path: `${dir}/1-inicio.png`, fullPage: true });
  await page.goto("/buscar?q=algo%20dulce%20por%20menos%20de%205%20mil");
  await page.getByText("Dulces de Caro").first().waitFor();
  await page.screenshot({ path: `${dir}/2-busqueda.png`, fullPage: true });
  await page.goto("/t/empanadas-dona-rosa");
  await page.getByRole("heading", { name: "Empanadas Doña Rosa" }).waitFor();
  await page.getByRole("button", { name: "Agregar Empanada de pollo" }).click();
  await page.screenshot({ path: `${dir}/3-tienda.png`, fullPage: true });
  await page.goto("/carrito");
  await page.getByText("Subtotal").waitFor();
  await page.screenshot({ path: `${dir}/4-carrito.png`, fullPage: true });
});
