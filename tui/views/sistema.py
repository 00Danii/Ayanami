from textual.containers import Vertical
from textual.widgets import Label


class SistemaView(Vertical):

    def compose(self):
        yield Vertical(
            Label("Sistema", classes="section-title"),
            id="sistema-container"
        )
