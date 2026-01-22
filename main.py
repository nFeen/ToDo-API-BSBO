from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from database import init_db, get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from routers import tasks, stats, auth
from routers import tasks_router_v2, auth_router_v2, stats_router, admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код ДО yield выполняется при ЗАПУСКЕ
    print("Запуск приложения...")
    print("Инициализация базы данных...")
    # Создаем таблицы (если их нет)
    await init_db()
    print("Приложение готово к работе!")
    
    yield  # Здесь приложение работает
    
    # Код ПОСЛЕ yield выполняется при ОСТАНОВКЕ
    print("Остановка приложения...")


app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="3.0.0",
    contact={
        "name": "Дренин Кирилл Александрович",
    },
    lifespan=lifespan  # Подключаем lifespan
)

app.include_router(tasks.router, prefix="/api/v3")
app.include_router(stats.router, prefix="/api/v3")
app.include_router(auth.router, prefix="/api/v3")

# v2 endpoints
app.include_router(tasks_router_v2)
app.include_router(auth_router_v2)
app.include_router(admin_router)


@app.get("/")
async def read_root() -> dict:
    return {
        "message": "Task Manager API - Управление задачами по матрице Эйзенхауэра",
        "version": "3.0.0",
        "database": "PostgreSQL (Supabase)",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    """
    Проверка здоровья API и динамическая проверка подключения к БД.
    """
    try:
        # Пытаемся выполнить простейший запрос к БД
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "database": db_status
    }