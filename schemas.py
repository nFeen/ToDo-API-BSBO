# Pydantic модели
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TaskBase(BaseModel):
    title: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Название задачи"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Описание задачи"
    )
    is_important: bool = Field(
        ...,
        description="Важность задачи"
    )
    deadline_at: datetime = Field(
        ...,
        description="Плановый дедлайн задачи"
    )


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="Новое название задачи"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Новое описание"
    )
    is_important: Optional[bool] = Field(
        None,
        description="Новая важность"
    )
    deadline_at: Optional[datetime] = Field(
        None,
        description="Новый дедлайн"
    )
    completed: Optional[bool] = Field(
        None,
        description="Статус выполнения"
    )


class TaskResponse(TaskBase):
    # Для обратной совместимости: старые записи могут не иметь дедлайна
    deadline_at: Optional[datetime] = Field(
        None,
        description="Плановый дедлайн задачи (может отсутствовать у старых записей)"
    )
    id: int = Field(
        ...,
        description="Уникальный идентификатор задачи",
        examples=[1]
    )
    quadrant: str = Field(
        ...,
        description="Квадрант матрицы Эйзенхауэра (Q1, Q2, Q3, Q4)",
        examples=["Q1"]
    )
    completed: bool = Field(
        default=False,
        description="Статус выполнения задачи"
    )
    created_at: datetime = Field(
        ...,
        description="Дата и время создания задачи"
    )
    is_urgent: bool = Field(
        ...,
        description="Срочность задачи (рассчитывается по дедлайну)"
    )
    days_left: int = Field(
        ...,
        description="Оставшиеся дни до дедлайна (может быть отрицательным)"
    )

    class Config:
        from_attributes = True