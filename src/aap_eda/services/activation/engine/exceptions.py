"""Exceptions for the engine module."""


class ContainerEngineError(Exception):
    """Base class for exceptions in this module."""


class ContainerStartError(ContainerEngineError):
    """Raised when a container fails to start."""


class ContainerImagePullError(ContainerEngineError):
    """Raised when a container fails to pull image."""


class ContainerStopError(ContainerEngineError):
    """Raised when a container fails to stop."""


class ContainerUpdateLogsError(ContainerEngineError):
    """Raised when a container fails to update logs."""


class ContainerNotFoundError(ContainerEngineError):
    """Raised when a container is not found."""
