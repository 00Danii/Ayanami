from textual.theme import Theme


MIDNIGHT = Theme(
    name="midnight",
    primary="#7aa2f7",
    secondary="#7dcfff",
    accent="#bb9af7",
    foreground="#c0caf5",
    background="#1a1b26",
    surface="#24283b",
    panel="#16161e",
    success="#9ece6a",
    warning="#e0af68",
    error="#f7768e",
    dark=True,
)

DARK = Theme(
    name="dark",
    primary="#89b4fa",
    secondary="#94e2d5",
    accent="#f5c2e7",
    foreground="#cdd6f4",
    background="#1e1e2e",
    surface="#313244",
    panel="#181825",
    success="#a6e3a1",
    warning="#f9e2af",
    error="#f38ba8",
    dark=True,
)

LIGHT = Theme(
    name="light",
    primary="#1e66f5",
    secondary="#179299",
    accent="#ea76cb",
    foreground="#4c4f69",
    background="#eff1f5",
    surface="#e6e9ef",
    panel="#dce0e8",
    success="#40a02b",
    warning="#df8e1d",
    error="#d20f39",
    dark=False,
)


THEMES = {
    "midnight": MIDNIGHT,
    "dark": DARK,
    "light": LIGHT,
}
