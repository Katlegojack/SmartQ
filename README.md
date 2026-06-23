# Smart Q

**Where Time Meets Priority**

Smart Q is a Django-based **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair, and efficient.

The system helps customers book services at a branch, receive queue tickets, understand their queue status, and get notified when important queue or rescheduling events happen. Smart Q is being developed as a practical software engineering project that combines booking management, queue operations, disruption handling, rescheduling logic, notifications, and API development.

The long-term vision is to reduce unnecessary physical waiting, help organizations manage customer flow, and give customers clearer visibility into when they will be assisted.

---

## Table of Contents

- [Project Vision](#project-vision)
- [Project Overview](#project-overview)
- [Problem Statement](#problem-statement)
- [Solution Summary](#solution-summary)
- [Current Project Status](#current-project-status)
- [Current API Status](#current-api-status)
- [Core Features](#core-features)
- [Implemented Features](#implemented-features)
- [Planned Features](#planned-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Current Django Apps](#current-django-apps)
- [Database and Model Relationships](#database-and-model-relationships)
- [Queue Number Rules](#queue-number-rules)
- [Priority Queue Logic](#priority-queue-logic)
- [Waiting-Time Intelligence](#waiting-time-intelligence)
- [Queue Operations](#queue-operations)
- [Disruption and Rescheduling Intelligence](#disruption-and-rescheduling-intelligence)
- [Notification System](#notification-system)
- [API Endpoints](#api-endpoints)
- [Main User Roles](#main-user-roles)
- [Project Setup](#project-setup)
- [Running the Project](#running-the-project)
- [Admin Usage](#admin-usage)
- [API Testing](#api-testing)
- [Development Workflow](#development-workflow)
- [Security and Safety Considerations](#security-and-safety-considerations)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Author](#author)

---

## Project Vision

Smart Q is more than a basic digital queue system.

It is being built as a queue intelligence platform that helps organizations answer important operational questions such as:

```text
Who is waiting?
Who should be served next?
How long might a customer wait?
Which customers are affected by a disruption?
Which customers may need to be rescheduled?
Has the customer been notified?
```

The bigger vision is to give customers their time back by making queues:

- digital
- fair
- trackable
- predictable
- safer during disruptions
- easier for staff and managers to operate

Smart Q aims to move queue management from a passive waiting system to an intelligent operational system.

---

## Project Overview

Smart Q allows a customer to book a service at a branch. Once the booking is created, the system can generate a queue ticket and decide whether the customer belongs in the general queue or priority queue.

The system is currently being built as a **Django modular monolith**.

That means the backend is still one Django project, but responsibilities are separated into focused Django apps such as:

```text
accounts
branches
services
bookings
queues
counters
notifications
rescheduling
```

This keeps the system easier to understand, test, and grow.

A simplified flow looks like this:

```text
Customer/User
   ↓
Profile Information
   ↓
Booking
   ↓
Branch + Service
   ↓
Priority Decision
   ↓
Queue Ticket
   ↓
Queue Operations
   ↓
Notifications / Rescheduling / Reports
```

---

## Problem Statement

Many organizations still rely on physical queues where customers wait for long periods without knowing when they will be assisted.

This creates several problems:

- Customers waste time waiting physically.
- Organizations struggle with overcrowding.
- Staff cannot easily manage the queue flow.
- Priority customers may not be handled fairly.
- Waiting times are often unclear or unrealistic.
- Delays and system interruptions are not communicated properly.
- Customers may remain in the queue even when there is no realistic chance of being assisted that day.
- Managers may not have useful reports about queue performance, no-shows, delays, or service capacity.

Smart Q aims to solve these problems by making queues digital, trackable, and intelligent.

---

## Solution Summary

Smart Q provides a backend foundation for:

- customer booking
- branch and service management
- automatic queue ticket generation
- general and priority queue handling
- queue movement
- waiting-time estimation
- counter capacity awareness
- queue disruption tracking
- reschedule-risk detection
- notification creation
- API access for frontend integration

A simplified queue flow:

```text
Customer creates booking
   ↓
Booking stores branch, service, date, and time
   ↓
Smart Q decides General or Priority
   ↓
QueueTicket is created
   ↓
Queue number is generated
   ↓
Staff operate the queue
   ↓
Waiting time and queue position can be calculated
   ↓
Disruptions can be tracked
   ↓
Affected customers can be flagged
   ↓
Notifications can be created and exposed through the API
```

---

## Current Project Status

Smart Q is in active backend development.

The project currently has a strong Django backend foundation with models, business logic, service functions, migrations, admin testing, API work, GitHub workflow, and pull request discipline.

Current status:

- Django project foundation is complete.
- Multiple Django apps have been created.
- Core queue models and relationships are implemented.
- Booking-to-ticket relationship is implemented.
- Queue number generation is implemented.
- Priority decision logic is implemented.
- Queue movement logic has been worked on.
- Waiting-time foundation has been created.
- Queue disruption tracking has been implemented.
- Reschedule-risk logic has been implemented.
- Customer disruption impact tracking has been implemented.
- Notification model and services are implemented.
- Reschedule confirmation notification workflow is implemented.
- Django REST Framework has been added.
- Initial notification API endpoints are implemented and tested.
- Frontend is still limited.
- External notification channels such as SMS, email, and WhatsApp are not yet implemented.
- Real-time updates are planned but not yet implemented.

---

## Current API Status

Smart Q now has its first working Django REST Framework API endpoints.

The notification API foundation is implemented.

Current API endpoints:

```text
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

These endpoints allow a logged-in user to:

- view their notifications
- see their unread notification count
- mark one of their notifications as read

The notification API was tested using DRF `APIClient`.

The API uses authentication protection through:

```python
IsAuthenticated
```

The notification list and mark-read endpoints protect user data by ensuring users can only access or update their own notifications.

---

## Core Features

### 1. Smart Booking Management

Customers can book services based on:

- branch
- service
- booking date
- booking time
- user account

Bookings form the foundation of the queue process.

---

### 2. Queue Ticket Generation

Each booking can be connected to a queue ticket.

Queue tickets store:

- queue number
- queue type
- queue status
- assigned counter
- creation time
- booking relationship

Examples:

```text
A001 → General Queue
P001 → Priority Queue
```

---

### 3. Priority Queue Management

Smart Q can decide whether a customer belongs in the general queue or priority queue.

Priority logic can consider:

- age
- disability status
- pregnancy status

This supports fairer queue handling.

---

### 4. Branch Management

Branches represent service locations.

Examples:

```text
Kimberley Branch
Pretoria Branch
Cape Town Branch
```

Branches can store:

- code
- name
- address
- city
- opening time
- closing time
- active status

---

### 5. Service Management

Services represent what a customer wants to book.

Examples:

```text
Passport Collection
ID Application
General Enquiry
License Renewal
```

Services store average service time, which supports waiting-time estimation and disruption capacity calculations.

---

### 6. Counter Management

Counters represent service points used by employees.

Counters can support queue operations by helping Smart Q understand active service capacity.

Counter information supports:

- active counter count
- queue movement
- waiting-time calculations
- future staff/counter availability logic

---

### 7. Queue Status Tracking

Queue tickets can move through different statuses:

```text
waiting
serving
completed
no_show
cancelled
```

These statuses allow the system to understand what is happening in the queue.

---

### 8. Queue Operations

The backend has been developed toward operational queue movement.

Important queue operations include:

- call next customer
- mark ticket as serving
- mark ticket as completed
- mark ticket as no-show
- cancel ticket
- update queue movement
- support recalculation after status changes

---

### 9. Waiting-Time Estimation Foundation

Smart Q can estimate queue waiting time using:

```text
people ahead
average service time
active counters
```

A simple waiting-time idea is:

```text
Estimated Wait Time = (People Ahead × Average Service Time) ÷ Active Counter Count
```

This is not yet final AI forecasting, but it creates an important foundation for queue intelligence.

---

### 10. Disruption Handling

Smart Q can now record queue pauses and calculate disruption impact.

The system can answer:

```text
How long was the queue paused?
How many service slots were lost?
Which waiting customers were affected?
Which customers are most at risk of being pushed to another day?
```

This is one of the strongest intelligence features in the system.

---

### 11. Rescheduling Foundation

Smart Q supports reschedule recommendation logic.

The system can:

- create reschedule recommendations
- create reschedule options
- approve a recommendation
- apply an approved recommendation
- move the booking date and time
- generate a new priority queue number
- reset the ticket for the new appointment
- mark the recommendation as applied

---

### 12. Notification System

Smart Q now has a database notification system.

Notifications can store:

- user
- title
- message
- notification type
- related ticket
- related disruption impact
- read/unread state
- creation time

Notifications are created internally by backend workflows such as reschedule confirmation.

---

### 13. API Foundation

Smart Q now uses Django REST Framework.

The API foundation currently exposes notification data.

This prepares the backend for future frontend integration.

---

## Implemented Features

The following features have already been implemented or worked on.

---

### Django Project Setup

- Django project created.
- Virtual environment configured.
- Django installed.
- Initial migrations applied.
- Superuser created.
- Project connected to GitHub.
- `.gitignore` added.
- Project pushed to GitHub.

---

### Django REST Framework Setup

Django REST Framework was installed and registered.

Implemented setup:

- `djangorestframework` installed
- `rest_framework` added to `INSTALLED_APPS`
- `requirements.txt` created/updated
- API foundation merged through pull request

Purpose:

```text
Enable API serializers, API views, permissions, and API testing.
```

---

### Queues App

The `queues` app handles queue tickets and queue-related business logic.

Implemented work includes:

- `QueueTicket` model
- queue type choices
- queue status choices
- queue ticket relationship to booking
- ticket list page
- queue number generation logic
- waiting-time support
- disruption support
- queue operation support

Queue types:

```text
general
priority
```

Queue statuses:

```text
waiting
serving
completed
no_show
cancelled
```

---

### Branches App

The `branches` app handles service locations.

A branch can store:

- branch code
- branch name
- address
- city
- opening time
- closing time
- active status

Branches are important because queue numbers and service flow are branch-specific.

---

### Services App

The `services` app handles services that customers can book.

A service can store:

- service code
- service name
- service description
- average service time
- active status

The `average_service_time` field is important because it supports:

- waiting-time prediction
- lost capacity calculation during disruptions
- future analytics

---

### Bookings App

The `bookings` app handles customer bookings.

A booking connects:

- user
- branch
- service
- booking date
- booking time
- booking status

Bookings are the starting point for queue ticket generation.

---

### Accounts App and Profile Model

The `accounts` app stores customer profile information used in priority decisions.

A profile can store:

- user
- date of birth
- gender
- disability status
- created date

Profile information supports automatic queue type decisions.

---

### Counters App

The `counters` app supports service capacity.

Counters help the system understand how many service points are active.

This supports waiting-time estimation because active counters affect how fast a queue moves.

---

### Automatic Queue Ticket Creation

When a booking is created or saved, the system can create a queue ticket automatically.

Flow:

```text
Booking saved
   ↓
Check whether QueueTicket already exists
   ↓
If no ticket exists, create one
   ↓
Decide queue type
   ↓
Generate queue number
```

This prevents a booking from existing without a queue ticket.

---

### Automatic Queue Number Generation

Smart Q generates customer-friendly queue numbers.

General queue:

```text
A001
A002
A003
```

Priority queue:

```text
P001
P002
P003
```

Queue numbers are generated based on:

- branch
- booking date
- queue type

This means different branches can have their own queue numbering for the same day.

Example:

```text
Kimberley Branch - 2026-06-15 - General
A001, A002, A003

Pretoria Branch - 2026-06-15 - General
A001, A002, A003
```

This is acceptable because each branch has its own queue.

---

### Automatic Priority Decision Logic

Priority status is not simply selected manually by the customer.

The system decides priority using business rules.

A customer can be placed in the priority queue if:

```text
Age >= 55
OR disability_status = True
OR pregnancy-related priority applies
```

This supports fairer queue handling.

---

### Waiting-Time Foundation

Smart Q has a foundation for waiting-time prediction.

The system can use:

```text
queue position
people ahead
average service time
active counters
```

to calculate estimated waiting information.

This allows Smart Q to begin answering:

```text
What position am I in?
How many people are ahead of me?
How long might I wait?
```

This is an early stage of queue intelligence.

---

### Queue Operations

Smart Q has queue movement logic under development.

Supported operational concepts include:

- call next customer
- mark ticket as serving
- mark ticket as completed
- mark ticket as no-show
- cancel ticket
- reset ticket after rescheduling
- assign ticket to counter
- clear assigned counter

These operations allow Smart Q to move from static tickets to an actual queue workflow.

---

### Queue Disruption Tracking

A `QueuePause` model was created to track service-level queue disruptions.

A queue pause is tied to:

```text
branch
service
booking date
start time
end time
reason
active state
```

This allows Smart Q to record when a queue stops moving.

Example:

```text
Passport Collection queue paused at Kimberley Branch on 2026-06-15.
```

---

### Disruption Impact Calculation

Smart Q can calculate:

```text
pause duration
lost service capacity
affected waiting tickets
reschedule-risk tickets
disruption report
```

This allows the system to turn a disruption into operational intelligence.

Example:

```text
Pause duration = 240 minutes
Average service time = 10 minutes
Lost capacity = 24 customers
```

That means about 24 service slots were lost.

---

### Customer Disruption Impact Tracking

A `QueueDisruptionImpact` model was added to store which tickets were affected by a disruption.

Impact types include:

```text
affected
reschedule_risk
```

This means Smart Q can remember:

```text
This ticket was affected.
This ticket is at risk of rescheduling.
This customer has not been notified yet.
```

This is important because calculated results disappear, but database records can be used later for dashboards and notifications.

---

### Notification Model

The `Notification` model stores system notifications.

It includes:

- user
- title
- message
- notification type
- related ticket
- related impact
- read state
- created date

Notification types include:

```text
general
queue_update
disruption
reschedule
```

The `message` field was added so notifications can contain full customer-facing messages, not only short titles.

---

### Reschedule Applied Notification

When an approved reschedule is applied, Smart Q can create a confirmation notification.

Example message:

```text
Your booking has been rescheduled to 2026-06-16 at 08:00:00. Your new queue number is P001.
```

This connects backend rescheduling to customer communication.

---

### Notification APIs

Smart Q now exposes notification data through Django REST Framework.

Implemented notification endpoints:

```text
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

These endpoints support:

- viewing notifications
- showing unread count
- marking one notification as read

---

## Planned Features

The following features are planned for future development:

- Branch API endpoints
- Service API endpoints
- Booking API endpoints
- Customer registration/login frontend
- Customer booking form
- Customer dashboard
- Employee dashboard
- Branch manager dashboard
- Admin dashboard improvements
- Queue ticket API endpoints
- Queue operation API endpoints
- Mark all notifications as read endpoint
- Notification filtering and pagination
- Live queue position tracking
- Real-time updates using WebSockets
- External email notifications
- SMS or WhatsApp notifications
- Customer feedback system
- Analytics dashboard
- Historical reports
- AI-assisted waiting-time forecasting

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django |
| API Framework | Django REST Framework |
| Language | Python |
| Development Database | SQLite |
| Future Production Database | PostgreSQL |
| Frontend | Django Templates currently; frontend/mobile-friendly web planned |
| Admin Tool | Django Admin |
| Version Control | Git and GitHub |
| API Testing | DRF APIClient |
| Future Real-Time Updates | WebSockets |
| Future Notifications | Email, SMS, WhatsApp, in-app notifications |
| Future Forecasting | AI/ML-based waiting-time prediction |

---

## System Architecture

Current simplified architecture:

```text
Browser / API Client
   ↓
Django URLs
   ↓
Django Views / DRF API Views
   ↓
Serializers
   ↓
Business Logic / Service Functions
   ↓
Django Models / ORM
   ↓
Database
```

Notification API architecture:

```text
GET /api/v1/notifications/
   ↓
smartq/urls.py
   ↓
notifications/api_urls.py
   ↓
NotificationIsAPIView
   ↓
NotificationSerializer
   ↓
JSON Response
```

Unread count API architecture:

```text
GET /api/v1/notifications/unread-count/
   ↓
UnreadNotificationCountAPIView
   ↓
get_unread_notification_count(user)
   ↓
Response: {"unread_count": number}
```

Mark-read API architecture:

```text
PATCH /api/v1/notifications/<id>/mark-read/
   ↓
MarkNotificationReadAPIView
   ↓
Find notification belonging to request.user
   ↓
mark_notification_as_read(notification)
   ↓
Return updated notification
```

Future platform architecture:

```text
Customer Web App
Employee Dashboard
Admin Dashboard
        ↓
Django REST API
        ↓
Booking Service
Queue Service
Counter Service
Priority Decision Logic
Waiting-Time Service
Disruption Service
Rescheduling Service
Notification Service
Analytics Service
        ↓
Database
```

---

## Current Django Apps

### `accounts`

Handles customer profile data.

Main responsibility:

```text
Store extra user information needed for queue decisions.
```

Main model:

```text
Profile
```

---

### `branches`

Handles service locations.

Main responsibility:

```text
Store branch/location information.
```

Main model:

```text
Branch
```

---

### `services`

Handles services customers can book.

Main responsibility:

```text
Store service details and average service time.
```

Main model:

```text
Service
```

---

### `bookings`

Handles customer bookings.

Main responsibility:

```text
Connect user, branch, service, date, and time.
```

Main model:

```text
Booking
```

---

### `queues`

Handles queue tickets and queue business logic.

Main responsibilities:

```text
queue tickets
queue numbers
queue statuses
waiting-time foundation
disruption tracking
queue movement
```

Important models include:

```text
QueueTicket
QueuePause
QueueDisruptionImpact
```

---

### `counters`

Handles service counters.

Main responsibility:

```text
Track counter/service capacity for queue operations and waiting-time estimation.
```

---

### `notifications`

Handles in-app notifications and notification APIs.

Main responsibilities:

```text
store notifications
create notification records
count unread notifications
mark notifications as read
expose notification APIs
```

Main model:

```text
Notification
```

Important files:

```text
notifications/models.py
notifications/services.py
notifications/serializers.py
notifications/api_views.py
notifications/api_urls.py
```

---

### `rescheduling`

Handles reschedule recommendations and application logic.

Main responsibilities:

```text
create reschedule recommendations
store reschedule options
approve recommendations
apply approved reschedules
trigger reschedule confirmation notifications
```

Important concepts:

```text
RescheduleRecommendation
RescheduleOption
apply approved reschedule workflow
```

---

## Database and Model Relationships

Current high-level relationship structure:

```text
User
 ├── Profile
 ├── Booking
 │    ├── Branch
 │    ├── Service
 │    └── QueueTicket
 │
 └── Notification
```

Queue disruption relationship structure:

```text
QueuePause
 ├── Branch
 ├── Service
 ├── Booking Date
 └── QueueDisruptionImpact
       └── QueueTicket
```

Rescheduling relationship structure:

```text
Booking
 └── QueueTicket
      ↓
RescheduleRecommendation
 └── RescheduleOption
```

Notification relationship structure:

```text
User
 └── Notification
      ├── related_ticket
      └── related_impact
```

---

## Queue Number Rules

Smart Q uses simple queue numbers.

### General Queue

```text
A001
A002
A003
```

### Priority Queue

```text
P001
P002
P003
```

The prefix shows the queue type:

| Prefix | Meaning |
|---|---|
| A | General queue |
| P | Priority queue |

Queue numbers are generated using:

```text
branch
booking date
queue type
```

This prevents one branch’s numbering from interfering with another branch’s queue.

---

## Priority Queue Logic

Priority status is decided by the system using business rules.

A customer can receive a priority ticket if:

```text
Age >= 55
OR disability status is true
OR pregnancy-related priority applies
```

Priority decision flow:

```text
Get booking
   ↓
Get user profile
   ↓
Calculate age
   ↓
Check age rule
   ↓
Check disability rule
   ↓
Check pregnancy rule
   ↓
Return priority or general
```

Example results:

| Customer Details | Result |
|---|---|
| Age 60 | Priority ticket |
| Disability status true | Priority ticket |
| Pregnancy priority applies | Priority ticket |
| No priority rule applies | General ticket |

---

## Waiting-Time Intelligence

Smart Q’s waiting-time foundation uses:

```text
people ahead
average service time
active counters
```

Simple idea:

```text
Estimated Wait Time = (People Ahead × Average Service Time) ÷ Active Counter Count
```

The system can begin producing:

```text
queue position
people ahead
estimated waiting time
```

This is not yet the final AI forecasting system.

It is the first rule-based waiting-time foundation.

Future AI forecasting may use:

```text
historical service data
past delays
no-show rates
branch demand
time of day
day of week
staff availability
```

---

## Queue Operations

Queue operations allow Smart Q to behave like a real queue system.

Important operations include:

```text
call next customer
mark as serving
mark as completed
mark as no-show
cancel ticket
assign counter
clear counter
reset after reschedule
```

These operations are important because a queue is not only data.

A real queue moves.

Smart Q must know who is waiting, who is being served, and who has already left the queue.

---

## Disruption and Rescheduling Intelligence

Smart Q includes disruption intelligence.

A disruption is when a queue stops moving or loses service capacity.

Examples:

```text
System down
Network failure
Staff unavailable
Service paused
Counter capacity reduced
```

Smart Q can record a queue pause through `QueuePause`.

It can calculate:

```text
pause duration
lost service capacity
affected customers
reschedule-risk customers
```

Example:

```text
Pause duration = 240 minutes
Average service time = 10 minutes
Lost capacity = 24 customers
```

This means the system lost about 24 service slots.

Smart Q can then identify customers most at risk of not being served on the same day.

This does not automatically reschedule them immediately.

It first identifies risk.

That is safer.

---

## Notification System

Smart Q has a database notification system.

Notification fields include:

```text
user
title
message
notification_type
related_ticket
related_impact
is_read
created_at
```

Example notification:

```text
Title:
Reschedule confirmed

Message:
Your booking has been rescheduled to 2026-06-16 at 08:00:00. Your new queue number is P001.
```

Notification types include:

```text
general
queue_update
disruption
reschedule
```

Current notification capabilities:

```text
create notification for disruption impact
create notification for applied reschedule
get user notifications
get unread notifications
count unread notifications
mark one notification as read
```

---

## API Endpoints

### Notification List

```http
GET /api/v1/notifications/
```

Purpose:

```text
Return the logged-in user’s notifications.
```

Example response:

```json
[
  {
    "id": 1,
    "title": "Reschedule confirmed",
    "message": "Your booking has been rescheduled to 2026-06-16 at 08:00:00. Your new queue is P001.",
    "notification_type": "reschedule",
    "is_read": false,
    "created_at": "2026-06-20T00:51:42.190144Z"
  }
]
```

Security:

```text
Only authenticated users can access this endpoint.
Users only receive their own notifications.
```

---

### Unread Notification Count

```http
GET /api/v1/notifications/unread-count/
```

Purpose:

```text
Return the logged-in user’s unread notification count.
```

Example response:

```json
{
  "unread_count": 1
}
```

Security:

```text
Only authenticated users can access this endpoint.
The count is based on request.user.
```

---

### Mark Notification as Read

```http
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

Example:

```http
PATCH /api/v1/notifications/1/mark-read/
```

Purpose:

```text
Mark one notification as read.
```

Security:

```text
Only authenticated users can access this endpoint.
Users can only mark their own notifications as read.
```

Important logic:

```python
get_object_or_404(Notification, id=notification_id, user=request.user)
```

This prevents a user from marking another user’s notification as read.

---

## Main User Roles

### Customer

A customer will be able to:

- create an account
- log in
- manage profile information
- choose a branch
- choose a service
- make a booking
- receive a queue ticket
- view queue status
- receive notifications
- view reschedule updates
- submit feedback

---

### Employee

An employee will be able to:

- view waiting customers
- call next customer
- mark customer as serving
- mark customer as completed
- mark customer as no-show
- manage assigned counter activity

---

### Branch Manager

A branch manager will be able to:

- monitor branch queues
- view service capacity
- handle queue pauses
- view disruption impact
- manage reschedule decisions
- view reports

---

### Admin

An admin will be able to:

- manage users
- manage branches
- manage services
- manage bookings
- manage queues
- manage counters
- view notifications
- monitor system state
- review reports

---

## Project Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Katlegojack/SmartQ.git
cd SmartQ
```

---

### 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv venv
```

macOS/Linux:

```bash
python3 -m venv venv
```

---

### 3. Activate the Virtual Environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the script:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

---

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing, install the main dependencies manually:

```bash
pip install django djangorestframework
```

Then freeze dependencies:

```bash
pip freeze > requirements.txt
```

---

### 5. Apply Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

### 6. Create a Superuser

```bash
python manage.py createsuperuser
```

---

### 7. Run the Development Server

```bash
python manage.py runserver
```

Project URL:

```text
http://127.0.0.1:8000/
```

Admin URL:

```text
http://127.0.0.1:8000/admin/
```

Notification API URL:

```text
http://127.0.0.1:8000/api/v1/notifications/
```

---

## Running the Project

Common commands:

```bash
python manage.py runserver
```

```bash
python manage.py check
```

```bash
python manage.py makemigrations
```

```bash
python manage.py migrate
```

```bash
python manage.py createsuperuser
```

---

## Admin Usage

Django Admin is currently used heavily for testing backend logic.

Recommended admin testing order:

```text
Create user
↓
Create profile
↓
Create branch
↓
Create service
↓
Create booking
↓
Confirm queue ticket creation
↓
Test queue number
↓
Test queue type
↓
Test queue movement
↓
Test disruption/rescheduling logic
↓
Test notification creation
```

---

## API Testing

APIs can be tested using DRF `APIClient`.

Example:

```python
from rest_framework.test import APIClient
from notifications.models import Notification

notification = Notification.objects.first()
user = notification.user

client = APIClient()
client.force_authenticate(user=user)

response = client.get(
    "/api/v1/notifications/",
    HTTP_HOST="localhost"
)

print(response.status_code)
print(response.data)
```

Important testing note:

DRF `APIClient` may use a default host called:

```text
testserver
```

If Django rejects it with:

```text
Invalid HTTP_HOST header: 'testserver'
```

use:

```python
HTTP_HOST="localhost"
```

inside the test request.

---

## Development Workflow

Smart Q uses a professional Git workflow.

Recommended flow:

```text
checkout main
pull latest main
create feature branch
make changes
run checks
test feature
commit
push branch
create pull request
review files changed
squash merge
checkout main
pull latest main
confirm clean status
```

Example:

```bash
git checkout main
git pull origin main
git checkout -b feature/example-feature
```

After changes:

```bash
python manage.py check
git status
git add .
git commit -m "Add example feature"
git push -u origin feature/example-feature
```

After PR merge:

```bash
git checkout main
git pull origin main
git status
python manage.py check
```

Important rule:

```text
Do not continue new work on a branch that has already been merged.
Create a fresh branch from updated main.
```

---

## Security and Safety Considerations

Smart Q handles sensitive customer and operational data.

Security matters from the beginning.

### Authentication

Users must be authenticated before accessing private API data.

Notification APIs use:

```python
IsAuthenticated
```

---

### Authorization

Authentication answers:

```text
Who are you?
```

Authorization answers:

```text
What are you allowed to do?
```

For example, a user should only access their own notifications.

This is enforced with:

```python
Notification.objects.filter(user=self.request.user)
```

and:

```python
get_object_or_404(Notification, id=notification_id, user=request.user)
```

---

### User Data Protection

Sensitive data may include:

```text
date of birth
disability status
pregnancy-related priority
booking history
queue history
notifications
rescheduling records
```

This data must not be exposed publicly.

---

### Queue Safety

Smart Q should avoid unrealistic customer promises.

The system should not promise:

```text
You will definitely be served today.
```

if disruptions or capacity problems make that uncertain.

That is why disruption impact and reschedule-risk detection are important.

---

### API Safety

Dangerous actions such as:

```text
pause queue
resume queue
call next customer
apply reschedule
complete ticket
```

should have stronger permission checks later.

These should not be available to normal customers.

---

## Known Limitations

Current limitations:

- Frontend is still limited.
- Most operational testing is still done through Django Admin and shell.
- Only notification APIs are currently exposed.
- Branch and service APIs are planned next.
- Booking API is not implemented yet.
- Queue operation APIs are not implemented yet.
- API pagination is not implemented yet.
- Notification filtering by type is not implemented yet.
- Mark all notifications as read is not implemented yet.
- External SMS/email/WhatsApp notifications are not implemented yet.
- Real-time WebSocket updates are not implemented yet.
- Production database setup is not complete yet.
- Production deployment configuration is not complete yet.
- Role-based API permissions still need to be expanded.
- Automated test suite still needs to be improved.

---

## Roadmap

### Phase 1: Backend Foundation

- Django setup
- GitHub setup
- Modular Django apps
- User profiles
- Branch model
- Service model
- Booking model
- Queue ticket model
- Queue number generation
- Priority logic
- Admin testing

Status:

```text
Mostly implemented
```

---

### Phase 2: Queue Operations

- Call next customer
- Mark as serving
- Mark as completed
- Mark as no-show
- Cancel ticket
- Counter assignment
- Counter capacity logic

Status:

```text
In progress / partially implemented
```

---

### Phase 3: Waiting-Time Engine

- Queue position
- People ahead
- Average service time
- Active counter count
- Estimated waiting time
- Recalculation after queue movement

Status:

```text
Foundation implemented
```

---

### Phase 4: Disruption Handling

- Queue pause model
- Pause duration
- Lost service capacity
- Affected customers
- Reschedule-risk detection
- Disruption report
- Disruption impact records

Status:

```text
Foundation implemented
```

---

### Phase 5: Rescheduling

- Reschedule recommendations
- Reschedule options
- Approval workflow
- Apply approved reschedule
- New queue number generation
- Reschedule confirmation notification

Status:

```text
Foundation implemented
```

---

### Phase 6: Notifications

- Notification model
- Notification message field
- Notification services
- Reschedule confirmation notification
- Notification list API
- Unread count API
- Mark notification as read API

Status:

```text
Core foundation implemented
```

---

### Phase 7: API Expansion

Next planned APIs:

```text
Branch API
Service API
Booking API
Queue Ticket API
Queue Operation APIs
Rescheduling APIs
```

Status:

```text
Started with notification APIs
```

---

### Phase 8: Frontend Integration

Planned frontend features:

- customer dashboard
- booking form
- ticket page
- notification bell
- queue status view
- employee dashboard
- manager dashboard

Status:

```text
Planned
```

---

### Phase 9: Real-Time Updates

Future real-time features:

- live queue position
- live queue status changes
- live counter updates
- real-time notifications

Possible technology:

```text
Django Channels / WebSockets
```

Status:

```text
Planned
```

---

### Phase 10: Analytics and AI

Future intelligence features:

- historical waiting-time reports
- no-show analysis
- disruption analytics
- branch performance reports
- demand forecasting
- AI-assisted waiting-time prediction

Status:

```text
Planned
```

---

## Author

**Katlego Mmako**

Smart Q is being developed as a practical Django software engineering project focused on backend development, queue management, system design, API development, disruption intelligence, rescheduling workflows, and future AI-assisted waiting-time prediction.

---

## Final Project Statement

Smart Q is being built to solve a real-world problem: people lose too much time in unclear, unmanaged queues.

The project is growing from a Django backend into a queue intelligence platform that can support digital bookings, fair queue handling, waiting-time estimation, disruption management, customer notifications, and future analytics.

The current backend already includes strong foundations for bookings, queues, disruptions, rescheduling, notifications, and APIs.

The next stage is to continue expanding the API layer so the frontend can interact with the system properly.

Smart Q’s mission is simple:

```text
Make queues fairer, smarter, and more respectful of people’s time.
```
