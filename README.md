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

## 6. API Documentation

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
