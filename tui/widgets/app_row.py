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

        # Se llenan en compose(); update_state() los usa para pintar el estado.
        self._accent = None
        self._status = None

    def compose(self):
        blocked = self.app_data.get("blocked", False)
        accent_cls = "app-accent-blocked" if blocked else "app-accent-unblocked"
        self._accent = Label("", classes=f"app-accent {accent_cls}")
        yield self._accent

        app_type = self.app_data.get("type", "Videojuegos")
        type_cls = f"app-type-tag app-type-{safe_id(app_type.lower())}"

        with Vertical(classes="app-row-body"):
            yield Label(self.app_name, classes="app-row-name")

            with Horizontal(classes="app-row-sub"):
                domains = self.app_data.get("domains", [])
                yield Label(f"{len(domains)} dominios", classes="app-row-badge")

                yield Label(app_type, classes=type_cls)

                status_cls = "tag-blocked" if blocked else "tag-unblocked"
                status_text = "BLOQUEADA" if blocked else "DESBLOQUEADA"
                self._status = Label(status_text, classes=f"app-row-tag {status_cls}")
                yield self._status

                domains_str = ", ".join(domains)
                yield Label(domains_str if domains_str else "Sin dominios", classes="app-row-domains")

        with Horizontal(classes="app-row-actions"):
            yield Switch(value=blocked, id=self._switch_id, classes="app-row-switch")
            yield Button("Modificar", id=self._modify_id, classes="app-row-btn")
            yield Button("Eliminar", variant="error", id=self._delete_id, classes="app-row-btn")

    def update_state(self, blocked: bool):
        """Pinta el nuevo estado sin recrear la fila (mucho más barato)."""
        self.app_data["blocked"] = blocked

        if self._accent is None or self._status is None:
            return  # compose() todavía no corrió

        self._accent.set_class(blocked, "app-accent-blocked")
        self._accent.set_class(not blocked, "app-accent-unblocked")

        self._status.update("BLOQUEADA" if blocked else "DESBLOQUEADA")
        self._status.set_class(blocked, "tag-blocked")
        self._status.set_class(not blocked, "tag-unblocked")
