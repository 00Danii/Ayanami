from textual.containers import Vertical
from textual.widgets import Label


class RulesTab(Vertical):
    def compose(self):
        yield Label("Gestión de reglas iptables", id="fw-rules-placeholder")
