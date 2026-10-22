"""Editor de ``dnsmasq.conf`` con resaltado de sintaxis.

Textual resalta sus ``TextArea`` con tree-sitter, pero no incluye una gramática
de dnsmasq. Para no añadir dependencias ni fingir que el archivo es bash/ini,
usamos Pygments (ya es dependencia del proyecto) y traducimos sus tokens al
mapa interno de resaltados del ``TextArea``.
"""

from bisect import bisect_right

from pygments.lexer import RegexLexer, bygroups
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    String,
    Text,
    Whitespace,
)
from rich.style import Style
from textual.widgets import TextArea
from textual.widgets.text_area import TextAreaTheme


_TOKEN_STYLES = (
    (Comment, "comment"),
    (Name.Builtin, "type"),
    (Keyword, "keyword"),
    (Name, "keyword"),
    (String, "string"),
    (Number, "number"),
    (Operator, "operator"),
)

_THEME = TextAreaTheme(
    "ayanami_dnsmasq",
    syntax_styles={
        "comment": Style(color="#565f89", italic=True),
        "keyword": Style(color="#7aa2f7", bold=True),
        "type": Style(color="#bb9af7", bold=True),
        "operator": Style(color="#89ddff"),
        "string": Style(color="#9ece6a"),
        "number": Style(color="#ff9e64"),
    },
)


class DnsmasqLexer(RegexLexer):
    """Lexer mínimo para la sintaxis de ``dnsmasq.conf``.

    ``IniLexer`` interpreta cualquier ``#`` como comentario, pero dnsmasq usa
    ``IP#puerto`` (por ejemplo ``server=8.8.8.8#5353``). Este lexer separa
    comentarios, claves, valores, IPs/MACs/duraciones y opciones con nombre.
    """

    name = "dnsmasq"
    aliases = ["dnsmasq"]
    filenames = ["dnsmasq.conf"]

    tokens = {
        "root": [
            (r"^[ \t]*#[^\n]*", Comment.Single),
            (
                r"^([ \t]*)([A-Za-z0-9][\w-]*)([ \t]*)(=)([ \t]*)",
                bygroups(
                    Whitespace,
                    Name.Attribute,
                    Whitespace,
                    Operator,
                    Whitespace,
                ),
                "value",
            ),
            (
                r"^([ \t]*)([A-Za-z0-9][\w-]*)(?=[ \t]*(?:#|\n|$))",
                bygroups(Whitespace, Name.Attribute),
            ),
            (r"[ \t]+#[^\n]*", Comment.Single),
            (r"\n", Whitespace),
            (r"[ \t]+", Whitespace),
            (r".", Text),
        ],
        "value": [
            (r"[ \t]+#[^\n]*", Comment.Single),
            (r"/(?:[^/\n]*/)+", String),
            (r"#[0-9]+", Number.Integer),
            (r"(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?", Number),
            (r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", Number.Hex),
            (r"\d+(?:[smhdw])?", Number),
            (r"option:[A-Za-z0-9_-]+", Name.Builtin),
            (r"[^,\s#]+", String),
            (r",", Operator),
            (r"[ \t]+", Whitespace),
            (r"#[^\n]*", Comment.Single),
            (r"\n", Whitespace, "#pop"),
            (r".", String),
        ],
    }


class DnsmasqTextArea(TextArea):
    """``TextArea`` con resaltado para el formato clave=valor de dnsmasq."""

    _lexer = DnsmasqLexer()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_theme(_THEME)
        self.theme = _THEME.name

    def _build_highlight_map(self) -> None:
        """Traduce tokens de Pygments a los resaltados internos del TextArea.

        El ``TextArea`` espera posiciones en bytes y nombres de estilo de su
        tema. Pygments devuelve posiciones de caracteres sobre el texto
        original, así que convertimos línea/columna y luego a UTF-8.
        """
        self._line_cache.clear()
        highlights = self._highlights
        highlights.clear()

        text = self.document.text
        if not text:
            return

        lines = text.split("\n")
        line_starts = [0]
        for line in lines[:-1]:
            line_starts.append(line_starts[-1] + len(line) + 1)

        # get_tokens_unprocessed conserva los índices del texto original;
        # lex() normaliza saltos de línea y rompería las posiciones.
        for index, token, value in self._lexer.get_tokens_unprocessed(text):
            style_name = self._style_name(token)
            if style_name is None or not value:
                continue

            start_line = bisect_right(line_starts, index) - 1
            start_column = index - line_starts[start_line]
            for offset, fragment in enumerate(value.split("\n")):
                if fragment.endswith("\r"):
                    fragment = fragment[:-1]
                line_index = start_line + offset
                if line_index >= len(lines):
                    break

                column = start_column if offset == 0 else 0
                end_column = column + len(fragment)
                if end_column <= column:
                    continue

                line_text = lines[line_index]
                start_byte = len(line_text[:column].encode("utf-8"))
                end_byte = len(line_text[:end_column].encode("utf-8"))
                highlights[line_index].append(
                    (start_byte, end_byte, style_name)
                )

    @staticmethod
    def _style_name(token) -> str | None:
        for token_type, style_name in _TOKEN_STYLES:
            if token in token_type:
                return style_name
        return None
