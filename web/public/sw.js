// Service worker de uMarket: muestra los avisos push y abre el pedido al tocarlos.
// Los avisos los manda el worker del backend (CanalWebPush) con VAPID.

self.addEventListener("push", (evento) => {
  if (!evento.data) return;
  const aviso = evento.data.json();
  evento.waitUntil(
    self.registration.showNotification(aviso.titulo, {
      body: aviso.cuerpo,
      icon: "/icono.svg",
      data: { url: aviso.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  evento.waitUntil(self.clients.openWindow(evento.notification.data.url));
});
