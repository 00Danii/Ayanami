"""
Modal para elegir la ruta de un archivo.

Muestra un Input con la ruta completa (editable) y un árbol de directorios
(`DirectoryTree`) para navegar:

- Al seleccionar una **carpeta** se re-enraiza el árbol y se actualiza el
  directorio del Input (conservando el nombre de archivo si ya había uno).
- Al seleccionar un **archivo** se completa la ruta en el Input.
- El botón **⬆ Subir** (o la tecla `b`) sube un nivel en el árbol.
- `Escape` cierra el modal con `dismiss(None)`.
- "Aceptar" cierra con `dismiss(path)`; "Cancelar" con `dismiss(None)`.
"""
import os

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Input, Label


class PathPicker(Screen):
    """Selector de rutas por navegación visual o escritura directa."""

    DEFAULT_CSS = """
    PathPicker {
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "cancelar", "Cancelar"),
        ("b", "subir", "Subir un nivel"),
    ]

    def __init__(self, title: str, default_path: str, confirm_text: str = "Aceptar"):
        super().__init__()
        self.title_text = title
        self.default_path = default_path or os.path.expanduser("~")
        self.confirm_text = confirm_text

    def _start_dir(self) -> str:
        """Directorio raíz inicial del árbol."""
        path = self.default_path
        if os.path.isdir(path):
            return path
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            return parent
        home = os.path.expanduser("~")
        return home if os.path.isdir(home) else "/"

    def compose(self):
        with Vertical(id="path-picker"):
            yield Label(self.title_text, classes="modal-title")
            yield Label("Ruta", classes="modal-label")
            yield Input(value=self.default_path, id="pp-path")
            yield Label("Navegá el árbol para cambiar de carpeta", classes="modal-label")
            yield DirectoryTree(path=self._start_dir(), id="pp-tree")
            with Horizontal(classes="modal-buttons"):
                yield Button("⬆ Subir", id="pp-up", variant="default")
                yield Button(self.confirm_text, id="pp-ok", variant="success")
                yield Button("Cancelar", id="pp-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "pp-up":
            self.action_subir()
        elif event.button.id == "pp-ok":
            path = self.query_one("#pp-path", Input).value.strip()
            self.dismiss(path if path else None)
        elif event.button.id == "pp-cancel":
            self.dismiss(None)

    def action_cancelar(self):
        self.dismiss(None)

    def action_subir(self):
        tree = self.query_one("#pp-tree", DirectoryTree)
        current = tree.path
        if current is None:
            return
        parent = current.parent
        if parent is None or parent == current:
            self.notify("Ya estás en el directorio raíz", severity="warning")
            return
        self._set_tree_dir(str(parent))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        """Seleccionaste una carpeta → navega y actualiza la ruta."""
        self._set_tree_dir(str(event.path))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        """Seleccionaste un archivo → completa la ruta exacta."""
        self.query_one("#pp-path", Input).value = str(event.path)

    def _set_tree_dir(self, dir_path: str):
        """Re-enraiza el árbol en dir_path y actualiza el directorio del Input,
        conservando el nombre de archivo si ya había uno escrito."""
        tree = self.query_one("#pp-tree", DirectoryTree)
        try:
            tree.path = dir_path
        except Exception:
            return

        inp = self.query_one("#pp-path", Input)
        base = dir_path if dir_path.endswith(os.sep) else dir_path + os.sep
        current = inp.value
        filename = os.path.basename(current) if current and not current.endswith(os.sep) else ""
        inp.value = base + filename
        inp.cursor_position = len(inp.value)