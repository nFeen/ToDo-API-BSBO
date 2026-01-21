from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Task
from database import get_async_session
from typing import List, Dict
from datetime import datetime

router = APIRouter(
    prefix="/stats",
    tags=["statistics"]
)


@router.get("/", response_model=dict)
async def get_tasks_stats(
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    
    total_tasks = len(tasks)
    
    by_quadrant = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    by_status = {"completed": 0, "pending": 0}
    
    for task in tasks:
        if task.quadrant in by_quadrant:
            by_quadrant[task.quadrant] += 1
        
        if task.completed:
            by_status["completed"] += 1
        else:
            by_status["pending"] += 1
    
    return {
        "total_tasks": total_tasks,
        "by_quadrant": by_quadrant,
        "by_status": by_status
    }


@router.get("/deadlines", response_model=List[Dict])
async def get_pending_deadlines(
    db: AsyncSession = Depends(get_async_session)
) -> List[Dict]:
    """Статистика по срокам выполнения задач со статусом "pending":
    название, описание, дата начала, оставшийся срок (в днях).
    """
    result = await db.execute(select(Task).where(Task.completed == False))
    tasks = result.scalars().all()

    items: List[Dict] = []
    today = datetime.now().date()
    for t in tasks:
        days_left = (t.deadline_at.date() - today).days if t.deadline_at else 0
        items.append({
            "title": t.title,
            "description": t.description,
            "created_at": t.created_at,
            "days_left": days_left
        })

    return items