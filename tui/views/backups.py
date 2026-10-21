from datetime import datetime

import json
import os
import shlex
import subprocess

from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Label, Button, RichLog

import network
import firewall_config
from firewall_ops import (
    get_dns_block_file,
    apply_whitelist,
    write_block_domains,
    save_whitelist,
)
from widgets.clickable_label import ClickableLabel
from widgets.confirm_screen import ConfirmScreen
from widgets.path_picker import PathPicker


TIMER_UNIT = "ayanami-backup.timer"


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB"):
        if value < 1024 or unit == "MB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} MB"


class BackupRow(Horizontal):
    """Fila de un backup mensual con sus acciones."""

    def __init__(self, info: dict, **kwargs):
        super().__init__(classes="bk-row", **kwargs)
        self.info = info

    def compose(self):
        date = datetime.fromtimestamp(self.info["mtime"]).strftime("%d/%m/%Y %H:%M")
        yield Label(self.info["bucket"], classes="bk-month")
        yield Label(_human_size(self.info["size"]), classes="bk-size")
        yield Label(date, classes="bk-date")
        yield Button(
            "Restaurar",
            id=f"bk-restore-{self.info['bucket']}",
            variant="primary",
            classes="bk-row-btn",
        )
        yield Button(
            "Eliminar",
            id=f"bk-del-{self.info['bucket']}",
            variant="error",
            classes="bk-row-btn",
        )


class BackupsView(Vertical):
    """Copias manuales y gestión de los backups automáticos de systemd."""

    def compose(self):
        with Vertical(classes="fw-card"):
            yield Label("Copia de Seguridad", classes="fw-card-title")
            with Horizontal(classes="bk-copy-row"):
                yield Label(
                    "Lista blanca, Apps y los datos de referencia del gateway en un único archivo JSON.",
                    classes="fw-card-desc",
                )
                with Horizontal(classes="bk-actions bk-copy-actions"):
                    yield ClickableLabel(
                        "[Guardar Copia]",
                        id="bk-export",
                        classes="bk-action-link bk-action-save",
                        markup=False,
                    )
                    yield ClickableLabel(
                        "[Cargar Copia]",
                        id="bk-import",
                        classes="bk-action-link bk-action-load",
                        markup=False,
                    )

        with Vertical(classes="fw-card"):
            yield Label("Respaldos automáticos", classes="fw-card-title")
            yield Label(
                f"Timer mensual de systemd con retención de los últimos "
                f"{firewall_config.RETENTION_MONTHS} meses. "
                "Instalar o desinstalar el timer requiere permisos de administrador.",
                classes="fw-card-desc",
            )
            with Horizontal(classes="bk-status-row"):
                yield Label("Timer:", classes="bk-status-key")
                yield Label("consultando…", id="bk-timer-state", classes="bk-status-value")
            with Horizontal(classes="bk-status-row"):
                yield Label("Próxima ejecución:", classes="bk-status-key")
                yield Label("—", id="bk-timer-next", classes="bk-status-value")
            with Horizontal(classes="bk-actions"):
                yield Button("Actualizar", id="bk-refresh", variant="default")
                yield Button("Backup Ahora", id="bk-run", variant="success")
                yield Button("Instalar Timer", id="bk-install", variant="success")
                yield Button("Desinstalar Timer", id="bk-uninstall", variant="error")

        with Vertical(classes="fw-card"):
            yield Label("Backups mensuales disponibles", classes="fw-card-title")
            with ScrollableContainer(id="bk-list"):
                yield Label("  Abrí la vista para cargar la lista", classes="bk-empty")

        yield RichLog(id="bk-log", markup=True, highlight=True)

    # ── Datos y estado ───────────────────────────────────

    def refresh_data(self):
        self.run_worker(self._refresh_worker, name="bk-refresh", group="backups", thread=True)

    def _refresh_worker(self):
        backups = firewall_config.list_backups()
        status = self._read_timer_status()
        self.app.call_from_thread(self._render_data, backups, status)

    def _systemctl(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["systemctl", *args],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"error: {exc}"
        return (result.stdout or result.stderr).strip()

    def _read_timer_status(self) -> dict:
        enabled = self._systemctl("is-enabled", TIMER_UNIT)
        active = self._systemctl("is-active", TIMER_UNIT)
        next_run = self._systemctl(
            "show", TIMER_UNIT,
            "--property=NextElapseUSecRealtime",
            "--value",
        )

        # `systemctl is-enabled` devuelve un estado conocido si el unit
        # existe; cualquier error (systemd ausente, unit inexistente) se
        # trata como "no instalado" para no ofrecer "Desinstalar".
        known_states = {
            "enabled", "enabled-runtime", "linked", "linked-runtime",
            "alias", "masked", "masked-runtime", "static", "indirect",
            "disabled", "generated", "transient",
        }
        if enabled not in known_states:
            enabled = "not-found"
        if (not next_run or next_run == "n/a" or next_run.startswith("error:")
                or next_run.startswith("Failed") or "not be found" in next_run):
            next_run = "sin programar"

        installed = enabled != "not-found"
        return {
            "enabled": enabled,
            "active": active or "desconocido",
            "next": next_run,
            "installed": installed,
        }

    def _set_status(self, label: Label, text: str, kind: str):
        label.update(text)
        for cls in ("bk-ok", "bk-warn", "bk-error"):
            label.remove_class(cls)
        label.add_class(kind)

    def _render_data(self, backups: list[dict], status: dict):
        state = self.query_one("#bk-timer-state", Label)
        enabled = status["enabled"]
        active = status["active"]

        if not status["installed"]:
            self._set_status(state, "no instalado", "bk-error")
        elif enabled == "enabled" and active == "active":
            self._set_status(state, "instalado · activo", "bk-ok")
        elif enabled == "enabled":
            self._set_status(state, f"instalado · {active}", "bk-warn")
        else:
            self._set_status(state, f"instalado · {enabled}", "bk-warn")

        self.query_one("#bk-timer-next", Label).update(
            status["next"] if status["installed"] else "—"
        )
        self.query_one("#bk-install", Button).display = not status["installed"]
        self.query_one("#bk-uninstall", Button).display = status["installed"]

        container = self.query_one("#bk-list", ScrollableContainer)
        container.remove_children()
        if not backups:
            container.mount(
                Label("  No hay backups mensuales todavía", classes="bk-empty")
            )
            return
        for info in backups:
            container.mount(BackupRow(info))

    # ── Botones ──────────────────────────────────────────

    def on_clickable_label_pressed(self, event: ClickableLabel.Pressed):
        if event.label.id == "bk-export":
            self._request_export()
        elif event.label.id == "bk-import":
            self._request_import()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "bk-refresh":
            self.refresh_data()
        elif bid == "bk-run":
            self.create_backup_now()
        elif bid == "bk-install":
            self.install_timer()
        elif bid == "bk-uninstall":
            self.uninstall_timer()
        elif bid and bid.startswith("bk-restore-"):
            row = self._row_for_button(event.button)
            if row is not None:
                self._confirm_import(row.info["path"])
        elif bid and bid.startswith("bk-del-"):
            row = self._row_for_button(event.button)
            if row is not None:
                self.delete_backup(row.info)

    def _row_for_button(self, button: Button) -> BackupRow | None:
        node = button.parent
        while node is not None and not isinstance(node, BackupRow):
            node = node.parent
        return node

    # ── Copia manual ─────────────────────────────────────

    def _request_export(self):
        self.app.push_screen(
            PathPicker(
                "Guardar Configuración",
                firewall_config.CONFIG_FILE,
                confirm_text="Guardar",
            ),
            self._do_export,
        )

    def _request_import(self):
        self.app.push_screen(
            PathPicker(
                "Cargar Configuración",
                firewall_config.CONFIG_FILE,
                confirm_text="Cargar",
            ),
            self._pick_import_path,
        )

    def _pick_import_path(self, path):
        if not path:
            return
        if not os.path.exists(path):
            self.app.notify("El archivo seleccionado no existe", severity="error")
            return
        if os.path.isdir(str(path).strip().rstrip(os.sep)):
            self.app.notify(
                "Seleccionaste una carpeta: elige el archivo de configuración",
                severity="error",
            )
            return
        self._confirm_import(path)

    def _confirm_import(self, path):
        candidate = firewall_config.load_config(path)
        ok, reason = firewall_config.validate_config(candidate)
        if not ok:
            self.app.notify(
                f"No es un archivo de configuración válido: {reason}",
                severity="error",
            )
            return

        self.app.push_screen(
            ConfirmScreen(
                f"Se cargará:\n\n{path}\n\n"
                "Se reaplicarán lista blanca, apps y gateway/NAT.\n"
                "Se sobrescribirá el estado actual.\n\n"
                "¿Continuar?",
                confirm_text="Cargar",
                confirm_variant="success",
            ),
            lambda confirmed: self._import_config(confirmed, path),
        )

    def _do_export(self, path):
        """Guarda el estado actual y crea el backup mensual inmediato."""
        if not path:
            return

        stripped = str(path).strip().rstrip(os.sep)
        if not stripped:
            path = firewall_config.CONFIG_FILE
        elif os.path.isdir(stripped):
            path = os.path.join(stripped, "firewall_config.json")
        else:
            path = stripped

        self.query_one("#bk-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Guardar Configuración ━━━[/]")
        self.log(f"[#565f89]  → Destino: {path}[/]")

        wan, lan, dns_target = self._gateway_values()
        bundle = firewall_config.build_bundle(
            wan_iface=wan,
            lan_iface=lan,
            dns_target=dns_target,
        )

        target = firewall_config.save_config(bundle, path=path)
        self.log(f"[#9ece6a]  ✓ Configuración guardada en {target}[/]")

        # Mantener la copia canónica al día para que el timer mensual
        # siempre respalde la configuración más reciente.
        if os.path.abspath(target) != os.path.abspath(firewall_config.CONFIG_FILE):
            firewall_config.save_config(bundle)
            self.log(
                f"[#565f89]  → Copia canónica también en "
                f"{firewall_config.CONFIG_FILE}[/]"
            )

        stats = bundle.get("stats", {})
        self.log(
            f"[#565f89]  → {stats.get('whitelist_count', 0)} entradas en lista blanca, "
            f"{stats.get('apps_count', 0)} apps, "
            f"{stats.get('blocked_count', 0)} bloqueadas[/]"
        )

        backup = firewall_config.save_backup()
        removed = firewall_config.prune_backups()
        if backup:
            self.log(f"[#9ece6a]  ✓ Backup mensual: {backup}[/]")
        if removed:
            self.log(
                f"[#565f89]  → Backups viejos eliminados: {len(removed)}[/]"
            )

        self.refresh_data()
        self.app.notify("Configuración guardada")

    def _gateway_values(self) -> tuple[str, str, str]:
        stored = firewall_config.load_config().get("gateway", {})
        lan = self._get_selected_interface() or stored.get("lan_iface", "")
        dns_target = ""
        if lan:
            dns_target = network.get_iface_ip(lan) or stored.get("dns_target", "")
        return stored.get("wan_iface", ""), lan, dns_target

    def _get_selected_interface(self):
        return getattr(self.app, "selected_interface", None)

    def _import_config(self, confirmed: bool | None = None, path: str | None = None):
        if not confirmed:
            return
        source = path or firewall_config.CONFIG_FILE
        self.query_one("#bk-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Cargar Configuración ━━━[/]")
        self.log(f"[#565f89]  → Origen: {source}[/]")

        config = firewall_config.load_config(source)

        ok, reason = firewall_config.validate_config(config)
        if not ok:
            self.log(
                f"[#f7768e]  ✗ {source} no es un archivo de configuración válido: "
                f"{reason}[/]"
            )
            self.app.notify("El archivo no es válido", severity="error")
            return

        # ── Lista blanca ─────────────────────────────────
        whitelist = config.get("whitelist", [])
        whitelist_disabled = config.get("whitelist_disabled", [])
        save_whitelist(whitelist, whitelist_disabled)
        self.log(
            f"[#9ece6a]  ✓ Lista blanca restaurada "
            f"({len(whitelist)} entradas, {len(whitelist_disabled)} desactivadas)[/]"
        )

        # ── Apps ─────────────────────────────────────────
        apps = config.get("apps", {})
        with open(firewall_config.APPS_FILE, "w") as f:
            json.dump(apps, f, indent=2, ensure_ascii=False)
            f.write("\n")
        blocked_domains = []
        for info in apps.values():
            if info.get("blocked"):
                blocked_domains.extend(info.get("domains", []))
        self.log(
            f"[#9ece6a]  ✓ Registro de apps restaurado "
            f"({len(apps)} apps, {len(blocked_domains)} dominios bloqueados)[/]"
        )

        # ── Firewall: aplicar whitelist + bloqueo DNS ────
        self.log("[#7dcfff]◆ Aplicando reglas de lista blanca[/]")
        apply_whitelist()
        self.log("[#9ece6a]  ✓ Reglas de lista blanca aplicadas[/]")

        self.log("[#7dcfff]◆ Regenerando configuración de bloqueo DNS[/]")
        dns_conf = get_dns_block_file()
        if os.path.exists(dns_conf):
            os.remove(dns_conf)
        write_block_domains(blocked_domains)
        self.log(
            f"[#9ece6a]  ✓ Bloqueo DNS regenerado "
            f"({len(blocked_domains)} dominios)[/]"
        )

        # ── Gateway / NAT ────────────────────────────────
        gw = config.get("gateway", {})
        wan = gw.get("wan_iface", "")
        lan = gw.get("lan_iface", "")
        stored_target = gw.get("dns_target", "")
        if wan:
            self.log("[#7dcfff]◆ Reaplicando gateway[/]")
            self.run("sysctl -w net.ipv4.ip_forward=1")
            self.run(
                f"iptables -t nat -C POSTROUTING -o {wan} -j MASQUERADE 2>/dev/null || "
                f"iptables -t nat -A POSTROUTING -o {wan} -j MASQUERADE"
            )
            if lan:
                dns_target = network.get_iface_ip(lan) or stored_target
            else:
                dns_target = stored_target
            if dns_target:
                for proto in ("udp", "tcp"):
                    self.run(
                        f"iptables -t nat -C PREROUTING -p {proto} --dport 53 "
                        f"-j DNAT --to-destination {dns_target} 2>/dev/null || "
                        f"iptables -t nat -A PREROUTING -p {proto} --dport 53 "
                        f"-j DNAT --to-destination {dns_target}"
                    )
                self.log(
                    f"[#9ece6a]  ✓ Gateway reaplicado: WAN={wan} "
                    f"DNS→{dns_target}[/]"
                )
            else:
                self.log(
                    "[#f7768e]  ✗ Sin DNS target: no se pudo reaplicar "
                    "la redirección DNS[/]"
                )
        else:
            self.log("[#565f89]  → Sin gateway guardado, se omite[/]")

        # ── Aplicar cambios y refrescar vistas ────────────
        self.log("[#7dcfff]◆ Reiniciando NetworkManager[/]")
        self.run("systemctl restart NetworkManager")
        self.log("[#9ece6a]  ✓ Cambios aplicados[/]")
        self.log("[#9ece6a]━━━ Configuración cargada ━━━[/]")

        apps_tab = self.screen.query_one("#fw-panel-apps")
        if hasattr(apps_tab, "refresh_apps"):
            apps_tab.refresh_apps()
        rules_tab = self.screen.query_one("#fw-panel-rules")
        if hasattr(rules_tab, "refresh_list"):
            rules_tab.refresh_list()

        self.app.notify("Configuración cargada y aplicada")

    # ── Backups automáticos ──────────────────────────────

    def create_backup_now(self):
        self.query_one("#bk-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Backup manual ━━━[/]")
        self.log("[#7dcfff]◆ Copiando la configuración actual…[/]")
        self.run_worker(self._do_backup_now, name="bk-run", group="backups", thread=True)

    def _do_backup_now(self):
        wan, lan, dns_target = self._gateway_values()
        bundle = firewall_config.build_bundle(
            wan_iface=wan,
            lan_iface=lan,
            dns_target=dns_target,
        )
        firewall_config.save_config(bundle)
        target = firewall_config.save_backup()
        removed = firewall_config.prune_backups()
        self.app.call_from_thread(self._after_backup_now, target, removed)

    def _after_backup_now(self, target: str | None, removed: list[str]):
        if target:
            self.log(f"[#9ece6a]  ✓ Backup creado: {target}[/]")
        else:
            self.log("[#f7768e]  ✗ No se pudo crear el backup[/]")
        if removed:
            self.log(f"[#565f89]  → Backups viejos eliminados: {len(removed)}[/]")
        self.refresh_data()
        if target:
            self.app.notify("Backup creado")
        else:
            self.app.notify("No se pudo crear el backup", severity="error")

    def install_timer(self):
        self.app.push_screen(
            ConfirmScreen(
                "Se instalará y activará el timer mensual de systemd.\n\n"
                "El backup se ejecutará el primer día de cada mes.\n\n"
                "¿Continuar?",
                confirm_text="Instalar",
                confirm_variant="success",
            ),
            lambda confirmed: confirmed and self._run_timer_action("install"),
        )

    def uninstall_timer(self):
        self.app.push_screen(
            ConfirmScreen(
                "Se desinstalará el timer mensual de systemd.\n\n"
                "Los backups existentes se conservan.\n\n"
                "¿Continuar?",
                confirm_text="Desinstalar",
            ),
            lambda confirmed: confirmed and self._run_timer_action("uninstall"),
        )

    def _run_timer_action(self, action: str):
        script = firewall_config.INSTALL_BACKUP_TIMER
        self.query_one("#bk-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Timer de backups ━━━[/]")
        if not os.path.exists(script):
            self.log(f"[#f7768e]  ✗ No se encontró {script}[/]")
            self.app.notify("No se encontró el instalador del timer", severity="error")
            return

        cmd = f"bash {shlex.quote(script)}"
        if action == "uninstall":
            cmd += " --uninstall"
        self.log(f"[#565f89]$ {cmd}[/]")
        self.run_worker(
            lambda: self._do_timer_cmd(cmd),
            name=f"bk-timer-{action}",
            group="backups",
            thread=True,
        )

    def _do_timer_cmd(self, cmd: str):
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        self.app.call_from_thread(self._after_timer_cmd, result)

    def _after_timer_cmd(self, result):
        if result.returncode == 0:
            self.log("[#9ece6a]  ✓ Operación completada[/]")
        else:
            self.log("[#f7768e]  ✗ Error al gestionar el timer[/]")
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                self.log(f"[#a9b1d6]{line}[/]")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        self.refresh_data()
        if result.returncode == 0:
            self.app.notify("Timer actualizado")
        else:
            self.app.notify("Error al actualizar el timer", severity="error")

    def delete_backup(self, info: dict):
        def on_confirm(confirmed):
            if not confirmed:
                return
            if firewall_config.delete_backup(info["path"]):
                self.log(
                    f"[#9ece6a]✓ Backup eliminado: {info['bucket']}[/]"
                )
                self.refresh_data()
                self.app.notify(f"Backup {info['bucket']} eliminado")
            else:
                self.log(
                    f"[#f7768e]✗ No se pudo eliminar {info['path']}[/]"
                )
                self.app.notify("No se pudo eliminar el backup", severity="error")

        self.app.push_screen(
            ConfirmScreen(
                f"¿Eliminar el backup {info['bucket']}?\n\n{info['path']}",
                confirm_text="Eliminar",
            ),
            on_confirm,
        )

    # ── Helpers de log ───────────────────────────────────

    def log(self, text: str):
        self.query_one("#bk-log", RichLog).write(text)

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
