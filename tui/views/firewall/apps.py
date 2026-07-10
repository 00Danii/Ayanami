from textual.containers import Vertical
from textual.widgets import Label


class AppsTab(Vertical):
    def compose(self):
        yield Label("Gestión de aplicaciones", id="fw-apps-placeholder")
