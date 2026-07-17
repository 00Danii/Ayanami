import json
import os
from pathlib import Path

from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Switch, Input, Select

from views.firewall.app_modal import AppModal
from widgets.app_row import AppRow
from widgets.confirm_screen import ConfirmScreen


APPS_FILE = str(Path(__file__).resolve().parent.parent.parent.parent / "apps_firewall.json")


class AppsTab(Vertical):
    def compose(self):
        with Horizontal(classes="fw-apps-toolbar"):
            yield Input(placeholder="Buscar app...", id="apps-search")
            yield Select(
                [("Todas", "all"), ("Bloqueadas", "blocked"), ("Desbloqueadas", "unblocked")],
                id="apps-filter",
                value="all",
                prompt="Filtrar"
            )
            yield Select(
                [("Nombre (A-Z)", "name-asc"), ("Nombre (Z-A)", "name-desc")],
                id="apps-sort",
                value="name-asc",
                prompt="Ordenar"
            )
            yield Button("Registrar", id="apps-register", variant="primary")

        yield Vertical(id="apps-container")

    def on_mount(self):
        self.refresh_apps()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "apps-search":
            self.refresh_apps()

    def on_select_changed(self, event: Select.Changed):
        if event.select.id in ("apps-filter", "apps-sort"):
            self.refresh_apps()

    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id
        if btn_id == "apps-register":
            self.register_app()
        elif btn_id and btn_id.startswith("app-modify-"):
            app_name = btn_id.removeprefix("app-modify-")
            self.modify_app(app_name)
        elif btn_id and btn_id.startswith("app-delete-"):
            app_name = btn_id.removeprefix("app-delete-")
            self.delete_app(app_name)

    def on_switch_changed(self, event: Switch.Changed):
        switch_id = event.switch.id
        if switch_id and switch_id.startswith("app-switch-"):
            app_name = switch_id.removeprefix("app-switch-")
            data = self.load_apps()
            if app_name not in data:
                return
            data[app_name]["blocked"] = event.value
            self.save_apps(data)
            status = "bloqueada" if event.value else "desbloqueada"
            self.notify(f"App '{app_name}' {status}")

    def load_apps(self) -> dict:
        if not os.path.exists(APPS_FILE):
            return {}
        try:
            with open(APPS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save_apps(self, data: dict):
        with open(APPS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def refresh_apps(self):
        container = self.query_one("#apps-container", Vertical)
        container.remove_children()

        data = self.load_apps()
        search = self.query_one("#apps-search", Input).value.lower()
        filter_opt = self.query_one("#apps-filter", Select).value
        sort_opt = self.query_one("#apps-sort", Select).value

        items = list(data.items())

        if search:
            items = [
                (n, d) for n, d in items
                if search in n.lower()
                or any(search in dom.lower() for dom in d.get("domains", []))
            ]

        if filter_opt == "blocked":
            items = [(n, d) for n, d in items if d.get("blocked")]
        elif filter_opt == "unblocked":
            items = [(n, d) for n, d in items if not d.get("blocked")]

        reverse = False
        if sort_opt == "name-desc":
            reverse = True
        items.sort(key=lambda x: x[0].lower(), reverse=reverse)

        for name, info in items:
            container.mount(AppRow(name, info))

    def modify_app(self, app_name: str):
        data = self.load_apps()
        app_data = data.get(app_name)
        if not app_data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return

        def on_save(result):
            if not result:
                return
            data = self.load_apps()
            data.pop(app_name, None)
            data[result["name"]] = {
                "domains": result["domains"],
                "blocked": result["blocked"],
            }
            self.save_apps(data)
            self.refresh_apps()
            self.notify(f"App '{result['name']}' modificada")

        existing = set(self.load_apps().keys())
        self.app.push_screen(
            AppModal(app_data={"name": app_name, **app_data}, existing_names=existing),
            on_save
        )

    def delete_app(self, app_name: str):
        data = self.load_apps()
        if app_name not in data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return

        def on_confirm(confirmed):
            if not confirmed:
                return
            data = self.load_apps()
            data.pop(app_name)
            self.save_apps(data)
            self.refresh_apps()
            self.notify(f"App '{app_name}' eliminada")

        self.app.push_screen(
            ConfirmScreen(f"Eliminar app '{app_name}'?"),
            on_confirm
        )

    def register_app(self):
        def on_save(result):
            if not result:
                return
            data = self.load_apps()
            data[result["name"]] = {
                "domains": result["domains"],
                "blocked": result["blocked"],
            }
            self.save_apps(data)
            self.refresh_apps()
            self.notify(f"App '{result['name']}' registrada")

        existing = set(self.load_apps().keys())
        self.app.push_screen(AppModal(existing_names=existing), on_save)
