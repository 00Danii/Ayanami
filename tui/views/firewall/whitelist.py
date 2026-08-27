import re
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Label, Button, Input, Static
from widgets.confirm_screen import ConfirmScreen
from firewall_ops import (
    load_whitelist,
    add_whitelist_ip,
    remove_whitelist_ip,
    apply_whitelist,
    is_valid_whitelist_entry,
    is_valid_ip,
    is_valid_cidr,
    is_valid_range,
)


def safe_id(entry: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", entry)


def _entry_type(entry: str) -> str:
    if is_valid_ip(entry):
        return "IP"
    if is_valid_cidr(entry):
        return "CIDR"
    if is_valid_range(entry):
        return "RANGO"
    return "?"


class IPRow(Horizontal):
    def __init__(self, ip_entry: str, **kwargs):
        super().__init__(**kwargs)
        self.ip_entry = ip_entry
        self._safe = safe_id(ip_entry)

    def compose(self):
        entry_type = _entry_type(self.ip_entry)
        tag_cls = "wl-tag-ip" if entry_type == "IP" else (
            "wl-tag-cidr" if entry_type == "CIDR" else "wl-tag-range"
        )
        yield Label(entry_type, classes=f"wl-type-tag {tag_cls}")
        yield Static(self.ip_entry, classes="wl-ip-text")
        yield Button("Quitar", id=f"wl-del-{self._safe}", variant="error", classes="wl-remove-btn")


class WhitelistTab(Vertical):
    def compose(self):
        with Vertical(classes="fw-card"):
            yield Label("Lista Blanca de IPs", classes="fw-card-title")
            yield Label(
                "Estas IPs ignoran todas las reglas de bloqueo del firewall. "
                "El DNS de estas IPs se resuelve externamente (sin filtros).",
                classes="fw-card-desc"
            )
            with Horizontal(classes="wl-input-row"):
                yield Input(
                    placeholder="192.168.1.100  |  192.168.1.0/24  |  10.0.0.1-10.0.0.255",
                    id="wl-input",
                    classes="wl-input"
                )
                yield Button("Agregar", id="wl-add", variant="primary", classes="wl-add-btn")

        with ScrollableContainer(id="wl-container"):
            pass

    def on_mount(self):
        self.refresh_list()

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
            self.notify("Escribe una IP, CIDR o rango", severity="warning")
            return
        if not is_valid_whitelist_entry(entry):
            self.notify(
                "Formato invalido.\n"
                "  IP:  192.168.1.100\n"
                "  CIDR: 192.168.1.0/24\n"
                "  Rango: 10.0.0.1-10.0.0.255",
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
        count = len(load_whitelist())
        self.app.call_from_thread(
            self.app.notify,
            f"Firewall actualizado ({count} IPs en lista blanca)"
        )

    def refresh_list(self):
        container = self.query_one("#wl-container", ScrollableContainer)
        container.remove_children()
        whitelist = load_whitelist()
        if not whitelist:
            container.mount(Label("  No hay IPs en la lista blanca", classes="wl-empty"))
            return
        for ip in whitelist:
            container.mount(IPRow(ip))
