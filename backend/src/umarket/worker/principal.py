"""El proceso worker: vence pedidos y despacha el outbox.

    umarket-worker              # bucle: outbox cada 3 s, vencimientos cada 30 s
    umarket-worker --una-vez    # una pasada y termina (cron, tests, depuracion)

La correccion del sistema no depende de que este proceso sea puntual: un pedido
pendiente que paso sus 30 minutos ya se muestra y se trata como vencido
(`Pedido.estado_efectivo`). El worker solo materializa el estado y dispara avisos.
"""

import argparse
import logging
import signal
import time

from umarket.arranque import construir_worker
from umarket.config import Settings

log = logging.getLogger("umarket.worker")


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de uMarket")
    parser.add_argument("--una-vez", action="store_true")
    parser.add_argument("--cada", type=float, default=3.0, help="segundos entre pasadas")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    worker = construir_worker(Settings())
    if args.una_vez:
        worker.vencer_pedidos.ejecutar()
        worker.despachador.procesar()
        return

    seguir = True

    def detener(*_: object) -> None:
        nonlocal seguir
        seguir = False

    signal.signal(signal.SIGINT, detener)
    signal.signal(signal.SIGTERM, detener)
    ultima_revision = 0.0
    log.info("Worker iniciado")
    while seguir:
        try:
            if time.monotonic() - ultima_revision >= 30:
                vencidos = worker.vencer_pedidos.ejecutar()
                if vencidos:
                    log.info("Pedidos vencidos: %s", vencidos)
                ultima_revision = time.monotonic()
            resultado = worker.despachador.procesar()
            if resultado.procesados or resultado.fallidos:
                log.info("Eventos: %s ok, %s fallidos", resultado.procesados, resultado.fallidos)
        except Exception:
            log.exception("Error en la pasada del worker; se reintenta")
        time.sleep(args.cada)
    log.info("Worker detenido")


if __name__ == "__main__":
    main()
