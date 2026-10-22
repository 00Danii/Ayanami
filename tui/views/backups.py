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
from widgets.backup_timer_modal import BackupTimerModal
from widgets.clickable_label import ClickableLabel
from widgets.confirm_screen import ConfirmScreen
from widgets.path_picker import PathPicker


TIMER_UNIT = "ayanami-backup.timer"


def _human_size(size: int) -> str:
    """Tamaño compacto para que la tabla entre en el ancho de la tarjeta."""
    value = float(size)
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f}M"
    if value >= 1024:
        return f"{value / 1024:.0f}K"
    return f"{value:.0f}B"


def _backup_label(info: dict) -> str:
    return datetime.fromtimestamp(info["mtime"]).strftime("%Y-%m-%d %H:%M")


class BackupTableHeader(Horizontal):
    """Encabezado de la tabla de backups."""

    def __init__(self):
        super().__init__(classes="bk-table-head")

    def compose(self):
        yield Label("Año", classes="bk-col bk-col-year")
        yield Label("Mes", classes="bk-col bk-col-month")
        yield Label("Día", classes="bk-col bk-col-day")
        yield Label("Hora", classes="bk-col bk-col-hour")
        yield Label("Tam", classes="bk-col bk-col-size")
        yield Label("Acciones", classes="bk-col bk-col-actions")


class BackupRow(Horizontal):
    """Fila de un backup automático con sus acciones."""

    def __init__(self, info: dict, **kwargs):
        super().__init__(classes="bk-row", **kwargs)
        self.info = info

    def compose(self):
        moment = datetime.fromtimestamp(self.info["mtime"])
        yield Label(moment.strftime("%Y"), classes="bk-col bk-col-year")
        yield Label(moment.strftime("%m"), classes="bk-col bk-col-month")
        yield Label(moment.strftime("%d"), classes="bk-col bk-col-day")
        yield Label(moment.strftime("%H:%M"), classes="bk-col bk-col-hour")
        yield Label(_human_size(self.info["size"]), classes="bk-col bk-col-size")
        with Horizontal(classes="bk-row-actions"):
            yield ClickableLabel(
                "Restaurar",
                id=f"bk-restore-{self.info['bucket']}",
                classes="bk-row-link",
                markup=False,
            )
            yield ClickableLabel(
                "Eliminar",
                id=f"bk-del-{self.info['bucket']}",
                classes="bk-row-link bk-row-link-delete",
                markup=False,
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
                f"Timer de systemd para editar la frecuencia y el modo persistente.",
                classes="fw-card-desc",
            )
            with Horizontal(classes="bk-auto-row"):
                with Vertical(classes="bk-status-col"):
                    with Horizontal(classes="bk-status-row"):
                        yield Label("Timer:", classes="bk-status-key")
                        yield Label("consultando…", id="bk-timer-state", classes="bk-status-value")
                    with Horizontal(classes="bk-status-row"):
                        yield Label("Próxima ejecución:", classes="bk-status-key")
                        yield Label("—", id="bk-timer-next", classes="bk-status-value")
                    with Horizontal(classes="bk-status-row"):
                        yield Label("Programación:", classes="bk-status-key")
                        yield Label("—", id="bk-timer-calendar", classes="bk-status-value")
                with Horizontal(classes="bk-actions"):
                    yield Button(
                        "Ver estado",
                        id="bk-status",
                        tooltip="Mostrar el estado del timer en el log",
                    )
                    yield Button(
                        "Editar",
                        id="bk-edit",
                        variant="primary",
                        tooltip="Editar la configuración del timer",
                    )
                    yield Button(
                        "Instalar Timer",
                        id="bk-install",
                        variant="success",
                        tooltip="Instalar el timer de backups",
                    )
                    yield Button(
                        "Desinstalar Timer",
                        id="bk-uninstall",
                        variant="error",
                        tooltip="Desinstalar el timer de backups",
                    )

        with Horizontal(classes="bk-bottom-row"):
            with Vertical(classes="fw-card bk-list-card"):
                yield Label("Backups disponibles\n", classes="fw-card-title")
                with ScrollableContainer(id="bk-list"):
                    yield Label("  Abrir para cargar la lista", classes="bk-empty")

            with Vertical(classes="fw-card bk-log-card"):
                yield Label("Log de salida", classes="fw-card-title")
                yield RichLog(id="bk-log", markup=True, highlight=True)

    # ── Datos y estado ───────────────────────────────────

    def on_mount(self):
        # Hasta conocer el estado real, solo dejamos visible "Instalar Timer".
        for widget_id in ("bk-status", "bk-edit", "bk-uninstall"):
            self.query_one(f"#{widget_id}", Button).display = False

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
        unit_text = self._systemctl("cat", TIMER_UNIT)

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

        calendar = "monthly"
        persistent = True
        for line in unit_text.splitlines():
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            value = value.strip()
            if key == "OnCalendar" and value:
                calendar = value
            elif key == "Persistent":
                persistent = value.lower() in ("1", "true", "yes", "on")

        installed = enabled != "not-found"
        return {
            "enabled": enabled,
            "active": active or "desconocido",
            "next": next_run,
            "installed": installed,
            "calendar": calendar,
            "persistent": persistent,
        }

    def _set_status(self, label: Label, text: str, kind: str):
        label.update(text)
        for cls in ("bk-ok", "bk-warn", "bk-error"):
            label.remove_class(cls)
        label.add_class(kind)

    @staticmethod
    def _short_next_run(value: str) -> str:
        """Convierte 'Sun 2026-11-01 00:00:00 CST' en '2026-11-01 00:00'."""
        parts = value.split()
        for index, part in enumerate(parts):
            if len(part) == 10 and part[4] == "-" and part[7] == "-":
                if index + 1 < len(parts):
                    return f"{part} {parts[index + 1][:5]}"
                return part
        return value

    def _render_data(self, backups: list[dict], status: dict):
        self._timer_status = status
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
            self._short_next_run(status["next"]) if status["installed"] else "—"
        )
        self.query_one("#bk-timer-calendar", Label).update(
            f"{status['calendar']} · "
            f"{'persistente' if status['persistent'] else 'no persistente'}"
        )
        self.query_one("#bk-install", Button).display = not status["installed"]
        self.query_one("#bk-uninstall", Button).display = status["installed"]
        self.query_one("#bk-status", Button).display = status["installed"]
        self.query_one("#bk-edit", Button).display = status["installed"]

        container = self.query_one("#bk-list", ScrollableContainer)
        container.remove_children()
        if not backups:
            container.mount(
                Label("  No hay backups", classes="bk-empty")
            )
            return
        container.mount(BackupTableHeader())
        for info in backups:
            container.mount(BackupRow(info))

    # ── Botones ──────────────────────────────────────────

    def on_clickable_label_pressed(self, event: ClickableLabel.Pressed):
        bid = event.label.id or ""
        if bid == "bk-export":
            self._request_export()
        elif bid == "bk-import":
            self._request_import()
        elif bid.startswith("bk-restore-"):
            row = self._row_for_widget(event.label)
            if row is not None:
                self._confirm_import(row.info["path"])
        elif bid.startswith("bk-del-"):
            row = self._row_for_widget(event.label)
            if row is not None:
                self.delete_backup(row.info)

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "bk-refresh":
            self.refresh_data()
        elif bid == "bk-run":
            self.create_backup_now()
        elif bid == "bk-status":
            self.show_timer_status()
        elif bid == "bk-edit":
            self.edit_timer_config()
        elif bid == "bk-install":
            self.install_timer()
        elif bid == "bk-uninstall":
            self.uninstall_timer()

    def _row_for_widget(self, widget) -> BackupRow | None:
        node = widget.parent
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
        candidate, read_error = firewall_config.load_config_checked(path)
        if read_error:
            self.app.notify(
                f"No se pudo leer la copia: {read_error}",
                severity="error",
            )
            return

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
        """Guarda el estado actual y crea el backup de inmediato."""
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

        # Mantener la copia canónica al día para que el timer programado
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
            self.log(f"[#9ece6a]  ✓ Backup creado: {backup}[/]")
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

        config, read_error = firewall_config.load_config_checked(source)
        if read_error:
            self.log(
                f"[#f7768e]  ✗ No se pudo leer {source}: {read_error}[/]"
            )
            self.app.notify("No se pudo leer el archivo", severity="error")
            return

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

    def show_timer_status(self):
        """Consulta systemd y escribe el estado completo en el log."""
        self.query_one("#bk-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Estado del timer ━━━[/]")
        self.log("[#7dcfff]◆ Consultando systemd…[/]")
        self.run_worker(
            self._do_show_timer_status,
            name="bk-status",
            group="backups",
            thread=True,
        )

    def _do_show_timer_status(self):
        status = self._read_timer_status()
        detail = self._systemctl("status", TIMER_UNIT, "--no-pager", "--full")
        self.app.call_from_thread(self._after_show_timer_status, status, detail)

    def _after_show_timer_status(self, status: dict, detail: str):
        if status["installed"]:
            state = f"{status['enabled']} · {status['active']}"
            next_run = self._short_next_run(status["next"])
        else:
            state = "no instalado"
            next_run = "—"

        self.log(f"[#a9b1d6]Timer:[/] {state}")
        self.log(f"[#a9b1d6]Próxima ejecución:[/] {next_run}")
        self.log(f"[#a9b1d6]Programación:[/] {status['calendar']}")
        self.log(
            f"[#a9b1d6]Persistent:[/] "
            f"{'sí' if status['persistent'] else 'no'}"
        )
        if detail:
            self.log("[#565f89]── systemctl status ──[/]")
            for line in detail.splitlines():
                self.log(f"[#a9b1d6]  {line}[/]")
        self.log("[#9ece6a]  ✓ Estado consultado[/]")

    def edit_timer_config(self):
        status = getattr(self, "_timer_status", {})
        self.app.push_screen(
            BackupTimerModal(
                calendar=status.get("calendar", "monthly"),
                persistent=status.get("persistent", True),
            ),
            self._configure_timer,
        )

    def _configure_timer(self, config: dict | None):
        if not config:
            return

        calendar = config["calendar"]
        persistent = config["persistent"]
        self.app.push_screen(
            ConfirmScreen(
                "Se aplicará la configuración del timer:\n\n"
                f"OnCalendar: {calendar}\n"
                f"Persistent: {'sí' if persistent else 'no'}\n\n"
                "Se instalará o reiniciará el timer.\n\n"
                "¿Continuar?",
                confirm_text="Aplicar",
                confirm_variant="success",
            ),
            lambda confirmed: confirmed and self._run_timer_action(
                "install",
                calendar=calendar,
                persistent=persistent,
            ),
        )

    def install_timer(self):
        """Antes de instalar, abre el editor para elegir la programación."""
        self.edit_timer_config()

    def uninstall_timer(self):
        self.app.push_screen(
            ConfirmScreen(
                "Se desinstalará el timer de backups de systemd.\n\n"
                "Los backups existentes se conservan.\n\n"
                "¿Continuar?",
                confirm_text="Desinstalar",
            ),
            lambda confirmed: confirmed and self._run_timer_action("uninstall"),
        )

    def _run_timer_action(
        self,
        action: str,
        calendar: str | None = None,
        persistent: bool | None = None,
    ):
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
        else:
            if calendar is not None:
                cmd += f" --calendar {shlex.quote(str(calendar))}"
            if persistent is not None:
                cmd += f" --persistent {'true' if persistent else 'false'}"
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
        label = _backup_label(info)

        def on_confirm(confirmed):
            if not confirmed:
                return
            if firewall_config.delete_backup(info["path"]):
                self.log(f"[#9ece6a]✓ Backup eliminado: {label}[/]")
                self.refresh_data()
                self.app.notify(f"Backup {label} eliminado")
            else:
                self.log(
                    f"[#f7768e]✗ No se pudo eliminar {info['path']}[/]"
                )
                self.app.notify("No se pudo eliminar el backup", severity="error")

        self.app.push_screen(
            ConfirmScreen(
                f"¿Eliminar el backup {label}?\n\n{info['path']}",
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
