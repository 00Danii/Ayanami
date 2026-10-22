"""Prueba rápida de la TUI (headless, sin root).

Uso:   venv/bin/python prueba.py

Arranca la app en modo test, recorre todos los botones de navegación y
comprueba que cada vista se muestre, que las pestañas del Firewall cambien
de panel y que la lista de Apps se cargue diferida y paginada. También
verifica que los backups incluyan y restauren dnsmasq.conf. Dura un par
de segundos.

Nota: el mensaje "sudo: se requiere una contraseña" que puede aparecer
viene del arp-scan del Scanner al no correr como root; es inofensivo
para esta prueba.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tui"))

from textual.widgets import Button, ContentSwitcher, TextArea

import firewall_config
from tui import AyanamiApp, NAV_ORDER
from views.firewall.apps import PAGINADO_FILAS
from widgets.clickable_label import ClickableLabel
from widgets.dnsmasq_text_area import DnsmasqTextArea

FW_TABS = [
    ("fw-tab-rules", "fw-panel-rules"),
    ("fw-tab-config", "fw-panel-config"),
    ("fw-tab-apps", "fw-panel-apps"),
]


def check_backup_dnsmasq():
    """Comprueba que los backups incluyan y restauren dnsmasq.conf."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dnsmasq = root / "dnsmasq.conf"
        dnsmasq.write_text("# original\ninterface=eno2\n")
        old = {
            name: getattr(firewall_config, name)
            for name in (
                "CONFIG_FILE",
                "BACKUP_DIR",
                "APPS_FILE",
                "WHITELIST_FILE",
                "DNSMASQ_CONF",
            )
        }
        firewall_config.CONFIG_FILE = str(root / "firewall_config.json")
        firewall_config.BACKUP_DIR = str(root / "backups")
        firewall_config.APPS_FILE = str(root / "apps_firewall.json")
        firewall_config.WHITELIST_FILE = str(root / "whitelist.json")
        firewall_config.DNSMASQ_CONF = str(dnsmasq)
        original_run = firewall_config.subprocess.run
        try:
            Path(firewall_config.CONFIG_FILE).write_text(json.dumps({
                "version": 1,
                "whitelist": [],
                "apps": {},
                "gateway": {},
            }))
            Path(firewall_config.APPS_FILE).write_text("{}")
            Path(firewall_config.WHITELIST_FILE).write_text("[]")

            assert firewall_config.validate_config({
                "version": 1, "whitelist": [], "apps": {},
            })[0], "una copia antigua sin dnsmasq ya no es válida"
            assert not firewall_config.validate_config({
                "version": 1,
                "whitelist": [],
                "apps": {},
                "dnsmasq": {"content": "x", "encoding": "ascii"},
            })[0], "se aceptó una codificación no soportada"

            target = firewall_config.save_backup("2026-10-22_120000_000000")
            assert target, "no se pudo crear el backup de prueba"
            bundle = json.loads(Path(target).read_text())
            assert bundle["dnsmasq"]["content"] == "# original\ninterface=eno2\n", (
                "el backup no incluye el contenido de dnsmasq.conf"
            )

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                return Result()

            firewall_config.subprocess.run = fake_run
            ok, warning = firewall_config.restore_dnsmasq(
                bundle["dnsmasq"], target=str(dnsmasq)
            )
            assert ok, warning
            assert calls[0][:3] == ["dnsmasq", "--test", "-C"], (
                "no se valida dnsmasq.conf antes de restaurarlo"
            )
            assert calls[1] == ["systemctl", "restart", "dnsmasq"], (
                "no se reinicia dnsmasq tras restaurar"
            )
            assert dnsmasq.read_text() == bundle["dnsmasq"]["content"], (
                "la restauración no escribió el contenido del backup"
            )
            assert Path(str(dnsmasq) + ".ayanami.bak").exists(), (
                "no se conservó el dnsmasq.conf anterior"
            )
        finally:
            firewall_config.subprocess.run = original_run
            for name, value in old.items():
                setattr(firewall_config, name, value)
    print("OK  backups con dnsmasq.conf y restauración validada")


async def main():
    app = AyanamiApp()

    async with app.run_test(size=(130, 45)) as pilot:
        await pilot.pause(0.5)
        print("OK  la app arranca")

        sidebar = app.query_one("#sidebar-list")
        content = app.query_one("#main-content", ContentSwitcher)

        for nav in NAV_ORDER:
            sidebar.query_one(f"#{nav}", Button).press()
            # Las vistas se importan/montan bajo demanda; Monitor y Sniffer
            # pueden tardar en importar scapy. Esperar al cambio real evita
            # depender de una pausa fija.
            for _ in range(40):
                await pilot.pause(0.1)
                if content.current == nav:
                    break
            assert content.current == nav, f"no navegó a {nav} (actual: {content.current})"
            print(f"OK  navega a {nav}")

        assert app.query_one("#dhcp-editor"), "la vista DHCP no tiene editor de configuración"
        assert not app.query_one("#dhcp-editor").display, "el editor DHCP debería empezar oculto"
        assert app.query_one("#dhcp-config", TextArea), "el editor DHCP no tiene TextArea"
        assert app.query_one("#dhcp-save-config", ClickableLabel), "el editor DHCP no tiene Guardar"
        assert app.query_one("#dhcp-cancel-config", ClickableLabel), "el editor DHCP no tiene Cancelar"
        syntax_probe = DnsmasqTextArea(
            "# comentario\n"
            "interface=eno2\n"
            "dhcp-option=option:router,192.168.1.1\n"
        )
        highlight_styles = {
            name
            for line_highlights in syntax_probe._highlights.values()
            for _start, _end, name in line_highlights
        }
        expected_styles = {
            "comment",
            "keyword",
            "operator",
            "string",
            "number",
            "type",
        }
        assert expected_styles <= highlight_styles, (
            f"el editor DHCP no resalta la sintaxis: {highlight_styles}"
        )
        print("OK  vista DHCP con editor, resaltado y acciones")

        assert app.query_one("#bk-list"), "la vista Respaldos no tiene lista de backups"
        assert app.query_one("#bk-log"), "la vista Respaldos no tiene log de salida"
        assert app.query_one(".bk-bottom-row"), "la lista y el log no están en dos columnas"
        assert app.query_one("#bk-timer-state"), "la vista Respaldos no muestra el timer"
        assert app.query_one("#bk-timer-calendar"), "la vista Respaldos no muestra la programación"
        assert app.query_one("#bk-edit"), "la vista Respaldos no permite editar el timer"
        assert app.query_one("#bk-status"), "la vista Respaldos no permite ver el estado del timer"
        # Las filas se montan después de leer los backups; esperar a que
        # terminen de componer evita mirar una fila a medio armar.
        for _ in range(40):
            await pilot.pause(0.05)
            if app.query(".bk-row-link") or app.query(".bk-empty"):
                break
        if app.query(".bk-row"):
            assert app.query_one(".bk-table-head"), "la lista de backups no tiene encabezado de tabla"
            row = app.query_one(".bk-row")
            assert row.region.width == app.query_one("#bk-list").region.width, (
                "la tabla de backups no ocupa el ancho de la lista"
            )
            links = list(app.query(".bk-row-link"))
            assert len(links) >= 2, "la lista de backups no tiene acciones clicables"
            assert links[0].region.y == links[1].region.y, (
                "Restaurar y Eliminar no están en la misma fila"
            )
        print("OK  vista Respaldos compuesta (tabla + log en dos columnas)")

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


check_backup_dnsmasq()
asyncio.run(main())