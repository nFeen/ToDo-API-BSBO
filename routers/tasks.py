from fastapi import APIRouter, HTTPException, Query
from fastapi import Response, status, Depends
from typing import List, Dict, Any
from datetime import datetime
from schemas import TaskBase, TaskCreate, TaskUpdate, TaskResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_async_session
from models.task import Task

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Task not found"}}
)

@router.get("", response_model=List[TaskResponse])
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks

@router.get("/quadrant/{quadrant}", response_model=List[TaskResponse])
async def get_tasks_by_quadrant(
    quadrant: str,
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(
            status_code=400,
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4"  # текст, который будет выведен пользователю
        )
    
    # SELECT * FROM tasks WHERE quadrant = 'Q1'
    result = await db.execute(
        select(Task).where(Task.quadrant == quadrant)
    )
    tasks = result.scalars().all()
    return tasks

@router.get("/status/{status}", response_model=List[TaskResponse])
async def get_tasks_by_status(
    status: str,
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if status not in ["completed", "pending"]:
        raise HTTPException(
            status_code=404,
            detail="Недопустимый статус. Используйте: completed или pending"
        )
    
    is_completed = (status == "completed")
    
    # SELECT * FROM tasks WHERE completed = True/False
    result = await db.execute(
        select(Task).where(Task.completed == is_completed)
    )
    tasks = result.scalars().all()
    return tasks

@router.get("/search", response_model=List[TaskResponse])
async def search_tasks(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    keyword = f"%{q.lower()}%"  # %keyword% для LIKE
    
    # SELECT * FROM tasks
    # WHERE LOWER(title) LIKE '%keyword%'
    # OR LOWER(description) LIKE '%keyword%'
    result = await db.execute(
        select(Task).where(
            (Task.title.ilike(keyword)) |
            (Task.description.ilike(keyword))
        )
    )
    tasks = result.scalars().all()
    
    if not tasks:
        raise HTTPException(
            status_code=404,
            detail="По данному запросу ничего не найдено"
        )
    
    return tasks

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена"
        )
    
    return task

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    # Рассчитываем срочность по дедлайну
    days_left = (task.deadline_at.date() - datetime.now().date()).days
    is_urgent = days_left <= 3
    # Определяем квадрант
    if task.is_important and is_urgent:
        quadrant = "Q1"
    elif task.is_important and not is_urgent:
        quadrant = "Q2"
    elif not task.is_important and is_urgent:
        quadrant = "Q3"
    else:
        quadrant = "Q4"
    
    new_task = Task(
        title=task.title,
        description=task.description,
        is_important=task.is_important,
        deadline_at=task.deadline_at,
        quadrant=quadrant,
        completed=False  # Новая задача всегда не выполнена
        # created_at заполнится автоматически (server_default=func.now())
    )
    
    db.add(new_task)          # Добавляем в сессию (еще не в БД!)
    await db.commit()         # Выполняем INSERT в БД
    await db.refresh(new_task)  # Обновляем объект (получаем ID из БД)
    
    # FastAPI автоматически преобразует Task → TaskResponse
    return new_task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    # ШАГ 1: по аналогии с GET ищем задачу по ID
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    
    # Получаем одну задачу или None
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # ШАГ 2: Получаем и обновляем только переданные поля (exclude_unset=True)
    # Без exclude_unset=True все None поля тоже попадут в БД
    update_data = task_update.model_dump(exclude_unset=True)
    
    # ШАГ 3: Обновить атрибуты объекта
    for field, value in update_data.items():
        setattr(task, field, value)  # task.field = value
    
    # ШАГ 4: Пересчитываем квадрант, если изменились важность или дедлайн
    if "is_important" in update_data or "deadline_at" in update_data:
        days_left = (task.deadline_at.date() - datetime.now().date()).days if task.deadline_at else 99999
        is_urgent = days_left <= 3
        if task.is_important and is_urgent:
            task.quadrant = "Q1"
        elif task.is_important and not is_urgent:
            task.quadrant = "Q2"
        elif not task.is_important and is_urgent:
            task.quadrant = "Q3"
        else:
            task.quadrant = "Q4"
    
    await db.commit()         # UPDATE tasks SET ... WHERE id = task_id
    await db.refresh(task)    # Обновить объект из БД
    
    return task

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task.completed = True
    task.completed_at = datetime.now()
    
    await db.commit()
    await db.refresh(task)
    
    return task

@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Сохраняем информацию для ответа
    deleted_task_info = {
        "id": task.id,
        "title": task.title
    }
    
    await db.delete(task)  # Помечаем для удаления
    await db.commit()      # DELETE FROM tasks WHERE id = task_id
    
    return {
        "message": "Задача успешно удалена",
        "id": deleted_task_info["id"],
        "title": deleted_task_info["title"]
    }