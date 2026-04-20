class AppError(Exception):
  """Base application error."""


class AuthenticationError(AppError):
  """Raised when authentication credentials are invalid."""


class AuthorizationError(AppError):
  """Raised when the actor does not have permission for an operation."""


class ConflictError(AppError):
  """Raised when a unique or state conflict occurs."""


class NotFoundError(AppError):
  """Raised when a requested resource cannot be found."""


class ConfigurationError(AppError):
  """Raised when required infrastructure or integration config is missing."""
