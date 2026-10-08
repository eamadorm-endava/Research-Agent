from .observability import setup_observability

# Initialize OpenTelemetry and standard Logging upon package load
setup_observability()

__all__ = ["agent"]
