from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, TextArea, Switch, Button


DOMAIN_RE = r"^([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"


class AppModal(Screen):
    DEFAULT_CSS = """
    AppModal {
        align: center middle;
    }
    """

    def __init__(self, app_data: dict | None = None, existing_names: set | None = None):
        super().__init__()
        self.app_data = app_data or {}
        self.existing_names = existing_names or set()

    def compose(self):
        title = "Modificar App" if self.app_data else "Registrar App"
        name_val = self.app_data.get("name", "")
        domains_val = "\n".join(self.app_data.get("domains", []))
        blocked_val = self.app_data.get("blocked", True)

        with Vertical(id="app-modal"):
            yield Label(title, classes="modal-title")

            yield Label("Nombre", classes="modal-label")
            yield Input(value=name_val, placeholder="Ej: tiktok", id="modal-name")

            yield Label("Dominios (uno por línea)", classes="modal-label")
            yield TextArea(domains_val, id="modal-domains", classes="modal-textarea")

            with Horizontal(classes="modal-switch-row"):
                yield Label("Bloqueada", classes="modal-label")
                yield Switch(value=blocked_val, id="modal-blocked")

            with Horizontal(classes="modal-buttons"):
                yield Button("Guardar", id="modal-save", variant="success")
                yield Button("Cancelar", id="modal-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "modal-cancel":
            self.app.pop_screen()
        elif event.button.id == "modal-save":
            self.save_app()

    def save_app(self):
        name = self.query_one("#modal-name", Input).value.strip()
        domains_text = self.query_one("#modal-domains", TextArea).text.strip()
        blocked = self.query_one("#modal-blocked", Switch).value

        if not name:
            self.notify("El nombre es obligatorio", severity="error")
            return

        original_name = self.app_data.get("name")
        if name != original_name and name in self.existing_names:
            self.notify(f"La app '{name}' ya existe", severity="error")
            return

        domains = [d.strip() for d in domains_text.splitlines() if d.strip()]

        if not domains:
            self.notify("Ingresa al menos un dominio", severity="error")
            return

        import re
        invalid = []
        for d in domains:
            if not re.match(DOMAIN_RE, d):
                invalid.append(d)

        if invalid:
            self.notify(
                f"Dominios inválidos: {', '.join(invalid)}",
                severity="error"
            )
            return

        self.dismiss({
            "name": name,
            "domains": domains,
            "blocked": blocked,
        })
