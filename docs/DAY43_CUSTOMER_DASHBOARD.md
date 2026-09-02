# Day 43 - Customer Dashboard

## Goal

Day 43 turns the authenticated Customer workspace into the first real Smart Q product dashboard. The frontend now reads the logged-in customer's bookings and live queue state from the backend and presents them in one focused operational view.

The browser presents backend state; it does not recreate Smart Q business rules.

## Scope

Day 43 adds:

- a dedicated customer dashboard at `/app/customer/`;
- current queue number, state, branch and service;
- server-calculated queue position, people ahead and estimated wait;
- the next non-final appointment;
- upcoming appointment and history tables;
- customer-owned lifecycle history in a details dialog;
- server-authoritative customer check-in;
- booking cancellation with deliberate confirmation;
- loading, empty, success and error states;
- responsive customer-specific styling;
- focused regression coverage.

## Backend authority remains unchanged

The dashboard does not calculate priority, capacity, check-in eligibility, queue position or ETA itself.

It uses the existing endpoints:

- `GET /api/v1/bookings/my/`
- `GET /api/v1/queues/my-current/`
- `GET /api/v1/queues/bookings/<booking_id>/timeline/`
- `POST /api/v1/bookings/<id>/check-in/`
- `PATCH /api/v1/bookings/<id>/cancel/`

The backend remains responsible for ownership checks, final-state rules, check-in timing and the locked Smart Q ETA contract.

## Current queue presentation

When an active ticket exists for today, the customer sees queue number, Waiting or Serving state, queue position, people ahead, estimated wait, service, branch and assigned counter when available.

The values come directly from `/api/v1/queues/my-current/`. No JavaScript ETA formula was introduced.

When no active queue exists, the interface shows a neutral empty state instead of fake statistics.

## Appointment presentation

Non-final bookings are separated from final history. Final history includes completed, cancelled and no-show bookings. The nearest non-final booking is shown as the next appointment. Upcoming appointments are presented chronologically; history is shown newest first.

This is presentation logic only and does not change persisted booking state.

## Check-in behavior

The dashboard exposes Check in only for bookings that have not entered the live queue. The frontend sends the request to the existing backend endpoint and does not decide whether the six-hour window is open.

If the request is early, the backend-provided opening timestamp is shown to the customer. Backend conflict responses trigger a refresh so the UI returns to authoritative server state.

## Cancellation behavior

Cancellation uses the existing customer-owned endpoint. The browser asks for confirmation before sending the request and then reloads the dashboard after success. No cancellation rule was introduced in JavaScript.

## Lifecycle history

The Details action loads the append-only customer QueueEvent timeline. Event codes are translated into readable labels such as Checked in, Called to a counter, Service completed and Appointment cancelled. The underlying timeline remains filtered by backend ownership.

## Frontend structure

New files:

- `templates/frontend/customer_dashboard.html`
- `static/css/customer-dashboard.css`
- `static/js/pages/customer-dashboard.js`
- `smartq/test_day43_customer_dashboard.py`
- `docs/DAY43_CUSTOMER_DASHBOARD.md`

Updated files:

- `smartq/urls.py`
- `.github/workflows/django-tests.yml`

The dashboard continues using the Day 42 shared browser API client for same-origin credentials, CSRF protection and structured errors.

## Visual direction

Day 43 keeps the Day 41 design system: white dominant surfaces, light-blue structure, restrained green success states, dark blue-grey text, subtle borders and no emoji interface language. The screen prioritizes live queue state and the next appointment instead of filling the page with decorative metric cards.

## Responsive behavior

The two primary customer panels collapse to one column on smaller screens. Queue metrics become a compact vertical list on mobile. Appointment tables remain horizontally scrollable rather than becoming unreadable cards.

## Automated verification

The focused Day 43 test suite verifies that the customer route renders the new contract, required static assets are discoverable, booking data remains ownership-scoped, the live queue response supplies the fields required by the frontend, and non-customer routes do not render the customer dashboard.

CI runs:

`python manage.py test smartq.test_day43_customer_dashboard`

before the complete Smart Q test suite.

## Completion rule

Day 43 is complete only when the focused test suite and complete SQLite3 regression workflow pass on the exact current feature head and the pull request is ready for review. `main` remains unchanged until explicit merge approval.

## Next milestone

Day 44 builds the full appointment booking and check-in experience: branch selection, service selection, date and slot availability, booking confirmation and the richer appointment workflow around this customer dashboard.
