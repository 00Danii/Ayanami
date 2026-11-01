from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, RichLog
from widgets.clickable_label import ClickableLabel

import os
import subprocess
from pathlib import Path

from firewall_ops import get_dns_block_file


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INSTALLER = REPO_ROOT / "systemd" / "install_ayanami_services.sh"


class ServicesTab(Vertical):
    """Pestaña para administrar los servicios systemd de AYANAMI."""

    def compose(self):
        with Horizontal(classes="svc-title-row"):
            yield Label("Servicios AYANAMI", classes="fw-card-title")
            with Horizontal(classes="svc-title-actions"):
                yield ClickableLabel("[Instalar]", id="svc-install", classes="svc-action svc-green", markup=False)
                yield ClickableLabel("[Desinstalar]", id="svc-uninstall", classes="svc-action svc-red", markup=False)
                yield ClickableLabel("[Estado]", id="svc-status", classes="svc-action svc-blue", markup=False)

        yield Label(
            "Instala, desinstala o consulta los servicios de arranque "
            "automático (restore y VPN Guard).",
            classes="fw-card-desc",
        )

        with Horizontal(classes="svc-columns"):
            with Vertical(classes="svc-card"):
                with Horizontal(classes="svc-service-row"):
                    yield Label("ayanami-restore.service", classes="fw-card-title")
                    with Horizontal(classes="svc-title-actions"):
                        yield ClickableLabel("[Iniciar]", id="svc-start-restore", classes="svc-action svc-green", markup=False)
                        yield ClickableLabel("[Detener]", id="svc-stop-restore", classes="svc-action svc-red", markup=False)

            with Vertical(classes="svc-card"):
                with Horizontal(classes="svc-service-row"):
                    yield Label("ayanami-vpn-guard.service", classes="fw-card-title")
                    with Horizontal(classes="svc-title-actions"):
                        yield ClickableLabel("[Iniciar]", id="svc-start-vpn", classes="svc-action svc-green", markup=False)
                        yield ClickableLabel("[Detener]", id="svc-stop-vpn", classes="svc-action svc-red", markup=False)

        yield RichLog(id="svc-log", markup=True, highlight=True, wrap=True)

    def on_mount(self):
        self._refresh_status()
        self._log("Listo. Usa los botones para administrar los servicios.")

    def _log(self, text: str):
        try:
            self.query_one("#svc-log", RichLog).write(text)
        except Exception:
            pass

    def _refresh_status(self):
        pairs = [
            ("ayanami-restore.service", "svc-start-restore", "svc-stop-restore"),
            ("ayanami-vpn-guard.service", "svc-start-vpn", "svc-stop-vpn"),
        ]
        for service, start_id, stop_id in pairs:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", "--quiet", service],
                    check=False,
                )
                active = result.returncode == 0
                self.query_one(f"#{start_id}", ClickableLabel).display = not active
                self.query_one(f"#{stop_id}", ClickableLabel).display = active
            except Exception:
                pass

        try:
            installed = Path("/etc/systemd/system/ayanami-restore.service").exists()
            self.query_one("#svc-install", ClickableLabel).display = not installed
            self.query_one("#svc-uninstall", ClickableLabel).display = installed
        except Exception:
            pass

    def _run(self, cmd: list[str], title: str):
        self._log(f"\n[#e0af68]━━━ {title} ━━━[/]")
        self._log(f"[#565f89]$ {' '.join(cmd)}[/]")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            self._log(f"[#f7768e]Error: {exc}[/]")
            self.notify("Error ejecutando comando", severity="error")
            return

        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                self._log(f"[#a9b1d6]{line}[/]")
        if result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                self._log(f"[#f7768e]{line}[/]")
        if result.returncode != 0:
            self._log(f"[#f7768e]Código de salida: {result.returncode}[/]")
            self.notify("Comando finalizado con errores", severity="warning")
        else:
            self._log("[#9ece6a]OK[/]")
            self.notify("Comando finalizado")
        self._refresh_status()

    def on_clickable_label_pressed(self, event: ClickableLabel.Pressed):
        bid = event.label.id or ""
        if bid == "svc-install":
            self._run(["bash", str(INSTALLER)], "Instalar servicios AYANAMI")
        elif bid == "svc-uninstall":
            self._run(["bash", str(INSTALLER), "--uninstall"], "Desinstalar servicios AYANAMI")
        elif bid == "svc-status":
            self._run(["bash", str(INSTALLER), "--status"], "Estado de servicios AYANAMI")
        elif bid == "svc-start-restore":
            self._run(["systemctl", "start", "ayanami-restore.service"], "Iniciar ayanami-restore")
        elif bid == "svc-stop-restore":
            self._run(["systemctl", "stop", "ayanami-restore.service"], "Detener ayanami-restore")
        elif bid == "svc-start-vpn":
            self._run(["systemctl", "start", "ayanami-vpn-guard.service"], "Iniciar ayanami-vpn-guard")
        elif bid == "svc-stop-vpn":
            self._run(["systemctl", "stop", "ayanami-vpn-guard.service"], "Detener ayanami-vpn-guard")
