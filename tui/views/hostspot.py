from textual.containers import (
    Vertical,
    Horizontal
)

from textual.widgets import (
    Label,
    Button,
    Input,
    RichLog,
    Static
)

import subprocess


class HotspotView(Vertical):

    def compose(self):
        # HEADER
        yield Label(
            "Crear punto de acceso inalámbrico",
            classes="help-text"
        )

        # FORM
        with Vertical(classes="hotspot-card"):
            # SSID
            with Horizontal(classes="input-row"):
                yield Label(
                    "SSID",
                    classes="input-label"
                )
                yield Input(
                    placeholder="Nombre de la red",
                    id="hotspot-ssid",
                    classes="hotspot-input"
                )

            # PASSWORD
            with Horizontal(classes="input-row"):
                yield Label(
                    "PASSWORD",
                    classes="input-label"
                )
                yield Input(
                    placeholder="Mínimo 8 caracteres",
                    password=True,
                    id="hotspot-password",
                    classes="hotspot-input"
                )

            # BUTTONS
            with Horizontal(classes="hotspot-buttons"):
                yield Button(
                    "CREAR HOTSPOT",
                    variant="success",
                    id="btn-create-hotspot",
                    classes="hotspot-btn"
                )

                yield Button(
                    "MOSTRAR CONTRASEÑA",
                    id="btn-show-password",
                    classes="hotspot-btn"
                )

        # PANEL DE LOGS
        with Vertical(classes="log-card"):
            yield Static(
                "STATUS",
                classes="log-title"
            )

            yield RichLog(
                id="hotspot-log",
                markup=True,
                highlight=True
            )

    # EVENTOS DE BOTONES
    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == "btn-create-hotspot":
            self.create_hotspot()
        elif event.button.id == "btn-show-password":
            self.show_hotspot_password()

    # FUNCIONES AUXILIARES
    def write_log(self, text: str):
        self.query_one(
            "#hotspot-log",
            RichLog
        ).write(text)
    
    # ACCIONES DE BOTONES
    def create_hotspot(self):
        ssid = self.query_one(
            "#hotspot-ssid",
            Input
        ).value.strip()

        password = self.query_one(
            "#hotspot-password",
            Input
        ).value.strip()

        if not ssid:
            self.write_log(
                "[red]SSID requerido[/]"
            )
            return

        if len(password) < 8:
            self.write_log(
                "[red]Password mínimo 8 caracteres[/]"
            )
            return

        iface = getattr(
            self.app,
            "selected_interface",
            None
        )

        if not iface:
            self.write_log(
                "[red]No hay interfaz seleccionada[/]"
            )
            return

        self.write_log(
            f"[yellow]➜ Iniciando hotspot en {iface}[/]"
        )

        cmd = (
            f"nmcli dev wifi hotspot "
            f"ifname {iface} "
            f"ssid '{ssid}' "
            f"password '{password}'"
        )

        try:
            subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            self.write_log(
                f"[green]Hotspot creado[/]"
            )

            self.write_log(
                f"[cyan]SSID:[/] {ssid}"
            )
            
            self.write_log(
              f"[cyan]PASS:[/] {password}"
            )

            self.write_log(
                f"[cyan]Interface:[/] {iface}"
            )
            
            self.notify(f"HostSpot {ssid} creado")

        except subprocess.CalledProcessError:
            self.write_log(
                "[red]Error al crear hotspot[/]"
            )

    def show_hotspot_password(self):
        try:
            result = subprocess.check_output(
                "nmcli dev wifi show-password",
                shell=True
            ).decode()

            self.write_log(
                f"[green]{result}[/]"
            )

        except:
            self.write_log(
                "[red]No se pudo obtener password[/]"
            )