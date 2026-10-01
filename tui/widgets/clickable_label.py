"""Un `Label` que se usa como botón.

Un `Button` de Textual ocupa 3 celdas de alto y dibuja bordes, así que en
un pie de página ocupa más espacio del que necesita. Para acciones
secundarias ("Cargar más", "Ver más") alcanza con un texto que responda al
clic y al Enter: mucho más chico y se lee como un enlace.

Textual entrega los eventos de mouse al widget que está bajo el cursor, así
que un `Static` recibe `Click` sin más. Con `can_focus = True` además se
puede llegar con Tab y activar con Enter o espacio, que es lo que hace
accesible un control.
"""

from textual.events import Click, Key
from textual.message import Message
from textual.widgets import Static


class ClickableLabel(Static):
    can_focus = True

    class Pressed(Message):
        """Se emite cuando el usuario activa el label (clic, Enter o espacio)."""

        def __init__(self, label: "ClickableLabel") -> None:
            super().__init__()
            self.label = label

    def on_click(self, event: Click) -> None:
        event.stop()
        self.post_message(self.Pressed(self))

    def on_key(self, event: Key) -> None:
        if event.key in ("enter", "space"):
            event.stop()
            self.post_message(self.Pressed(self))
