from .tasks import router as tasks_router, router_v2 as tasks_router_v2
from .auth import router as auth_router, router_v2 as auth_router_v2
from .stats import router as stats_router
from .admin import router as admin_router

__all__ = [
	"tasks_router",
	"tasks_router_v2",
	"auth_router",
	"auth_router_v2",
	"stats_router",
	"admin_router",
]
