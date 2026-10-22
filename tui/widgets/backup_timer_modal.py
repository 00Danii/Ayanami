"""Editor de la programación del timer de backups de systemd."""

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Select, Switch


PRESETS = [
    ("Mensual (día 1, 00:00)", "monthly"),
    ("Semanal (lunes, 00:00)", "weekly"),
    ("Diaria (00:00)", "daily"),
]

SIMPLE_CALENDARS = {value for _, value in PRESETS}


class BackupTimerModal(Screen):
    """Permite elegir la frecuencia y `Persistent` del timer."""

    DEFAULT_CSS = """
    BackupTimerModal {
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "cancelar", "Cancelar"),
    ]

    def __init__(self, calendar: str = "monthly", persistent: bool = True):
        super().__init__()
        self.calendar = calendar or "monthly"
        self.persistent = persistent

    def compose(self):
        current = self.calendar if self.calendar in SIMPLE_CALENDARS else "monthly"

        with Vertical(id="backup-timer-modal"):
            yield Label("Configuración del timer", classes="modal-title")

            yield Label("Frecuencia", classes="modal-label")
            yield Select(
                PRESETS,
                value=current,
                allow_blank=False,
                id="btm-preset",
            )

            if self.calendar not in SIMPLE_CALENDARS:
                yield Label(
                    "La programación actual no es una frecuencia estándar. "
                    "Al guardar se reemplazará por la opción elegida.",
                    classes="btm-help",
                )

            with Horizontal(classes="modal-switch-row"):
                yield Label(
                    "Persistencia (ejecutar si se perdió el horario)",
                    classes="modal-label",
                )
                yield Switch(value=self.persistent, id="btm-persistent")

            with Horizontal(classes="modal-buttons"):
                yield Button("Guardar", id="btm-save", variant="success")
                yield Button("Cancelar", id="btm-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btm-cancel":
            self.dismiss(None)
        elif event.button.id == "btm-save":
            self.save()

    def action_cancelar(self):
        self.dismiss(None)

    def save(self):
        calendar = self.query_one("#btm-preset", Select).value
        persistent = self.query_one("#btm-persistent", Switch).value

        if calendar not in SIMPLE_CALENDARS:
            self.notify("Elegir una frecuencia válida", severity="error")
            return

        self.dismiss({
            "calendar": calendar,
            "persistent": persistent,
        })
