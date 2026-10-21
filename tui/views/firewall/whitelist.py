import re
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Label, Button, Input, Static, Switch
from widgets.confirm_screen import ConfirmScreen
from firewall_ops import (
    load_whitelist,
    load_disabled_entries,
    add_whitelist_ip,
    remove_whitelist_ip,
    apply_whitelist,
    is_valid_whitelist_entry,
    is_valid_ip,
    is_valid_cidr,
    is_valid_range,
    is_valid_mac,
    normalize_mac,
    is_entry_enabled,
    set_entry_enabled,
)


def safe_id(entry: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", entry)


def _entry_type(entry: str) -> str:
    if is_valid_mac(entry):
        return "MAC"
    if is_valid_ip(entry):
        return "IP"
    if is_valid_cidr(entry):
        return "CIDR"
    if is_valid_range(entry):
        return "RANGO"
    return "?"


class IPRow(Horizontal):
    def __init__(self, ip_entry: str, enabled: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.ip_entry = ip_entry
        self._safe = safe_id(ip_entry)
        self._enabled = enabled
        if not enabled:
            self.add_class("wl-row-disabled")

    def compose(self):
        entry_type = _entry_type(self.ip_entry)
        tag_cls = {
            "IP": "wl-tag-ip",
            "CIDR": "wl-tag-cidr",
            "RANGE": "wl-tag-range",
            "MAC": "wl-tag-mac",
        }.get(entry_type, "wl-tag-range")
        yield Label(entry_type, classes=f"wl-type-tag {tag_cls}")
        yield Static(self.ip_entry, classes="wl-ip-text")
        yield Switch(
            value=self._enabled,
            id=f"wl-switch-{self._safe}",
            classes="wl-row-switch",
        )
        yield Button("Quitar", id=f"wl-del-{self._safe}", variant="error", classes="wl-remove-btn")

    def set_enabled(self, enabled: bool):
        """Pinta el estado de la fila sin recrearla."""
        self._enabled = enabled
        self.set_class(not enabled, "wl-row-disabled")


class WhitelistTab(Vertical):
    def compose(self):
        with Vertical(classes="fw-card"):
            yield Label("Lista Blanca de IPs y MACs", classes="fw-card-title")
            yield Label(
                "Estas IPs y MACs ignoran todas las reglas de bloqueo del firewall. "
                "El switch de cada fila activa o desactiva esa entrada.",
                classes="fw-card-desc"
            )
            with Horizontal(classes="wl-input-row"):
                yield Input(
                    placeholder="10.0.0.2  |  10.0.0.1/21  |  10.0.0.1-10.0.7.254  |  AA:BB:CC:DD:EE:FF",
                    id="wl-input",
                    classes="wl-input"
                )
                yield Button("Agregar", id="wl-add", variant="primary", classes="wl-add-btn")

        with ScrollableContainer(id="wl-container"):
            pass

    def on_mount(self):
        self.refresh_list()

    def on_switch_changed(self, event: Switch.Changed):
        if not (event.switch.id and event.switch.id.startswith("wl-switch-")):
            return
        safe = event.switch.id.replace("wl-switch-", "")
        entry = next(
            (e for e in load_whitelist() if safe_id(e) == safe),
            None,
        )
        if entry is None:
            return
        # El Switch emite Changed al montarse: solo actuamos si el estado cambió.
        if event.value == is_entry_enabled(entry):
            return

        set_entry_enabled(entry, event.value)

        node = event.switch
        while node is not None and not isinstance(node, IPRow):
            node = node.parent
        if node is not None:
            node.set_enabled(event.value)

        self.run_worker(
            self._apply_and_notify, name="wl-apply", group="firewall", thread=True
        )
        self.notify(
            f"{'Activada' if event.value else 'Desactivada'}: {entry}"
        )

    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id
        if btn_id == "wl-add":
            self.add_ip()
        elif btn_id and btn_id.startswith("wl-del-"):
            safe = btn_id.replace("wl-del-", "")
            whitelist = load_whitelist()
            match = next((ip for ip in whitelist if safe_id(ip) == safe), None)
            if match:
                self.remove_ip(match)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "wl-input":
            self.add_ip()

    def add_ip(self):
        inp = self.query_one("#wl-input", Input)
        entry = inp.value.strip()
        if not entry:
            self.notify("Escribe una IP, CIDR, rango o MAC", severity="warning")
            return
        if is_valid_mac(entry):
            entry = normalize_mac(entry)
        if not is_valid_whitelist_entry(entry):
            self.notify(
                "Formato invalido.\n"
                "  IP:   192.168.1.100\n"
                "  CIDR: 192.168.1.0/24\n"
                "  Rango: 10.0.0.1-10.0.0.255\n"
                "  MAC:  AA:BB:CC:DD:EE:FF",
                severity="error",
                timeout=6
            )
            return
        if add_whitelist_ip(entry):
            inp.value = ""
            self.refresh_list()
            self.run_worker(self._apply_and_notify, name="wl-apply", group="firewall", thread=True)
            self.notify(f"Agregada: {entry}")
        else:
            self.notify(f"'{entry}' ya esta en la lista", severity="warning")

    def remove_ip(self, ip: str):
        def on_confirm(confirmed):
            if confirmed:
                remove_whitelist_ip(ip)
                self.refresh_list()
                self.run_worker(self._apply_and_notify, name="wl-apply", group="firewall", thread=True)
                self.notify(f"Eliminada: {ip}")

        self.app.push_screen(
            ConfirmScreen(f"Quitar '{ip}' de la lista blanca?"),
            on_confirm
        )

    def _apply_and_notify(self):
        apply_whitelist()
        total = len(load_whitelist())
        disabled = len(load_disabled_entries())
        suffix = f", {disabled} desactivada{'s' if disabled != 1 else ''}" if disabled else ""
        self.app.call_from_thread(
            self.app.notify,
            f"Firewall actualizado ({total} entradas{suffix})"
        )

    def refresh_list(self):
        container = self.query_one("#wl-container", ScrollableContainer)
        container.remove_children()
        whitelist = load_whitelist()
        disabled = set(load_disabled_entries())
        if not whitelist:
            container.mount(Label("  No hay entradas en la lista blanca", classes="wl-empty"))
            return
        for entry in whitelist:
            container.mount(IPRow(entry, enabled=entry not in disabled))
