import json
import os
from pathlib import Path

from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Switch, Input, Select

from views.firewall.app_modal import AppModal
from widgets.app_row import AppRow
from widgets.confirm_screen import ConfirmScreen
from firewall_ops import block_app, unblock_app


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
        elif btn_id and (btn_id.startswith("app-modify-") or btn_id.startswith("app-delete-")):
            node = event.button
            while node is not None:
                if isinstance(node, AppRow):
                    app_name = node.app_name
                    break
                node = node.parent
            else:
                return

            if btn_id.startswith("app-modify-"):
                self.modify_app(app_name)
            else:
                self.delete_app(app_name)

    def on_switch_changed(self, event: Switch.Changed):
        switch_id = event.switch.id
        if switch_id and switch_id.startswith("app-switch-"):
            node = event.switch
            while node is not None:
                if isinstance(node, AppRow):
                    app_name = node.app_name
                    break
                node = node.parent
            else:
                return

            data = self.load_apps()
            app_data = data.get(app_name)
            if not app_data:
                return

            blocked = event.value
            app_data["blocked"] = blocked
            self.save_apps(data)

            domains = app_data.get("domains", [])
            try:
                if blocked:
                    block_app(app_name, domains)
                else:
                    unblock_app(app_name, domains)
            except Exception as e:
                self.notify(f"Error al {'bloquear' if blocked else 'desbloquear'}: {e}", severity="error")
                return

            status = "bloqueada" if blocked else "desbloqueada"
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
            old_blocked = data[app_name].get("blocked", False)
            old_domains = data[app_name].get("domains", [])
            new_blocked = result["blocked"]
            new_domains = result["domains"]
            new_name = result["name"]

            data.pop(app_name, None)
            data[new_name] = {
                "domains": new_domains,
                "blocked": new_blocked,
            }
            self.save_apps(data)
            self.refresh_apps()

            try:
                if new_blocked:
                    if old_blocked and set(old_domains) != set(new_domains):
                        unblock_app(app_name, old_domains)
                    block_app(new_name, new_domains)
                elif old_blocked:
                    unblock_app(app_name, old_domains)
            except Exception as e:
                self.notify(f"Error al aplicar cambios: {e}", severity="error")
                return

            self.notify(f"App '{new_name}' modificada")

        existing = set(self.load_apps().keys())
        self.app.push_screen(
            AppModal(app_data={"name": app_name, **app_data}, existing_names=existing),
            on_save
        )

    def delete_app(self, app_name: str):
        data = self.load_apps()
        app_data = data.get(app_name)
        if not app_data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return

        def on_confirm(confirmed):
            if not confirmed:
                return
            data = self.load_apps()
            app_data = data.pop(app_name, None)
            self.save_apps(data)
            self.refresh_apps()

            if app_data and app_data.get("blocked"):
                try:
                    unblock_app(app_name, app_data.get("domains", []))
                except Exception as e:
                    self.notify(f"Error al desbloquear: {e}", severity="error")
                    return

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

            if result["blocked"]:
                try:
                    block_app(result["name"], result["domains"])
                except Exception as e:
                    self.notify(f"Error al bloquear: {e}", severity="error")
                    return

            self.notify(f"App '{result['name']}' registrada")

        existing = set(self.load_apps().keys())
        self.app.push_screen(AppModal(existing_names=existing), on_save)
