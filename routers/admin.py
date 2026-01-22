from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_async_session
from models import User, Task
from dependencies import get_current_admin
from typing import List, Dict

router = APIRouter(
    prefix="/api/v2/admin",
    tags=["admin"],
)


@router.get("/users", response_model=List[Dict])
async def list_users_with_task_counts(
    db: AsyncSession = Depends(get_async_session),
    admin = Depends(get_current_admin)
) -> List[Dict]:
    # LEFT OUTER JOIN tasks grouped by user, count tasks
    stmt = (
        select(
            User.id,
            User.nickname,
            User.email,
            func.count(Task.id).label("tasks_count")
        )
        .join(Task, Task.user_id == User.id, isouter=True)
        .group_by(User.id, User.nickname, User.email)
        .order_by(User.id)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": r.id,
            "nickname": r.nickname,
            "email": r.email,
            "tasks_count": int(r.tasks_count),
        }
        for r in rows
    ]
