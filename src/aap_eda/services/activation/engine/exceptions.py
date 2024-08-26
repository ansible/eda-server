"""Exceptions for the engine module."""


class ContainerEngineError(Exception):
    """Base class for exceptions in this module."""


class ContainerEngineInitError(ContainerEngineError):
    """Raised when an engine fails to initialize."""


class ContainerStartError(ContainerEngineError):
    """Raised when a container fails to start."""


class ContainerLoginError(ContainerEngineError):
    """Raised when a container fails to login."""


class ContainerImagePullError(ContainerEngineError):
    """Raised when a container fails to pull image."""


class ContainerCleanupError(ContainerEngineError):
    """Raised when a container fails to stop."""


class ContainerUpdateLogsError(ContainerEngineError):
    """Raised when a container fails to update logs."""


class ContainerNotFoundError(ContainerEngineError):
    """Raised when a container is not found."""
