"""Exceptions for problems the user can fix. The CLI prints them as one-line messages, without traceback."""


class SpriteKilnError(Exception):
    """Base class for user-facing errors (bad spec, missing file, failed render or export)."""


class RenderError(SpriteKilnError):
    pass


class ExportError(SpriteKilnError):
    pass
