"""Prueba rápida de la TUI (headless, sin root).

Uso:   venv/bin/python prueba.py

Arranca la app en modo test, recorre todos los botones de navegación y
comprueba que cada vista se muestre, que las pestañas del Firewall cambien
de panel y que la lista de Apps se cargue diferida y paginada. Dura un par
de segundos.

Nota: el mensaje "sudo: se requiere una contraseña" que puede aparecer
viene del arp-scan del Scanner al no correr como root; es inofensivo
para esta prueba.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tui"))

from textual.widgets import Button, ContentSwitcher

from tui import AyanamiApp, NAV_ORDER
from views.firewall.apps import PAGINADO_FILAS

FW_TABS = [
    ("fw-tab-rules", "fw-panel-rules"),
    ("fw-tab-config", "fw-panel-config"),
    ("fw-tab-apps", "fw-panel-apps"),
]


async def main():
    app = AyanamiApp()

    async with app.run_test(size=(130, 45)) as pilot:
        await pilot.pause(0.5)
        print("OK  la app arranca")

        sidebar = app.query_one("#sidebar-list")
        content = app.query_one("#main-content", ContentSwitcher)

        for nav in NAV_ORDER:
            sidebar.query_one(f"#{nav}", Button).press()
            await pilot.pause()
            assert content.current == nav, f"no navegó a {nav} (actual: {content.current})"
            print(f"OK  navega a {nav}")

        fw_content = app.query_one("#fw-content", ContentSwitcher)
        for tab, panel in FW_TABS:
            app.query_one(f"#{tab}", Button).press()
            await pilot.pause()
            assert fw_content.current == panel, f"no abre {tab} (actual: {fw_content.current})"
            print(f"OK  abre la pestaña {tab}")

        # La lista de Apps se pinta al abrir el Firewall (no al arrancar) y
        # de a un tramo, para que la app no se congele con muchas apps.
        # Hay que volver al Firewall: el bucle de navegación arriba termina
        # en nav-sistema y una vista oculta tiene región 0x0 (el clic no
        # tendría dónde caer).
        sidebar.query_one("#nav-firewall", Button).press()
        await pilot.pause()
        container = app.query_one("#apps-container")
        assert container.children, "la lista de apps quedó vacía"
        assert len(container.children) <= PAGINADO_FILAS, "se pintaron más filas de las que tocan"
        print(f"OK  lista de apps paginada ({len(container.children)} filas)")

        # «Cargar más» es un label clickeable: se prueba con un clic real.
        await pilot.click("#apps-more")
        await pilot.pause()
        assert len(container.children) > PAGINADO_FILAS, "«Cargar más» no agregó filas"
        print("OK  «Cargar más» agrega el siguiente tramo")

    print("\nTODO OK")


asyncio.run(main())