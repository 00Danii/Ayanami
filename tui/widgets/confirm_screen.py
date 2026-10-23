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
                 switch_label: str | None = None,
                 switches: list[dict] | None = None):
        super().__init__()
        self.message = message
        self.confirm_text = confirm_text
        self.confirm_variant = confirm_variant
        self.switch_label = switch_label
        self.switches = switches or []

    def compose(self):
        with Vertical(id="confirm-modal"):
            yield Label(self.message, id="confirm-message")
            if self.switch_label and not self.switches:
                with Horizontal(
                    id="confirm-switch-row",
                    classes="modal-switch-row",
                ):
                    yield Label(self.switch_label, classes="modal-label")
                    yield Switch(value=False, id="confirm-switch")
            for idx, sw in enumerate(self.switches):
                label = sw.get("label") or ""
                default = bool(sw.get("default", False))
                key = sw.get("key") or f"switch_{idx}"
                with Horizontal(
                    id=f"confirm-switch-row-{idx}",
                    classes="modal-switch-row",
                ):
                    yield Label(label, classes="modal-label")
                    yield Switch(value=default, id=f"confirm-switch-{key}")
            with Horizontal(classes="confirm-buttons"):
                yield Button(
                    self.confirm_text,
                    id="confirm-yes",
                    variant=self.confirm_variant,
                )
                yield Button("Cancelar", id="confirm-no", variant="default")

    def on_mount(self):
        if self.switch_label or self.switches:
            try:
                self.query_one("#confirm-yes", Button).focus()
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed):
        confirmed = event.button.id == "confirm-yes"
        if self.switches:
            selections = {}
            for idx, sw in enumerate(self.switches):
                key = sw.get("key") or f"switch_{idx}"
                try:
                    switch = self.query_one(f"#confirm-switch-{key}", Switch)
                    selections[key] = bool(switch.value)
                except Exception:
                    selections[key] = bool(sw.get("default", False))
            self.dismiss({"confirmed": confirmed, "selections": selections})
            return
        if self.switch_label:
            try:
                switch = self.query_one("#confirm-switch", Switch)
                self.dismiss((confirmed, switch.value))
            except Exception:
                self.dismiss(confirmed)
            return
        self.dismiss(confirmed)
