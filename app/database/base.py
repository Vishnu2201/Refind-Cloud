"""SQLAlchemy declarative base class."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all ORM models.
    
    Subclasses will define business models in future modules.
    No models are declared in the foundation phase.
    """

    pass
