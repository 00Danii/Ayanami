from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Static


THEMES = [
    {"id": "dark", "name": "Oscuro", "colors": "#1a1b26, #7aa2f7, #ff007c"},
    {"id": "light", "name": "Claro", "colors": "#ffffff, #1a1b26, #ff007c"},
    {"id": "midnight", "name": "Medianoche", "colors": "#0d1117, #58a6ff, #f78166"},
]


class ThemeScreen(Screen):
    def compose(self):
        with Vertical(id="theme-modal"):
            yield Static("[bold #7aa2f7]Temas[/]", classes="theme-title")
            for theme in THEMES:
                with Horizontal(id=f"theme-{theme['id']}", classes="theme-item"):
                    yield Static(f"{theme['name']}", classes="theme-name")
            with Horizontal(classes="theme-close"):
                yield Button("Cerrar", id="theme-close", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "theme-close":
            self.dismiss()

    def on_click(self, event):
        if hasattr(event, "widget") and hasattr(event.widget, "id"):
            theme_id = event.widget.id
            if theme_id.startswith("theme-"):
                self.dismiss(theme_id.replace("theme-", ""))
