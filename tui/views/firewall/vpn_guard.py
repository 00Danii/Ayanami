from pathlib import Path
import os
import re
import signal
import subprocess
import sys
import time

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import (
    Label,
    Button,
    Switch,
    Input,
    Select,
    RichLog,
)
from widgets.clickable_label import ClickableLabel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
VPN_GUARD_SCRIPT = REPO_ROOT / "tui" / "vpn_guard.py"

MAC_RE = re.compile(r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})")


class VpnGuardTab(Vertical):
    """Pestaña del Firewall: detección de VPN con ndpiReader y bloqueo por MAC."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._proc = None
        self._worker = None
        self._blocked = {}  # mac -> {"ip":..., "since":...}
        self._apply = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="fw-card"):
            with Horizontal(classes="vpn-title-row"):
                yield Label("VPN Guard (ndpiReader)", classes="fw-card-title")
                with Horizontal(classes="vpn-title-actions"):
                    yield ClickableLabel("[Iniciar]", id="vpn-start", classes="vpn-action vpn-start", markup=False)
                    yield ClickableLabel("[Detener]", id="vpn-stop", classes="vpn-action vpn-stop", markup=False)

            yield Label(
                "Detecta conexiones VPN en la red y bloquea el dispositivo por MAC. "
                "Requiere ndpiReader compilado y ejecución como root.",
                classes="fw-card-desc",
            )

            yield Label("Estado: detenido", id="vpn-status")

        yield RichLog(id="vpn-log", markup=True, highlight=True)

    def on_mount(self):
        self.styles.height = "1fr"
        try:
            self.query_one("#vpn-stop", ClickableLabel).display = False
        except Exception:
            pass
        if not VPN_GUARD_SCRIPT.exists():
            self._log(f"[red]No se encontró {VPN_GUARD_SCRIPT}[/]")

    def _log(self, text: str):
        try:
            self.query_one("#vpn-log", RichLog).write(text)
        except Exception:
            pass

    def _set_status(self, text: str):
        try:
            self.query_one("#vpn-status", Label).update(f"Estado: {text}")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "vpn-start":
            self.start_guard()
        elif bid == "vpn-stop":
            self.stop_guard()
        elif bid == "vpn-clear-blocked":
            self._blocked.clear()
            self._render_blocked()

    def on_clickable_label_pressed(self, event: ClickableLabel.Pressed):
        bid = event.label.id or ""
        if bid == "vpn-start":
            self.start_guard()
        elif bid == "vpn-stop":
            self.stop_guard()

    def start_guard(self):
        if self._proc is not None and self._proc.poll() is None:
            self.notify("El VPN Guard ya está en ejecución", severity="warning")
            return

        iface = getattr(self.app, "selected_interface", None)
        if not iface:
            self.notify("Selecciona una interfaz LAN primero", severity="error")
            return

        dur = 5
        block_device = True
        self._apply = True

        cmd = [
            sys.executable, str(VPN_GUARD_SCRIPT),
            "--interface", str(iface),
            "--lan-iface", str(iface),
            "--block-duration", str(dur),
            "--block-device",
            "--apply",
        ]

        self._log(f"[#565f89]$ {' '.join(cmd)}[/]")
        self._set_status("iniciando...")

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            self._log(f"[red]Error al lanzar: {e}[/]")
            self._set_status("error")
            return

        self.query_one("#vpn-start", ClickableLabel).display = False
        self.query_one("#vpn-stop", ClickableLabel).display = True
        self._set_status("ejecutando")

        self._worker = self.run_worker(self._read_output, name="vpn-guard", group="vpn", thread=True)

    def _read_output(self):
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                self.app.call_from_thread(self._handle_line, line)
        except Exception as e:
            self.app.call_from_thread(self._log, f"[red]Error leyendo salida: {e}[/]")
        finally:
            rc = proc.poll()
            self.app.call_from_thread(self._on_finished, rc)

    def _handle_line(self, line: str):
        if not line:
            return
        # Colorear según contenido
        low = line.lower()
        if "error" in low:
            self._log(f"[red]{line}[/]")
        elif "vpn detectada" in low:
            self._log(f"[yellow]{line}[/]")
            self._parse_detection(line)
        elif "bloqueo temporal programado" in low:
            self._log(f"[cyan]{line}[/]")
        elif "desbloqueo automático" in low:
            self._log(f"[green]{line}[/]")
            self._parse_unblock(line)
        elif "simulación" in low:
            self._log(f"[#565f89]{line}[/]")
        else:
            self._log(line)

    def _parse_detection(self, line: str):
        m = re.search(r"cliente_ip=(\S+)\s+MAC=(\S+)", line)
        if not m:
            # Intentar solo MAC
            mm = MAC_RE.search(line)
            mac = mm.group(1).lower() if mm else None
            ip = None
        else:
            ip = m.group(1)
            mac = m.group(2).lower()
        if not mac:
            return
        if mac not in self._blocked:
            self._blocked[mac] = {"ip": ip, "since": time.strftime("%H:%M:%S")}
        else:
            if ip:
                self._blocked[mac]["ip"] = ip
        self._render_blocked()

    def _parse_unblock(self, line: str):
        m = MAC_RE.search(line)
        if not m:
            return
        mac = m.group(1).lower()
        self._blocked.pop(mac, None)
        self._render_blocked()

    def _render_blocked(self):
        try:
            container = self.query_one("#vpn-blocked-list", Vertical)
        except Exception:
            return
        container.remove_children()
        if not self._blocked:
            container.mount(Label("Sin dispositivos bloqueados.", classes="vpn-blocked-empty"))
            return
        for mac, info in self._blocked.items():
            ip = info.get("ip") or "?"
            since = info.get("since") or ""
            container.mount(Label(f"{mac}  —  IP: {ip}  —  desde {since}", classes="vpn-blocked-row"))

    def _on_finished(self, rc):
        self._proc = None
        self._worker = None
        self.query_one("#vpn-start", ClickableLabel).display = True
        self.query_one("#vpn-stop", ClickableLabel).display = False
        self._set_status(f"detenido (rc={rc})")
        self._log(f"[#565f89]Proceso finalizado (rc={rc})[/]")

    def stop_guard(self):
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    proc.wait()
            except Exception as e:
                self._log(f"[red]Error al detener: {e}[/]")
        if self._worker is not None:
            try:
                self._worker.cancel()
            except Exception:
                pass
        self._proc = None
        self._worker = None
        self.query_one("#vpn-start", ClickableLabel).display = True
        self.query_one("#vpn-stop", ClickableLabel).display = False
        self._set_status("detenido")
