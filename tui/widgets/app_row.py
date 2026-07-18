import re

from textual.containers import Horizontal, Vertical
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
        blocked = self.app_data.get("blocked", False)
        accent_cls = "app-accent-blocked" if blocked else "app-accent-unblocked"
        yield Label("", classes=f"app-accent {accent_cls}")

        with Vertical(classes="app-row-body"):
            yield Label(self.app_name, classes="app-row-name")

            with Horizontal(classes="app-row-sub"):
                domains = self.app_data.get("domains", [])
                yield Label(f"{len(domains)} dominios", classes="app-row-badge")

                status_cls = "tag-blocked" if blocked else "tag-unblocked"
                status_text = "BLOQUEADA" if blocked else "DESBLOQUEADA"
                yield Label(status_text, classes=f"app-row-tag {status_cls}")

                domains_str = ", ".join(domains)
                yield Label(domains_str if domains_str else "Sin dominios", classes="app-row-domains")

        with Horizontal(classes="app-row-actions"):
            yield Switch(value=blocked, id=self._switch_id, classes="app-row-switch")
            yield Button("Modificar", id=self._modify_id, classes="app-row-btn")
            yield Button("Eliminar", variant="error", id=self._delete_id, classes="app-row-btn")
