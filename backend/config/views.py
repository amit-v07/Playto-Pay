from django.http import JsonResponse
from django.db import connection
from redis import Redis
from decouple import config
import logging

logger = logging.getLogger(__name__)

def health_check(request):
    """
    Simple health check endpoint that verifies DB and Redis connectivity.
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }
    
    # Check Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row and row[0] == 1:
                health_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "unhealthy"
        health_status["status"] = "unhealthy"

    # Check Redis
    try:
        redis_url = config("REDIS_URL", default="redis://redis:6379/0")
        r = Redis.from_url(redis_url, socket_connect_timeout=1)
        if r.ping():
            health_status["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["redis"] = "unhealthy"
        health_status["status"] = "unhealthy"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JsonResponse(health_status, status=status_code)
