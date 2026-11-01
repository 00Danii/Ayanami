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




def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def launch_vpn_guard(iface: str):
    """Inicia o reutiliza VPN Guard administrado por systemd."""
    service = "ayanami-vpn-guard.service"

    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", service],
        check=False,
    )
    if result.returncode == 0:
        status = "ya en ejecución"
    else:
        result = subprocess.run(
            ["systemctl", "start", service],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None, (
                "No se pudo iniciar VPN Guard: "
                + result.stderr.strip()
            )
        status = "iniciado"

    result = subprocess.run(
        ["systemctl", "show", service, "--property=MainPID", "--value"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        pid = int(result.stdout.strip())
    except ValueError:
        return None, "No se pudo obtener el PID del servicio"
    if pid <= 0:
        return None, "VPN Guard no tiene un proceso activo"
    return pid, status


class VpnGuardTab(Vertical):
    """Pestaña del Firewall: detección de VPN con ndpiReader y bloqueo por MAC."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._proc = None
        self._worker = None
        self._tail_running = False
        self._tail_position = 0
        self._pid = None
        self._running = False
        self._blocked = {}  # mac -> {"ip":..., "since":...}
        self._apply = False
        self._log_path = REPO_ROOT / "vpn_guard.log"
        self._pid_path = REPO_ROOT / "vpn_guard.pid"

    def compose(self) -> ComposeResult:
        with Horizontal(classes="vpn-title-row"):
            yield Label("VPN Guard (ndpiReader) DETENIDO", id="vpn-status", classes="vpn-status")
            yield ClickableLabel("[Iniciar]", id="vpn-start", classes="vpn-action vpn-start", markup=False)
            yield ClickableLabel("[Detener]", id="vpn-stop", classes="vpn-action vpn-stop", markup=False)

        yield RichLog(id="vpn-log", markup=True, highlight=True, wrap=True)

    def on_mount(self):
        self.styles.height = "1fr"
        try:
            self.query_one("#vpn-stop", ClickableLabel).display = False
        except Exception:
            pass
        try:
            self.query_one("#vpn-status", Label).update("VPN Guard (ndpiReader) DETENIDO")
        except Exception:
            pass
        try:
            status = self.query_one("#vpn-status", Label)
            status.styles.margin = (0, 0, 0, 0)
            status.styles.height = 1
            status.display = True
        except Exception:
            pass
        self._reattach_if_running()
        self.set_interval(2.0, self._check_proc)
        if not VPN_GUARD_SCRIPT.exists():
            self._log(f"[red]No se encontró {VPN_GUARD_SCRIPT}[/]")

    def _log(self, text: str):
        try:
            self.query_one("#vpn-log", RichLog).write(text)
        except Exception:
            pass

    def _set_status(self, text: str):
        try:
            self.query_one("#vpn-status", Label).update(f"VPN Guard (ndpiReader) {text}")
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

    def _reattach_if_running(self):
        result = subprocess.run(
            [
                "systemctl", "show",
                "ayanami-vpn-guard.service",
                "--property=MainPID", "--value",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            pid = int(result.stdout.strip())
        except ValueError:
            return
        if pid <= 0:
            return

        self._pid = pid
        self._running = True
        self._proc = None
        try:
            self.query_one(
                "#vpn-start", ClickableLabel
            ).display = False
            lbl = self.query_one("#vpn-stop", ClickableLabel)
            lbl.markup = False
            lbl.update(f"[Detener {pid}]")
            lbl.display = True
        except Exception:
            pass
        self._set_status("INICIADO")
        self._log(
            f"[cyan]VPN Guard activo mediante systemd "
            f"(PID {pid})[/]"
        )
        if not self._tail_running:
            self._tail_running = True
            self._worker = self.run_worker(
                self._tail_log,
                name="vpn-guard-tail",
                group="vpn",
                thread=True,
            )

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def start_guard(self):
        if self._proc is not None and self._proc.poll() is None:
            self.notify("El VPN Guard ya está en ejecución", severity="warning")
            return

        iface = getattr(self.app, "selected_interface", None)
        if not iface:
            self.notify("Selecciona una interfaz LAN primero", severity="error")
            return

        self._set_status("INICIANDO")

        pid, msg = launch_vpn_guard(str(iface))
        if pid is None:
            self._log(f"[red]{msg}[/]")
            self._set_status("error")
            return

        self._pid = pid
        self._running = True
        self._tail_position = 0
        try:
            self._pid_path.write_text(str(pid))
        except Exception:
            pass

        self.query_one("#vpn-start", ClickableLabel).display = False
        self.query_one("#vpn-stop", ClickableLabel).display = True
        self._set_status("INICIADO")
        self._log(f"[#565f89]VPN Guard {msg} (PID {pid}). Log: {REPO_ROOT / 'vpn_guard.log'}[/]")
        self._tail_running = True
        self._worker = self.run_worker(self._tail_log, name="vpn-guard-tail", group="vpn", thread=True)

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

    def _tail_log(self):
        path = self._log_path
        try:
            with open(path, "r") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                if self._tail_position == 0:
                    start = max(0, size - 4096)
                else:
                    start = min(self._tail_position, size)
                handle.seek(start)
                while True:
                    pos = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    if not self._running:
                        return
                    self.app.call_from_thread(self._handle_line, line.rstrip("\n"))
                    self._tail_position = handle.tell()
                while self._running:
                    pos = handle.tell()
                    line = handle.readline()
                    if line:
                        self.app.call_from_thread(self._handle_line, line.rstrip("\n"))
                        self._tail_position = handle.tell()
                    else:
                        handle.seek(pos)
                        time.sleep(0.5)
                    proc = self._proc
                    if proc is not None and proc.poll() is not None:
                        self.app.call_from_thread(self._check_proc)
                        return
        except Exception as e:
            self.app.call_from_thread(self._log, f"[red]Error leyendo log: {e}[/]")
        finally:
            self._tail_running = False

    def _check_proc(self):
        if self._proc is None and self._running:
            result = subprocess.run(
                [
                    "systemctl", "is-active", "--quiet",
                    "ayanami-vpn-guard.service",
                ],
                check=False,
            )
            if result.returncode != 0:
                self._running = False
                self._pid = None
                self._set_status("DETENIDO")
                try:
                    self.query_one(
                        "#vpn-start", ClickableLabel
                    ).display = True
                    lbl = self.query_one("#vpn-stop", ClickableLabel)
                    lbl.markup = False
                    lbl.update("[Detener]")
                    lbl.display = False
                except Exception:
                    pass
                self._log(
                    "[yellow]VPN Guard no está activo[/]"
                )
                return
            pid_result = subprocess.run(
                [
                    "systemctl", "show",
                    "ayanami-vpn-guard.service",
                    "--property=MainPID", "--value",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            try:
                pid = int(pid_result.stdout.strip())
                if pid > 0:
                    self._pid = pid
                    try:
                        self.query_one("#vpn-start", ClickableLabel).display = False
                        lbl = self.query_one("#vpn-stop", ClickableLabel)
                        lbl.markup = False
                        lbl.update(f"[Detener {pid}]")
                        lbl.display = True
                    except Exception:
                        pass
                    self._set_status("INICIADO")
            except ValueError:
                pass

        proc = self._proc
        if proc is not None and proc.poll() is not None:
            self._proc = None
            try:
                self.query_one("#vpn-start", ClickableLabel).display = True
                self.query_one("#vpn-stop", ClickableLabel).display = False
            except Exception:
                pass
            self._set_status("DETENIDO")
            self._log(f"[#565f89]Proceso finalizado (rc={proc.returncode})[/]")

    def _on_finished(self, rc):
        self._proc = None
        self._worker = None
        self.query_one("#vpn-start", ClickableLabel).display = True
        self.query_one("#vpn-stop", ClickableLabel).display = False
        self._set_status("DETENIDO")
        self._log(f"[#565f89]Proceso finalizado (rc={rc})[/]")

    def stop_guard(self):
        """Detiene VPN Guard mediante systemd."""
        result = subprocess.run(
            ["systemctl", "stop", "ayanami-vpn-guard.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self._log(
                f"[red]Error al detener VPN Guard: "
                f"{result.stderr.strip()}[/]"
            )
            self.notify(
                "No se pudo detener VPN Guard",
                severity="error",
            )
            return

        self._running = False
        if self._worker is not None:
            try:
                self._worker.cancel()
            except Exception:
                pass
        self._worker = None
        self._tail_running = False
        self._tail_position = 0
        self._proc = None
        self._pid = None
        try:
            self._pid_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            self.query_one(
                "#vpn-start", ClickableLabel
            ).display = True
            lbl = self.query_one("#vpn-stop", ClickableLabel)
            lbl.markup = False
            lbl.update("[Detener]")
            lbl.display = False
        except Exception:
            pass
        self._set_status("DETENIDO")
        self._log("[green]VPN Guard detenido correctamente[/]")
