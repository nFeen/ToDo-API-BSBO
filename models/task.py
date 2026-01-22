from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class Task(Base):
    __tablename__ = "tasks"

    id = Column(
        Integer,
        primary_key=True,       # Первичный ключ
        index=True,             # Создать индекс для быстрого поиска
        autoincrement=True      # Автоматическая генерация
    )

    title = Column(
        Text,                   # Text = текст неограниченной длины
        nullable=False          # Не может быть NULL
    )

    description = Column(
        Text,
        nullable=True           # Может быть NULL
    )

    is_important = Column(
        Boolean,
        nullable=False,
        default=False           # По умолчанию False
    )

    # Плановый срок выполнения задачи
    deadline_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    quadrant = Column(
        String(2),              # Максимум 2 символа: "Q1", "Q2", "Q3", "Q4"
        nullable=False
    )

    completed = Column(
        Boolean,
        nullable=False,
        default=False
    )

    created_at = Column(
        DateTime(timezone=True),          # С поддержкой часовых поясов
        server_default=func.now(),        # Автоматически текущее время
        nullable=False
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True                     # NULL пока задача не завершена
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    owner = relationship(
        "User",
        back_populates="tasks"
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', quadrant='{self.quadrant}')>"

    @property
    def is_urgent(self) -> bool:
        """Срочно, если до дедлайна осталось 3 дня или меньше.
        Отрицательное значение (просрочено) также считается срочно.
        """
        if not self.deadline_at:
            return False
        try:
            days = (self.deadline_at.date() - datetime.now().date()).days
        except Exception:
            return False
        return days <= 3

    @property
    def days_left(self) -> int:
        """Количество дней до дедлайна от сегодняшней даты.
        Может быть отрицательным, если срок прошёл.
        """
        if not self.deadline_at:
            return 0
        return (self.deadline_at.date() - datetime.now().date()).days

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "is_important": self.is_important,
            "is_urgent": self.is_urgent,
            "quadrant": self.quadrant,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "deadline_at": self.deadline_at,
            "days_left": self.days_left,
            "user_id": self.user_id
        }