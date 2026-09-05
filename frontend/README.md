# Smart Q React Frontend

This directory contains Smart Q's browser application.

## Stack

- React 18
- TypeScript
- Vite
- React Router
- TanStack Query

Django + Django REST Framework remain the backend and source of truth. The React app uses the existing same-origin session/CSRF contract under `/api/v1/`.

## Codespaces / local run

Use two terminals for active frontend development:

```bash
# Terminal 1 — Django API/backend
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

```bash
# Terminal 2 — React/Vite dev server
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to Django on port 8000.

To run the integrated Django-served application instead:

```bash
cd frontend
npm install
npm run build
cd ..
python manage.py runserver 0.0.0.0:8000
```

The Vite production build writes `app.js` and `app.css` to `static/react/`. Build output and `node_modules` are generated artifacts and are not committed.

## Engineering boundary

Do not duplicate Smart Q business rules in React. Queue priority, queue numbering, slot generation, capacity validation, check-in eligibility, branch scoping, counter ownership, disruption impact and rescheduling validity remain backend-owned.
