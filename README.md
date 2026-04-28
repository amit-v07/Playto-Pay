# Platopay Payout Engine

## 1. Project Overview
A highly concurrent, robust Django-based payout engine designed with strict transaction boundaries to ensure zero double-spending.

## 2. Tech Stack
* **Backend Framework:** Django & Django REST Framework (DRF)
* **Database:** PostgreSQL
* **Background Jobs:** Celery
* **Message Broker / Cache:** Redis
* **Frontend:** React (Vite) + Tailwind CSS
* **Infrastructure:** Docker & Docker Compose

## 3. Local Setup (The "One-Command" Run)
To make reviewing this project frictionlessly easy, everything is containerized. Ensure you have Docker and Docker Compose installed, then run:

```bash
docker compose up -d --build
```

**Note:** This single command automatically spins up the PostgreSQL DB, Redis instance, Backend API, Celery Worker, Celery Beat scheduler, and the React Frontend. 
* The Frontend will be available at: `http://localhost:3000`
* The API will be available at: `http://localhost:8001`

## 4. Seeding Data
The application will automatically run migrations and seed data on startup. If you need to manually populate the database with the initial dummy merchants (Alice and Bob) and their starting balances, run this command in a separate terminal:

```bash
docker compose exec api python manage.py seed_demo_data
```

## 5. Running Tests
The test suite rigorously validates the critical sections of the application. We have specifically written tests for concurrency (preventing race conditions) and idempotency (handling duplicate network requests safely).

To execute the test suite inside the container, run:

```bash
docker compose exec api pytest
```

## 6. Railway Deployment
This project should be deployed to Railway as separate services instead of a single `docker-compose` stack:

- `frontend` service from the `frontend/` directory
- `api` service from the `backend/` directory
- `worker` service from the `backend/` directory
- `beat` service from the `backend/` directory
- PostgreSQL plugin
- Redis plugin

### Backend Service Settings
Use the `backend/` directory as the service root.

- `api` start command: default container command
- `worker` start command: `celery -A config.celery_app worker --loglevel=info --concurrency=4`
- `beat` start command: `celery -A config.celery_app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler`

Set these environment variables on all backend-based services:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<strong-random-secret>
ALLOWED_HOSTS=<your-api-domain>
CORS_ALLOWED_ORIGINS=<your-frontend-domain>
CSRF_TRUSTED_ORIGINS=<your-frontend-domain>
DATABASE_URL=<Railway Postgres connection string>
REDIS_URL=<Railway Redis connection string>
SEED_DEMO_DATA_ON_START=true
```

Notes:

- `ALLOWED_HOSTS` accepts a comma-separated list
- `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` should include the full Railway frontend URL with `https://`
- `SEED_DEMO_DATA_ON_START=true` is optional and useful only for demo deployments

### Frontend Service Settings
Use the `frontend/` directory as the service root.

Set:

```bash
VITE_API_BASE_URL=https://<your-api-domain>/api/v1
```

This makes the frontend call the Railway API directly in production while still using the local reverse-proxy behavior in Docker Compose.

## 7. API Documentation

We use `drf-spectacular` to automatically generate OpenAPI 3.0 schemas. Once the application is running, you can access the interactive documentation here:
* **Swagger UI:** [http://localhost:8001/api/v1/schema/docs/](http://localhost:8001/api/v1/schema/docs/)
* **Redoc:** [http://localhost:8001/api/v1/schema/redoc/](http://localhost:8001/api/v1/schema/redoc/)
* **Raw OpenAPI Schema:** [http://localhost:8001/api/v1/schema/](http://localhost:8001/api/v1/schema/)

### Create Payout
`POST /api/v1/payouts/`

Initiates a new withdrawal request. This endpoint enforces strict idempotency and uses row-level locking to prevent balance overdraws.

**Example cURL Request:**
```bash
curl -X POST http://localhost:8001/api/v1/payouts/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -H "Idempotency-Key: 123e4567-e89b-12d3-a456-426614174000" \
  -d '{
    "amount": 50000
  }'
```
*(Note: `amount` is strictly handled as an integer representing paise to avoid floating-point math issues. 50000 paise = ₹500.00)*
