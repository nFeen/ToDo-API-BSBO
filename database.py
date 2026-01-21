from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator
import os
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()


def _ensure_async_url(url: str | None) -> str:
    """Проверяет и конвертирует URL БД в async-совместимый.

    SQLAlchemy asyncio требует async-драйвер. Для PostgreSQL используем
    диалект "postgresql+asyncpg". Если указан sync-драйвер (например psycopg2),
    автоматически конвертируем.
    """
    if not url:
        raise RuntimeError(
            "DATABASE_URL не задан. Укажите переменную окружения DATABASE_URL. "
            "Для PostgreSQL используйте формат: postgresql+asyncpg://user:pass@host:port/db"
        )

    # Нормализуем только префикс драйвера
    if url.startswith("postgres://"):
        # Приводим устаревший префикс к стандартному
        url = "postgresql" + url[len("postgres"):]

    if url.startswith("postgresql+asyncpg://"):
        return url

    # Конвертация популярных sync-вариантов в asyncpg
    if url.startswith("postgresql://") or url.startswith("postgresql+psycopg2://") or url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql+psycopg://", "postgresql+asyncpg://"
        ).replace("postgresql://", "postgresql+asyncpg://", 1)

    # Для других СУБД пользователь должен сам указать async диалект.
    return url


DATABASE_URL = _ensure_async_url(os.getenv("DATABASE_URL"))

engine = create_async_engine(
    DATABASE_URL,
    echo=True,                    # Показывать SQL в консоли (удобно для обучения)
    future=True,                  # Использовать новый API SQLAlchemy 2.0
    pool_pre_ping=NullPool,           # Проверять живое ли соединение
    poolclass=NullPool,           # Использовать NullPool при работе через PgBouncer
    # Настройки для совместимости с PgBouncer:
    #  - отключаем кэш подготовленных выражений
    #  - задаем уникальные имена для prepared statements
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,              # Не сохранять автоматически при каждом изменении
    autocommit=False,             # Не коммитить автоматически
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session          # Отдаем сессию в endpoint
        finally:
            await session.close()  # Закрываем сессию после использования


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("База данных инициализирована!")


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Все таблицы удалены!")

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session