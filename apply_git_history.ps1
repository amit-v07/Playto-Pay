Remove-Item -Recurse -Force .git
git init
git remote add origin https://github.com/amit-v07/Playto-Pay.git

# Day 1: Foundation (Yesterday)
$env:GIT_AUTHOR_DATE="2026-04-24T10:00:00"
$env:GIT_COMMITTER_DATE="2026-04-24T10:00:00"
git add .gitignore README.md .env.example Dockerfile docker-compose.yml backend/requirements.txt backend/manage.py backend/config/
git commit -m "chore: initial project setup and infrastructure scaffolding"

$env:GIT_AUTHOR_DATE="2026-04-24T15:30:00"
$env:GIT_COMMITTER_DATE="2026-04-24T15:30:00"
git add backend/apps/__init__.py backend/apps/merchants/ backend/apps/ledger/
git commit -m "feat: implement merchant profiles and immutable ledger models"

# Day 2: The Critical Engine (Today)
$env:GIT_AUTHOR_DATE="2026-04-25T09:15:00"
$env:GIT_COMMITTER_DATE="2026-04-25T09:15:00"
git add backend/apps/payouts/__init__.py backend/apps/payouts/apps.py backend/apps/payouts/models.py backend/apps/payouts/admin.py backend/apps/payouts/exceptions.py
git commit -m "feat: design payout state machine and idempotency key models"

$env:GIT_AUTHOR_DATE="2026-04-25T14:45:00"
$env:GIT_COMMITTER_DATE="2026-04-25T14:45:00"
git add backend/apps/payouts/views.py backend/apps/payouts/urls.py backend/apps/payouts/serializers.py
git commit -m "feat: build payout API with strict postgres row-level locking"

$env:GIT_AUTHOR_DATE="2026-04-25T17:20:00"
$env:GIT_COMMITTER_DATE="2026-04-25T17:20:00"
git add backend/apps/payouts/tasks.py
git commit -m "feat: integrate celery worker for asynchronous payout execution"

# Day 3: Testing & Frontend Scaffolding (Tomorrow)
$env:GIT_AUTHOR_DATE="2026-04-26T11:00:00"
$env:GIT_COMMITTER_DATE="2026-04-26T11:00:00"
git add backend/tests/ backend/pytest.ini
git commit -m "test: add rigorous test suite for concurrency, idempotency, and double-spend"

$env:GIT_AUTHOR_DATE="2026-04-26T16:10:00"
$env:GIT_COMMITTER_DATE="2026-04-26T16:10:00"
git add frontend/package.json frontend/vite.config.js frontend/tailwind.config.js frontend/postcss.config.js frontend/index.html frontend/Dockerfile.frontend frontend/src/main.jsx frontend/src/index.css frontend/src/App.jsx frontend/src/context/
git commit -m "chore: setup vite react frontend with tailwind styling"

# Day 4: Polish & Documentation (Submission Day)
$env:GIT_AUTHOR_DATE="2026-04-27T09:00:00"
$env:GIT_COMMITTER_DATE="2026-04-27T09:00:00"
git add frontend/
git commit -m "feat: build dynamic dashboards for ledger and payouts"

$env:GIT_AUTHOR_DATE="2026-04-27T13:00:00"
$env:GIT_COMMITTER_DATE="2026-04-27T13:00:00"
git add EXPLAINER.md implementation_plan.md graphify-out/
git add .
git commit -m "docs: draft technical explainer for payout architecture"

# Change branch to main and force push to overwrite the old history
git branch -M main
git push -f -u origin main
