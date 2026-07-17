import re

from textual.containers import Horizontal
from textual.widgets import Label, Button, Switch


def safe_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


class AppRow(Horizontal):
    def __init__(self, app_name: str, app_data: dict):
        super().__init__()
        self.app_name = app_name
        self.app_data = app_data
        sid = safe_id(app_name)

        self._switch_id = f"app-switch-{sid}"
        self._modify_id = f"app-modify-{sid}"
        self._delete_id = f"app-delete-{sid}"

    def compose(self):
        yield Label(self.app_name, classes="app-row-name")

        domains = ", ".join(self.app_data.get("domains", []))
        yield Label(domains, classes="app-row-domains")

        with Horizontal(classes="app-row-actions"):
            yield Switch(
                value=self.app_data.get("blocked", False),
                id=self._switch_id,
                classes="app-row-switch"
            )
            yield Button("Modificar", id=self._modify_id, classes="app-row-btn")
            yield Button("Eliminar", variant="error", id=self._delete_id, classes="app-row-btn")
