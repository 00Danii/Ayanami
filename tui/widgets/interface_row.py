from textual.containers import Horizontal
from textual.widgets import Label

from widgets.clickable_label import ClickableLabel


class InterfaceRow(Horizontal):

    def __init__(self, iface_data: dict):
        super().__init__()
        self.iface_data = iface_data
        self.iface = iface_data["iface"]

    def compose(self):
        state = self.iface_data["state"]
        iface_type = self.iface_data["type"]

        yield Label(self.iface, classes="iface-name")

        type_icon = {"wifi": "◈", "ethernet": "┃"}.get(iface_type, "◇")
        yield Label(f"{type_icon}  {iface_type}", classes="iface-type")

        dot = "●"
        state_color = "iface-state-up" if state in ("connected", "conectado") else "iface-state-down"
        yield Label(f"{dot}  {state}", classes=f"iface-state {state_color}")

        with Horizontal(classes="iface-actions"):
            yield ClickableLabel(
                "[Establecer como interfaz LAN]",
                id=f"global-{self.iface}",
                classes="iface-btn iface-global",
                markup=False,
            )
            yield ClickableLabel(
                "[Desconectar]",
                id=f"disconnect-{self.iface}",
                classes="iface-btn iface-disconnect",
                markup=False,
            )
