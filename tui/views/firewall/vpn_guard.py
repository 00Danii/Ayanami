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

        yield RichLog(id="vpn-log", markup=True, highlight=True)

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
        """Si VPN Guard ya está corriendo, reanuda el seguimiento del log."""
        try:
            if not self._pid_path.exists():
                return
            pid = int(self._pid_path.read_text().strip())
        except (ValueError, OSError):
            try:
                self._pid_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

        if not self._pid_alive(pid):
            try:
                self._pid_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

        self._pid = pid
        self._running = True
        self._proc = None
        try:
            self.query_one("#vpn-start", ClickableLabel).display = False
            self.query_one("#vpn-stop", ClickableLabel).display = True
        except Exception:
            pass
        self._set_status("INICIADO")
        self._log(f"[#565f89]VPN Guard ya en ejecución (PID {pid}). Siguiendo log: {self._log_path}[/]")
        self._worker = self.run_worker(self._tail_log, name="vpn-guard-tail", group="vpn", thread=True)

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
        self._set_status("INICIANDO")

        log_path = REPO_ROOT / "vpn_guard.log"
        try:
            log_handle = open(log_path, "a", buffering=1)
            self._proc = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            log_handle.close()
        except Exception as e:
            self._log(f"[red]Error al lanzar: {e}[/]")
            self._set_status("error")
            return

        self._pid = self._proc.pid
        try:
            self._pid_path.write_text(str(self._proc.pid))
        except Exception as e:
            self._log(f"[red]No se pudo guardar PID: {e}[/]")
        self._running = True

        self.query_one("#vpn-start", ClickableLabel).display = False
        self.query_one("#vpn-stop", ClickableLabel).display = True
        self._set_status("INICIADO")
        self._log(f"[#565f89]Proceso desacoplado. Log: {log_path}[/]")
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
                handle.seek(max(0, size - 4096))
                for line in handle:
                    if not self._running:
                        return
                    self.app.call_from_thread(self._handle_line, line.rstrip("\n"))
                while self._running:
                    line = handle.readline()
                    if line:
                        self.app.call_from_thread(self._handle_line, line.rstrip("\n"))
                    else:
                        time.sleep(0.5)
                    proc = self._proc
                    if proc is not None and proc.poll() is not None:
                        self.app.call_from_thread(self._check_proc)
                        return
        except Exception as e:
            self.app.call_from_thread(self._log, f"[red]Error leyendo log: {e}[/]")

    def _check_proc(self):
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
        proc = self._proc
        pid = self._pid if self._pid is not None else (proc.pid if proc is not None else None)
        if pid is not None:
            try:
                os.killpg(pid, signal.SIGINT)
                if proc is not None:
                    try:
                        proc.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        os.killpg(pid, signal.SIGTERM)
                        proc.wait()
                else:
                    # Esperar a que el proceso termine
                    for _ in range(40):
                        try:
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            break
                        time.sleep(0.1)
            except ProcessLookupError:
                pass
            except Exception as e:
                self._log(f"[red]Error al detener: {e}[/]")
        self._running = False
        if self._worker is not None:
            try:
                self._worker.cancel()
            except Exception:
                pass
        self._worker = None
        self._proc = None
        self._pid = None
        try:
            self._pid_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            self.query_one("#vpn-start", ClickableLabel).display = True
            self.query_one("#vpn-stop", ClickableLabel).display = False
        except Exception:
            pass
        self._set_status("DETENIDO")
        self._log("[#565f89]VPN Guard detenido[/]")
