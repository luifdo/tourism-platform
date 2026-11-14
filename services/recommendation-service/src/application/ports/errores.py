class DependenciaNoDisponibleError(Exception):
    """PostgreSQL o Valkey no respondieron. Los adaptadores la lanzan en lugar de sus
    excepciones propias, para que el chat responda 503 con el formato común."""
