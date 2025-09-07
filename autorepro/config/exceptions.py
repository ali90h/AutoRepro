"""Configuration validation exceptions."""


class ConfigValidationError(ValueError):
    """Base class for configuration validation errors."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


class FieldValidationError(ConfigValidationError):
    """Individual field validation error."""

    pass


class CrossFieldValidationError(ConfigValidationError):
    """Cross-field validation error."""

    pass
