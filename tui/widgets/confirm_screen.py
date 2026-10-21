from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button


class ConfirmScreen(Screen):
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    """

    def __init__(self, message: str, confirm_text: str = "Eliminar",
                 confirm_variant: str = "error"):
        super().__init__()
        self.message = message
        self.confirm_text = confirm_text
        self.confirm_variant = confirm_variant

    def compose(self):
        with Vertical(id="confirm-modal"):
            yield Label(self.message, id="confirm-message")
            with Horizontal(classes="confirm-buttons"):
                yield Button(
                    self.confirm_text,
                    id="confirm-yes",
                    variant=self.confirm_variant,
                )
                yield Button("Cancelar", id="confirm-no", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)
