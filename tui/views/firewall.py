from textual.containers import Vertical
from textual.widgets import Label


class FirewallView(Vertical):
    def compose(self):
        yield Label(
            "Gestión de Firewall",
            classes="title"
        )
