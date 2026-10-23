from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Switch


class ConfirmScreen(Screen):
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    """

    def __init__(self, message: str, confirm_text: str = "Eliminar",
                 confirm_variant: str = "error",
                 switch_label: str | None = None):
        super().__init__()
        self.message = message
        self.confirm_text = confirm_text
        self.confirm_variant = confirm_variant
        self.switch_label = switch_label

    def compose(self):
        with Vertical(id="confirm-modal"):
            yield Label(self.message, id="confirm-message")
            if self.switch_label:
                with Horizontal(
                    id="confirm-switch-row",
                    classes="modal-switch-row",
                ):
                    yield Label(self.switch_label, classes="modal-label")
                    yield Switch(value=False, id="confirm-switch")
            with Horizontal(classes="confirm-buttons"):
                yield Button(
                    self.confirm_text,
                    id="confirm-yes",
                    variant=self.confirm_variant,
                )
                yield Button("Cancelar", id="confirm-no", variant="default")

    def on_mount(self):
        # El switch se monta antes que los botones. Mantener el foco en la
        # acción principal evita que Enter/Espacio active el switch por error.
        if self.switch_label:
            self.query_one("#confirm-yes", Button).focus()

    def on_button_pressed(self, event: Button.Pressed):
        confirmed = event.button.id == "confirm-yes"
        if self.switch_label:
            switch = self.query_one("#confirm-switch", Switch)
            self.dismiss((confirmed, switch.value))
        else:
            self.dismiss(confirmed)
