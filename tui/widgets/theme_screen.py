from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Static


THEMES = [
    {"id": "midnight", "name": "Medianoche", "colors": "$primary, $accent, $background"},
    {"id": "dark", "name": "Oscuro", "colors": "$primary, $accent, $background"},
    {"id": "light", "name": "Claro", "colors": "$primary, $accent, $background"},
]


class ThemeScreen(Screen):
    def compose(self):
        with Vertical(id="theme-modal"):
            yield Static("[bold $primary]Temas[/]", classes="theme-title")
            for theme in THEMES:
                with Horizontal(id=f"theme-{theme['id']}", classes="theme-item"):
                    yield Static(f"{theme['name']}", classes="theme-name")
            with Horizontal(classes="theme-close"):
                yield Button("Cerrar", id="theme-close", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "theme-close":
            self.dismiss()

    def on_click(self, event):
        widget = event.widget
        while widget is not None:
            if hasattr(widget, "id") and widget.id and str(widget.id).startswith("theme-"):
                self.dismiss(str(widget.id).replace("theme-", ""))
                return
            widget = getattr(widget, "parent", None)
