"""Errors the CLI prints without a traceback."""


class AudioOverviewError(Exception):
    """A problem the user can fix from the message."""


class ScriptSchemaError(AudioOverviewError):
    """The model, replay file, or fake backend returned a script we cannot use."""


class GroundingRejected(AudioOverviewError):
    """Strict mode stopped before speech because the script is not grounded."""
