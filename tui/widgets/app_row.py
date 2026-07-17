from textual.containers import Horizontal
from textual.widgets import Label, Button, Switch


class AppRow(Horizontal):
    def __init__(self, app_name: str, app_data: dict):
        super().__init__()
        self.app_name = app_name
        self.app_data = app_data

    def compose(self):
        yield Label(self.app_name, classes="app-row-name")

        domains = ", ".join(self.app_data.get("domains", []))
        yield Label(domains, classes="app-row-domains")

        with Horizontal(classes="app-row-actions"):
            yield Switch(
                value=self.app_data.get("blocked", False),
                id=f"app-switch-{self.app_name}",
                classes="app-row-switch"
            )
            yield Button("Modificar", id=f"app-modify-{self.app_name}", classes="app-row-btn")
            yield Button("Eliminar", variant="error", id=f"app-delete-{self.app_name}", classes="app-row-btn")
