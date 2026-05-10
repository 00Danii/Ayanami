from textual.containers import Horizontal
from textual.widgets import Label, Button


class InterfaceRow(Horizontal):

    def __init__(self, iface_data: dict):
        super().__init__()
        self.iface_data = iface_data
        self.iface = iface_data["iface"]

    def compose(self):
        yield Label(
            self.iface,
            classes="iface-name"
        )
        
        yield Label(
            self.iface_data["type"],
            classes="iface-type"
        )
        
        yield Label(
            self.iface_data["state"],
            classes="iface-state"
        )

        with Horizontal(classes="iface-actions"):
            yield Button(
                "Global",
                variant="success",
                id=f"global-{self.iface}",
                classes="iface-btn"
            )
            
            yield Button(
                "X",
                variant="error",
                id=f"disconnect-{self.iface}",
                classes="iface-btn"
            )