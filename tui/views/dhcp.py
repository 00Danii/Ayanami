from rich.markup import escape
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, RichLog, TextArea

from widgets.clickable_label import ClickableLabel
from widgets.confirm_screen import ConfirmScreen

import os
import shutil
import stat
import subprocess
import tempfile


DNSMASQ_CONF = "/etc/dnsmasq.conf"


class DhcpView(Vertical):
    """Estado y configuración del servicio dnsmasq (DHCP y DNS local)."""

    _editing = False
    _saving = False
    _config_encoding = "utf-8"
    _original_text = ""
    _pending_save = None

    def compose(self):
        with Vertical(classes="fw-card"):
            with Horizontal(classes="dhcp-header-row"):
                with Vertical(classes="dhcp-info-col"):
                    yield Label("DHCP / dnsmasq", classes="fw-card-title")
                    yield Label(
                        "Estado del servicio que reparte DHCP y resuelve el DNS local.",
                        classes="fw-card-desc"
                    )
                with Horizontal(classes="dhcp-actions"):
                    yield Button("Estado", id="dhcp-status", variant="primary")
                    yield Button("Editar Config", id="dhcp-show-config")
                    yield Button("Reiniciar Servicio", id="dhcp-restart", variant="warning")

        yield RichLog(id="dhcp-log", markup=True, highlight=True)

        # El editor ocupa el mismo espacio que el log. Solo se muestra al
        # pulsar «Editar Config», para no perder el historial de comandos.
        with Vertical(id="dhcp-editor"):
            with Horizontal(classes="dhcp-edit-actions"):
                yield Label(
                    "",
                    id="dhcp-edit-status",
                    classes="dhcp-edit-status",
                    markup=False,
                )
                with Horizontal(classes="dhcp-edit-links"):
                    yield ClickableLabel(
                        "[Guardar]",
                        id="dhcp-save-config",
                        classes="dhcp-edit-link dhcp-edit-save",
                        markup=False,
                    )
                    yield ClickableLabel(
                        "[Cancelar]",
                        id="dhcp-cancel-config",
                        classes="dhcp-edit-link dhcp-edit-cancel",
                        markup=False,
                    )
            yield TextArea(
                "",
                id="dhcp-config",
                show_line_numbers=True,
                soft_wrap=False,
            )

    def refresh_data(self):
        if self._editing:
            self.app.notify(
                "Guarda o cancela los cambios antes de actualizar la vista.",
                severity="warning",
            )
            return
        self.show_status()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "dhcp-status":
            self.show_status()
        elif bid == "dhcp-show-config":
            self.show_config()
        elif bid == "dhcp-restart":
            self.restart_service()

    def on_clickable_label_pressed(self, event: ClickableLabel.Pressed):
        if self._saving:
            return
        bid = event.label.id
        if bid == "dhcp-save-config":
            self.save_config()
        elif bid == "dhcp-cancel-config":
            self.cancel_config()

    def log(self, text: str):
        self.query_one("#dhcp-log", RichLog).write(text)

    def run(self, cmd: str):
        self.log(f"[#565f89]$ {cmd}[/]")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                self.log(f"[#a9b1d6]{line}[/]")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        return result

    def show_status(self, clear=True):
        if clear:
            self.query_one("#dhcp-log", RichLog).clear()
        self.log("[#7dcfff]◆ Estado del servicio dnsmasq[/]")
        self.run("systemctl status dnsmasq --no-pager")

    def show_config(self):
        self._discard_pending_save()
        try:
            with open(DNSMASQ_CONF, "rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            self.query_one("#dhcp-log", RichLog).clear()
            self.log(f"[#f7768e]✗ No existe {DNSMASQ_CONF}[/]")
            self.app.notify(f"No existe {DNSMASQ_CONF}", severity="error")
            return
        except OSError as exc:
            self.query_one("#dhcp-log", RichLog).clear()
            self.log(f"[#f7768e]✗ No se pudo leer {DNSMASQ_CONF}: {exc}[/]")
            self.app.notify("No se pudo leer la configuración de dnsmasq.", severity="error")
            return

        try:
            content = raw.decode("utf-8")
            self._config_encoding = "utf-8"
            encoding_note = ""
        except UnicodeDecodeError:
            # Preservar el archivo original si no es UTF-8 (p. ej. latin-1).
            content = raw.decode("latin-1")
            self._config_encoding = "latin-1"
            encoding_note = " (codificación latin-1)"

        text_area = self.query_one("#dhcp-config", TextArea)
        text_area.load_text(content)
        # Guardar el texto tal como queda en el editor permite detectar si el
        # usuario realmente cambió algo antes de validar y reiniciar dnsmasq.
        self._original_text = text_area.text
        self.query_one("#dhcp-edit-status", Label).update(
            f"Editando {DNSMASQ_CONF}{encoding_note}. "
            "Se valida con dnsmasq --test y se reinicia el servicio al guardar."
        )
        self._set_editing(True)
        self.query_one("#dhcp-config", TextArea).focus()

    def save_config(self):
        if not self._editing or self._saving:
            return

        text_area = self.query_one("#dhcp-config", TextArea)
        text = text_area.text
        if text == self._original_text:
            self.query_one("#dhcp-edit-status", Label).update(
                "Sin cambios; no se guardó ni reinició nada."
            )
            self.app.notify(
                "No se cambió nada; el servicio dnsmasq no se reinició.",
                severity="information",
            )
            text_area.focus()
            return

        encoding = self._config_encoding
        self._set_saving(True)
        self.query_one("#dhcp-edit-status", Label).update(
            "Validando cambios con dnsmasq --test…"
        )
        self.run_worker(
            lambda: self._do_prepare_save(text, encoding),
            thread=True,
        )

    def cancel_config(self):
        self._discard_pending_save()
        self._set_saving(False)
        self._set_editing(False)
        self.log("[#565f89]Edición cancelada; no se guardó ningún cambio.[/]")

    def _set_editing(self, editing: bool):
        self._editing = editing
        self.query_one("#dhcp-log").display = not editing
        self.query_one("#dhcp-editor").display = editing
        for widget_id in ("dhcp-status", "dhcp-show-config", "dhcp-restart"):
            self.query_one(f"#{widget_id}", Button).disabled = editing
        if not editing:
            self.query_one("#dhcp-edit-status", Label).update("")
            self.query_one("#dhcp-save-config", ClickableLabel).disabled = False
            self.query_one("#dhcp-cancel-config", ClickableLabel).disabled = False
            self.query_one("#dhcp-config", TextArea).read_only = False

    def _set_saving(self, saving: bool):
        self._saving = saving
        self.query_one("#dhcp-save-config", ClickableLabel).disabled = saving
        self.query_one("#dhcp-cancel-config", ClickableLabel).disabled = saving
        self.query_one("#dhcp-config", TextArea).read_only = saving

    def on_unmount(self):
        # Si la app se cierra con una confirmación pendiente, no dejar el
        # temporal validado en /etc.
        self._discard_pending_save()

    def _do_prepare_save(self, text: str, encoding: str):
        try:
            result = self._prepare_config_file(text, encoding)
        except Exception as exc:  # Mantener la UI viva ante errores inesperados.
            result = {
                "ok": False,
                "message": f"Error inesperado al validar: {exc}",
                "tmp_path": None,
                "target": None,
            }
        self.app.call_from_thread(self._after_prepare_save, result)

    def _prepare_config_file(self, text: str, encoding: str):
        """Escribe un temporal y lo valida, sin tocar el archivo real todavía."""
        target = os.path.realpath(DNSMASQ_CONF)
        tmp_path = None
        keep_tmp = False

        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".dnsmasq.conf.ayanami-",
                dir=os.path.dirname(target) or ".",
                text=True,
            )
            with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())

            try:
                original_stat = os.stat(target)
            except FileNotFoundError:
                original_stat = None

            if original_stat is not None:
                os.chmod(tmp_path, stat.S_IMODE(original_stat.st_mode))
                try:
                    os.chown(tmp_path, original_stat.st_uid, original_stat.st_gid)
                except (AttributeError, PermissionError):
                    pass
            else:
                os.chmod(tmp_path, 0o644)

            try:
                test = subprocess.run(
                    ["dnsmasq", "--test", "-C", tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except FileNotFoundError:
                return {
                    "ok": False,
                    "message": "No se encontró el comando dnsmasq.",
                    "tmp_path": None,
                    "target": target,
                }
            except subprocess.TimeoutExpired:
                return {
                    "ok": False,
                    "message": "dnsmasq --test agotó el tiempo de espera.",
                    "tmp_path": None,
                    "target": target,
                }

            test_output = (test.stdout + test.stderr).strip()
            if test.returncode != 0:
                return {
                    "ok": False,
                    "message": test_output or (
                        f"dnsmasq --test salió con código {test.returncode}."
                    ),
                    "tmp_path": None,
                    "target": target,
                }

            keep_tmp = True
            return {
                "ok": True,
                "message": test_output or "Sin errores de sintaxis.",
                "tmp_path": tmp_path,
                "target": target,
            }
        except UnicodeEncodeError as exc:
            return {
                "ok": False,
                "message": (
                    f"El texto contiene caracteres que no se pueden guardar en "
                    f"{encoding}: {exc}"
                ),
                "tmp_path": None,
                "target": target,
            }
        except OSError as exc:
            return {
                "ok": False,
                "message": f"No se pudo preparar {target}: {exc}",
                "tmp_path": None,
                "target": target,
            }
        finally:
            if tmp_path and not keep_tmp and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _after_prepare_save(self, result):
        if not result.get("ok"):
            self._set_saving(False)
            message = result.get("message", "")
            self.query_one("#dhcp-edit-status", Label).update(f"Error: {message}")
            self.app.notify(
                "No se guardó: dnsmasq --test rechazó la configuración.",
                severity="error",
            )
            self.query_one("#dhcp-config", TextArea).focus()
            return

        self._pending_save = result
        self.query_one("#dhcp-edit-status", Label).update(
            "Validación correcta. Confirma para guardar y reiniciar dnsmasq."
        )
        self.app.push_screen(
            ConfirmScreen(
                f"Se guardarán los cambios en {DNSMASQ_CONF}.\n\n"
                "dnsmasq --test:\n"
                f"{escape(result.get('message', ''))}\n\n"
                "Al guardar se reiniciará el servicio dnsmasq.\n\n"
                "¿Continuar?",
                confirm_text="Guardar y reiniciar",
                confirm_variant="success",
            ),
            self._on_save_confirmed,
        )

    def _on_save_confirmed(self, confirmed):
        pending = self._pending_save
        if pending is None:
            self._set_saving(False)
            return

        if not confirmed:
            self._discard_pending_save()
            self._set_saving(False)
            self.query_one("#dhcp-edit-status", Label).update(
                "Guardado cancelado; no se cambió nada."
            )
            self.app.notify(
                "No se guardaron los cambios.",
                severity="information",
            )
            self.query_one("#dhcp-config", TextArea).focus()
            return

        self.query_one("#dhcp-edit-status", Label).update(
            "Guardando y reiniciando dnsmasq…"
        )
        self.run_worker(
            lambda: self._do_commit_save(pending),
            thread=True,
        )

    def _discard_pending_save(self):
        pending = self._pending_save
        self._pending_save = None
        if not pending:
            return
        tmp_path = pending.get("tmp_path")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _do_commit_save(self, pending):
        try:
            result = self._commit_config_file(pending)
        except Exception as exc:
            result = {
                "written": False,
                "ok": False,
                "message": f"Error inesperado al guardar: {exc}",
                "backup_warning": "",
            }
        self.app.call_from_thread(self._after_save_config, result)

    def _commit_config_file(self, pending):
        """Aplica el temporal ya validado, crea la copia y reinicia dnsmasq."""
        target = pending.get("target") or os.path.realpath(DNSMASQ_CONF)
        tmp_path = pending.get("tmp_path")
        backup_warning = ""
        written = False

        try:
            if not tmp_path or not os.path.exists(tmp_path):
                return {
                    "written": False,
                    "ok": False,
                    "message": (
                        "No se encontró el archivo temporal validado. "
                        "Vuelve a intentar el guardado."
                    ),
                    "backup_warning": "",
                }

            try:
                original_stat = os.stat(target)
            except FileNotFoundError:
                original_stat = None

            if original_stat is not None:
                try:
                    shutil.copy2(target, target + ".ayanami.bak")
                except OSError as exc:
                    backup_warning = f"No se pudo crear la copia de seguridad: {exc}"

            os.replace(tmp_path, target)
            written = True

            try:
                restart = subprocess.run(
                    ["systemctl", "restart", "dnsmasq"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except FileNotFoundError:
                return {
                    "written": True,
                    "ok": False,
                    "message": "Archivo guardado, pero no se encontró systemctl.",
                    "backup_warning": backup_warning,
                }
            except subprocess.TimeoutExpired:
                return {
                    "written": True,
                    "ok": False,
                    "message": (
                        "Archivo guardado, pero systemctl restart agotó el tiempo "
                        "de espera."
                    ),
                    "backup_warning": backup_warning,
                }
            except OSError as exc:
                return {
                    "written": True,
                    "ok": False,
                    "message": (
                        f"Archivo guardado, pero no se pudo reiniciar dnsmasq: {exc}"
                    ),
                    "backup_warning": backup_warning,
                }

            restart_output = (restart.stdout + restart.stderr).strip()
            if restart.returncode != 0:
                return {
                    "written": True,
                    "ok": False,
                    "message": restart_output or (
                        f"systemctl restart salió con código {restart.returncode}."
                    ),
                    "backup_warning": backup_warning,
                }

            return {
                "written": True,
                "ok": True,
                "message": restart_output or "Servicio dnsmasq reiniciado correctamente.",
                "backup_warning": backup_warning,
            }
        except OSError as exc:
            return {
                "written": written,
                "ok": False,
                "message": f"No se pudo guardar {target}: {exc}",
                "backup_warning": backup_warning,
            }
        finally:
            if not written and tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _after_save_config(self, result):
        self._discard_pending_save()
        written = result.get("written", False)
        ok = result.get("ok", False)
        message = result.get("message", "")
        backup_warning = result.get("backup_warning", "")

        if written:
            self._set_editing(False)
        self._set_saving(False)

        if not written:
            self.query_one("#dhcp-edit-status", Label).update(f"Error: {message}")
            self.app.notify(
                "No se guardó la configuración. Revisa el error del editor.",
                severity="error",
            )
            self.query_one("#dhcp-config", TextArea).focus()
            return

        self.query_one("#dhcp-log", RichLog).clear()
        self.log("[#7dcfff]◆ Configuración de dnsmasq[/]")
        self.log(f"[#09b609]✓ Guardado en {DNSMASQ_CONF}[/]")
        if backup_warning:
            self.log(f"[#e0af68]⚠ {backup_warning}[/]")

        if ok:
            self.log("[#09b609]✓ Servicio dnsmasq reiniciado correctamente[/]")
        else:
            self.log("[#f7768e]✗ El archivo se guardó, pero dnsmasq no se reinició[/]")
            for line in message.splitlines():
                self.log(f"[#f7768e]{line}[/]")

        self.log("")
        self.show_status(clear=False)

        if ok:
            self.app.notify(
                "Configuración guardada y dnsmasq reiniciado.",
                severity="information",
            )
        else:
            self.app.notify(
                "Configuración guardada, pero dnsmasq no se reinició.",
                severity="warning",
            )

    def restart_service(self):
        # systemctl restart puede tardar: se corre en un hilo para no
        # congelar la interfaz y el resultado se pinta desde el hilo principal.
        self.log("[#7dcfff]◆ Reiniciando servicio dnsmasq…[/]")
        self.run_worker(self._do_restart, thread=True)

    def _do_restart(self):
        result = subprocess.run(
            "systemctl restart dnsmasq", shell=True, capture_output=True, text=True
        )
        self.app.call_from_thread(self._after_restart, result)

    def _after_restart(self, result):
        # Orden pedido: limpiar, mensaje del resultado, línea en blanco y estado.
        self.query_one("#dhcp-log", RichLog).clear()
        if result.returncode == 0:
            self.log("[#09b609]✓ Servicio dnsmasq reiniciado correctamente[/]")
        else:
            self.log("[#f7768e]✗ Error al reiniciar dnsmasq[/]")
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        self.log("")
        self.show_status(clear=False)
