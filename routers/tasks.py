from fastapi import APIRouter, HTTPException, Query
from fastapi import Response, status, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime
from schemas import TaskBase, TaskCreate, TaskUpdate, TaskResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_async_session
from models.task import Task
from models.user import User
from dependencies import get_current_user

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Task not found"}}
)


def calculate_days_until_deadline(deadline_at: Optional[datetime]) -> int:
    """Возвращает количество дней до дедлайна (может быть отрицательным).
    Если дедлайн отсутствует, возвращает 0.
    """
    if not deadline_at:
        return 0
    return (deadline_at.date() - datetime.now().date()).days

@router.get("", response_model=List[TaskResponse])
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    if current_user.role.value == "admin":
        result = await db.execute(select(Task))
    else:
        result = await db.execute(
            select(Task).where(Task.user_id == current_user.id)
        )
    tasks = result.scalars().all()

    tasks_with_days = []
    for task in tasks:
        task_dict = task.__dict__.copy()
        task_dict['days_until_deadline'] = calculate_days_until_deadline(task.deadline_at)
        tasks_with_days.append(TaskResponse(**task_dict))

    return tasks_with_days

@router.get("/quadrant/{quadrant}", response_model=List[TaskResponse])
async def get_tasks_by_quadrant(
    quadrant: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(
            status_code=400,
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4"  # текст, который будет выведен пользователю
        )
    
    if current_user.role.value == "admin":
        result = await db.execute(
            select(Task).where(Task.quadrant == quadrant)
        )
    else:
        result = await db.execute(
            select(Task).where(Task.quadrant == quadrant, Task.user_id == current_user.id)
        )
    tasks = result.scalars().all()
    return tasks

@router.get("/status/{status}", response_model=List[TaskResponse])
async def get_tasks_by_status(
    status: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    if status not in ["completed", "pending"]:
        raise HTTPException(
            status_code=404,
            detail="Недопустимый статус. Используйте: completed или pending"
        )
    
    is_completed = (status == "completed")
    if current_user.role.value == "admin":
        result = await db.execute(
            select(Task).where(Task.completed == is_completed)
        )
    else:
        result = await db.execute(
            select(Task).where(Task.completed == is_completed, Task.user_id == current_user.id)
        )
    tasks = result.scalars().all()
    return tasks

@router.get("/search", response_model=List[TaskResponse])
async def search_tasks(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    keyword = f"%{q.lower()}%"  # %keyword% для LIKE
    
    if current_user.role.value == "admin":
        result = await db.execute(
            select(Task).where(
                (Task.title.ilike(keyword)) |
                (Task.description.ilike(keyword))
            )
        )
    else:
        result = await db.execute(
        select(Task).where(
            Task.user_id == current_user.id,
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
    current_user: User = Depends(get_current_user)
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
    if current_user.role.value != "admin" and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой задаче"
        )
    days_deadline = calculate_days_until_deadline(task.deadline_at)
    task_dict = task.__dict__.copy()
    task_dict['days_until_deadline'] = days_deadline

    if task.deadline_at is not None and days_deadline is not None and days_deadline < 0:
        task_dict['status_message'] = "Задача просрочена"
    else:
        task_dict['status_message'] = "Все идет по плану"
    return TaskResponse(**task_dict)

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
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
        completed=False,
        user_id=current_user.id
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
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    # ШАГ 1: по аналогии с GET ищем задачу по ID
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if current_user.role.value != "admin" and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой задаче"
        )
    
    update_data = task_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(task, field, value)  # task.field = value
    
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
    
    task_dict = task.__dict__.copy()
    task_dict['days_until_deadline'] = calculate_days_until_deadline(task.deadline_at)    
    return TaskResponse(**task_dict)

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if current_user.role.value != "admin" and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой задаче"
        )

    task.completed = True
    task.completed_at = datetime.now()
    
    await db.commit()
    await db.refresh(task)

    task_dict = task.__dict__.copy()
    task_dict['days_until_deadline'] = calculate_days_until_deadline(task.deadline_at)
    
    return TaskResponse(**task_dict)

@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> dict:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if current_user.role.value != "admin" and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этой задаче"
        )
    
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


# v2 only: today deadlines endpoint
router_v2 = APIRouter(
    prefix="/api/v2/tasks",
    tags=["tasks v2"],
    responses={404: {"description": "Task not found"}}
)


@router_v2.get("/today", response_model=List[TaskResponse])
async def get_tasks_due_today(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    today = datetime.now().date()
    if current_user.role.value == "admin":
        stmt = select(Task).where(
            (Task.deadline_at.is_not(None)) &
            (Task.completed == False)
        )
    else:
        stmt = select(Task).where(
            (Task.user_id == current_user.id) &
            (Task.deadline_at.is_not(None)) &
            (Task.completed == False)
        )

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    # Оставляем только те, у кого дедлайн именно сегодня (по дате)
    tasks_today: List[Task] = []
    for t in tasks:
        if t.deadline_at and t.deadline_at.date() == today:
            tasks_today.append(t)

    return tasks_today