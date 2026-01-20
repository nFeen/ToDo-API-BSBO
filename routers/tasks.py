from fastapi import APIRouter, HTTPException, Query
from fastapi import Response, status
from typing import List, Dict, Any
from datetime import datetime
from schemas import TaskBase, TaskCreate, TaskUpdate, TaskResponse
from database import tasks_db

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Task not found"}}
)

@router.get("")
async def get_all_tasks() -> dict:
    return {
        "count": len(tasks_db),
        "tasks": tasks_db
    }

@router.get("/quadrant/{quadrant}")
async def get_tasks_by_quadrant(quadrant: str) -> dict:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException( 
            status_code=400,
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4"
        )
    filtered_tasks = [
        task
        for task in tasks_db
        if task["quadrant"] == quadrant
    ]
    return {
        "quadrant": quadrant,
        "count": len(filtered_tasks),
        "tasks": filtered_tasks
    }

@router.get("/status/{status}")
async def get_tasks_by_status(status: str) -> dict:
    if status not in ["completed", "pending"]:
        raise HTTPException(status_code=404, detail="Статус не найден")
    is_completed = status == "completed"
    filtered_tasks = [task for task in tasks_db if task["completed"] == is_completed]
    return {
        "status": status,
        "count": len(filtered_tasks),
        "tasks": filtered_tasks
    }

@router.get("/search")
async def search_tasks(q: str) -> dict:
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Ключевое слово должно быть не менее 2 символов")
    q_lower = q.lower()
    filtered_tasks = [
        task for task in tasks_db
        if q_lower in (task["title"].lower() if task["title"] else "") or
           q_lower in (task["description"].lower() if task["description"] else "")
    ]
    return {
        "query": q,
        "count": len(filtered_tasks),
        "tasks": filtered_tasks
    }

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(task_id: int) -> TaskResponse:
    task = [task for task in tasks_db if task["id"] == task_id]
    if len(task) == 0:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена"
        )
    return task[0]

@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_task(task: TaskCreate) -> TaskResponse:
    if task.is_important and task.is_urgent:
        quadrant = "Q1"
    elif task.is_important and not task.is_urgent:
        quadrant = "Q2"
    elif not task.is_important and task.is_urgent:
        quadrant = "Q3"
    else:
        quadrant = "Q4"

    new_id = max((t["id"] for t in tasks_db), default=0) + 1

    new_task = {
        "id": new_id,
        "title": task.title,
        "description": task.description,
        "is_important": task.is_important,
        "is_urgent": task.is_urgent,
        "quadrant": quadrant,
        "completed": False,
        "created_at": datetime.now()
    }

    tasks_db.append(new_task)

    return new_task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate) -> TaskResponse:
    # Находим задачу по ID
    task = next(
        (task for task in tasks_db if task["id"] == task_id),
        None
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Получаем только те поля, которые реально были переданы в запросе
    update_data = task_update.model_dump(exclude_unset=True)

    # Обновляем только переданные поля
    for field, value in update_data.items():
        task[field] = value

    # Если изменились is_important или is_urgent — пересчитываем квадрант
    if "is_important" in update_data or "is_urgent" in update_data:
        if task["is_important"] and task["is_urgent"]:
            task["quadrant"] = "Q1"
        elif task["is_important"] and not task["is_urgent"]:
            task["quadrant"] = "Q2"
        elif not task["is_important"] and task["is_urgent"]:
            task["quadrant"] = "Q3"
        else:
            task["quadrant"] = "Q4"

    return task

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: int) -> TaskResponse:
    task = next(
        (task for task in tasks_db if task["id"] == task_id),
        None
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    task["completed"] = True
    task["completed_at"] = datetime.now()
    
    return task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    task = next(
        (task for task in tasks_db if task["id"] == task_id),
        None
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    tasks_db.remove(task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)