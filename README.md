# Smart Q

**Where Time Meets Priority**

Smart Q is a Django-based Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and efficient. The system allows customers to book services at a branch, receive a queue ticket, track their queue status, and be handled according to fair priority rules.

The long-term goal of Smart Q is to reduce unnecessary physical waiting, help organizations manage customer flow, and give customers better visibility into when they will be assisted.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Current Project Status](#current-project-status)
- [Core Features](#core-features)
- [Implemented Features](#implemented-features)
- [Planned Features](#planned-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Current Django Apps](#current-django-apps)
- [Database Design](#database-design)
- [Queue Number Rules](#queue-number-rules)
- [Priority Queue Logic](#priority-queue-logic)
- [Main User Roles](#main-user-roles)
- [Project Setup](#project-setup)
- [Running the Project](#running-the-project)
- [Admin Usage](#admin-usage)
- [Development Workflow](#development-workflow)
- [Security and Safety Considerations](#security-and-safety-considerations)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Author](#author)

---

## Project Overview

Smart Q is not just a basic queue management system. It is being built as a Queue Intelligence Platform that combines:

- Appointment booking
- Queue ticket generation
- General and priority queue handling
- Branch and service management
- Customer profile information
- Automatic queue type decisions
- Future waiting-time prediction
- Future notifications and analytics

The system is currently being developed using Django as a modular monolith. This means the project stays inside one Django backend, but responsibilities are separated into smaller Django apps such as `accounts`, `branches`, `services`, `bookings`, and `queues`.

---

## Problem Statement

Many organizations still rely on physical queues where customers wait for long periods without knowing when they will be assisted. This creates several problems:

- Customers waste time waiting physically.
- Organizations struggle with overcrowding.
- Staff cannot easily manage queue flow.
- Priority customers may not be handled fairly.
- Waiting times are often unclear or unrealistic.
- Delays and system interruptions are not communicated properly.

Smart Q aims to solve these problems by making queues digital, trackable, and predictable.

---

## Solution

Smart Q allows a customer to book a service at a branch. Once the booking is created, the system can automatically generate a queue ticket and decide whether the customer belongs in the general queue or priority queue.

A simplified flow is:

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
A001 or P001
```

This gives the system the foundation to support live queue tracking, estimated waiting times, and fair queue management.

---

## Current Project Status

Smart Q is currently in active development.

The project already has a working Django foundation with models, relationships, migrations, admin testing, automatic queue ticket generation, and automatic priority decision logic.

Current status:

- Backend foundation is in progress.
- Django Admin is being used for testing models and business logic.
- Customer-facing frontend is still limited.
- Waiting-time prediction is planned but not fully implemented yet.
- Notifications, analytics, and real-time queue updates are planned future features.

---

## Core Features

### 1. Smart Booking Management

Customers will be able to book services based on branch, service, date, and time.

### 2. Queue Ticket Generation

Each booking can generate a queue ticket automatically.

Examples:

```text
A001 → General Queue
P001 → Priority Queue
```

### 3. Priority Queue Management

Smart Q can decide whether a customer should be placed in the general queue or priority queue using customer profile and booking information.

### 4. Branch Management

Organizations can manage different service locations such as branches, offices, departments, or service centres.

### 5. Service Management

Each service can have its own average service time, which will later support waiting-time calculations.

### 6. Queue Status Tracking

Queue tickets use statuses such as:

- Waiting
- Serving
- Completed
- No Show
- Cancelled

### 7. Future Waiting-Time Prediction

The system will later estimate waiting time using queue length, average service time, and active staff or counters.

Example formula:

```text
Estimated Wait Time = (People Ahead × Average Service Time) ÷ Active Staff Count
```

### 8. Future Disruption Handling

Smart Q is designed to eventually handle delays, outages, staff shortages, and queue pauses by recalculating capacity and rescheduling affected customers.

---

## Implemented Features

The following features have already been worked on:

### Django Project Setup

- Django project created.
- Virtual environment configured.
- Initial migrations applied.
- Project connected to GitHub.

### Queues App

- `QueueTicket` model created.
- Queue types added:
  - General
  - Priority
- Queue statuses added:
  - Waiting
  - Serving
  - Completed
  - No Show
  - Cancelled
- Queue tickets registered in Django Admin.
- Ticket list page created at `/tickets/`.

### Branches App

- `Branch` model created.
- Branches can store:
  - Branch code
  - Name
  - Address
  - City
  - Opening time
  - Closing time
  - Active status

### Services App

- `Service` model created.
- Services can store:
  - Service code
  - Name
  - Description
  - Average service time
  - Active status

### Bookings App

- `Booking` model created.
- Booking connects:
  - User
  - Branch
  - Service
  - Booking date
  - Booking time
  - Booking status

### QueueTicket and Booking Relationship

- Each `QueueTicket` is connected to a `Booking`.
- The relationship is one-to-one.
- One booking should generate one queue ticket.

### Automatic Queue Ticket Creation

When a booking is saved through Django Admin, the system checks whether a queue ticket already exists.

If no queue ticket exists, the system automatically creates one.

```text
Booking saved
   ↓
Check if QueueTicket exists
   ↓
Create QueueTicket automatically
   ↓
Generate queue number
```

### Automatic Queue Number Generation

The system generates queue numbers automatically.

Rules:

- General queue uses `A` prefix.
- Priority queue uses `P` prefix.
- Numbers are formatted using three digits.
- Examples: `A001`, `A002`, `P001`, `P002`.

### Accounts App and Profile Model

A profile model was added to store extra customer information.

The profile stores:

- User
- Date of birth
- Gender
- Disability status
- Created date

### Automatic Priority Decision Logic

The system can now decide whether a booking should be general or priority.

A customer is placed in the priority queue if:

```text
Age >= 55
OR disability_status = True
OR gender = Female AND is_pregnant = True
```

If none of these rules apply, the customer receives a general queue ticket.

---

## Planned Features

The following features are planned for future versions:

- Customer registration and login pages
- Customer booking form
- Customer profile creation during registration
- Employee dashboard
- Branch manager dashboard
- Admin dashboard improvements
- Live queue position tracking
- Waiting-time estimation
- Counter/staff management
- Queue pause and resume functionality
- Delay notifications
- Email notifications
- SMS notifications
- Customer feedback system
- Analytics dashboard
- Reports for waiting time, no-shows, staff performance, and customer satisfaction
- Real-time updates using WebSockets
- Future AI-powered waiting-time forecasting

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django |
| Language | Python |
| Database | SQLite for development |
| Future Production Database | PostgreSQL |
| Frontend | Django Templates currently; mobile-friendly web planned |
| Admin Tool | Django Admin |
| Version Control | Git and GitHub |
| Future Real-Time Updates | WebSockets |
| Future Notifications | Email, SMS, and in-app notifications |

---

## System Architecture

Current simplified architecture:

```text
User Browser
   ↓
Django URLs
   ↓
Django Views
   ↓
Business Logic / Service Functions
   ↓
Django Models / ORM
   ↓
Database
```

Future platform architecture:

```text
Customer Web App
Employee Dashboard
Admin Dashboard
        ↓
Django Backend
        ↓
Booking Service
Queue Service
Priority Decision Logic
Prediction Service
Notification Service
Analytics Service
        ↓
Database
```

---

## Current Django Apps

### `accounts`

Handles user profile data needed for queue decisions.

Main model:

- `Profile`

### `branches`

Handles service locations.

Main model:

- `Branch`

### `services`

Handles services that customers can book.

Main model:

- `Service`

### `bookings`

Handles customer bookings.

Main model:

- `Booking`

### `queues`

Handles queue tickets, queue numbers, statuses, and queue-related business logic.

Main model:

- `QueueTicket`

Important service file:

```text
queues/services.py
```

This file contains queue business logic such as:

- Age calculation
- Queue type decision
- Queue number generation
- Queue ticket creation

---

## Database Design

Current relationship structure:

```text
User
 └── Profile

User
 └── Booking
      ├── Branch
      ├── Service
      └── QueueTicket
```

Detailed relationship flow:

```text
User
   ↓
Booking
   ├── Branch
   ├── Service
   └── QueueTicket
```

### Main Entities

| Entity | Purpose |
|---|---|
| User | Stores authentication information |
| Profile | Stores customer details used for priority decisions |
| Branch | Stores branch/location information |
| Service | Stores services that customers can book |
| Booking | Stores the customer's service booking |
| QueueTicket | Stores queue number, queue type, and queue status |

---

## Queue Number Rules

Smart Q uses simple customer-friendly queue numbers.

### General Queue
Example 
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

### Queue Number Logic

Queue numbers are generated based on:

- Branch
- Booking date
- Queue type

This means different branches can have their own queue numbers for the same day.

Example:

```text
Kimberley Branch - 2026-06-15 - General
A001, A002, A003

Pretoria Branch - 2026-06-15 - General
A001, A002, A003
```

This is acceptable because the queues belong to different branches.

---

## Priority Queue Logic

Priority status is not selected manually by the customer.

The system decides priority using business rules.

### Priority Conditions

A booking becomes priority if at least one of these conditions is true:

1. The customer is 55 years or older.
2. The customer has disability status.
3. The customer is female and currently pregnant for that booking.

### Priority Decision Flow

```text
Get booking
   ↓
Get user profile
   ↓
Calculate age from date of birth
   ↓
Check age rule
   ↓
Check disability rule
   ↓
Check pregnancy rule
   ↓
Return Priority or General
```

### Example Results

| Customer Details | Result |
|---|---|
| Age 60 | Priority Ticket: `P001` |
| Disability status is true | Priority Ticket: `P001` |
| Female and pregnant | Priority Ticket: `P001` |
| No priority rule applies | General Ticket: `A001` |

---

## Main User Roles

### Customer

A customer will be able to:

- Create an account
- Log in
- Choose a branch
- Choose a service
- Book a slot
- View their ticket
- Track their queue status
- Receive notifications
- Submit feedback

### Employee

An employee will be able to:

- View waiting customers
- Call the next customer
- Mark a customer as being assisted
- Mark a customer as completed
- Mark a customer as no-show
- Report delays

### Branch Manager

A branch manager will be able to:

- Monitor branch queues
- Manage staff availability
- Pause or resume queues
- Handle delays
- View branch reports
- Manage rescheduling

### Admin

An admin will be able to:

- Manage users
- Manage branches
- Manage services
- Manage system configuration
- View platform-wide reports

---
More backend features from day10 + additional documentation. 



## Project Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Katlegojack/SmartQ.git
cd SmartQ
```

### 2. Create a Virtual Environment

#### Windows PowerShell

```powershell
python -m venv venv
```

#### macOS / Linux

```bash
python3 -m venv venv
```

### 3. Activate the Virtual Environment

#### Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:

```powershell
.\venv\Scripts\Activate.ps1
```

#### macOS / Linux

```bash
source venv/bin/activate
```

### 4. Install Dependencies

If a `requirements.txt` file exists:

```bash
pip install -r requirements.txt
```

If the project does not yet have a `requirements.txt`, install Django manually:

```bash
pip install django
```

After installing packages, you can create a requirements file using:

```bash
pip freeze > requirements.txt
```

### 5. Apply Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create a Superuser

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account.

### 7. Run the Development Server

```bash
python manage.py runserver
```

Open the project in the browser:

```text
http://127.0.0.1:8000/
```

Open Django Admin:

```text
http://127.0.0.1:8000/admin/
```

Open the queue ticket list page:

```text
http://127.0.0.1:8000/tickets/
```

---

## Running the Project

Common development commands:

```bash
python manage.py runserver
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

Check project status before and after changes:

```bash
git status
```

---

## Admin Usage

Django Admin is currently used to test the backend logic.

Recommended testing order:

1. Create a user.
2. Create a profile for the user.
3. Create a branch.
4. Create a service.
5. Create a booking.
6. Save the booking.
7. Confirm that a queue ticket is automatically created.
8. Confirm that the ticket number is generated as `A001` or `P001` depending on the priority rules.

---

## Development Workflow

Recommended Git workflow:

### Check status before starting

```bash
git status
```

### Create a feature branch

```bash
git checkout -b feature/feature-name
```

Example:

```bash
git checkout -b feature/waiting-time-engine
```

### Add changes

```bash
git add .
```

### Commit changes

```bash
git commit -m "Add waiting time estimation logic"
```

### Push branch

```bash
git push origin feature/feature-name
```

### Merge through GitHub

Use a pull request to review and merge changes into `main`.

---

## Security and Safety Considerations

Smart Q handles sensitive information, so security and safety are important.

### Security Principles

- Users must be authenticated.
- Users should only access their own bookings.
- Staff should only manage assigned branch queues.
- Admin permissions should be limited to trusted users.
- Sensitive profile information should not be exposed publicly.
- Queue numbers and priority status should be generated by the system, not manually controlled by customers.

### Sensitive Data

The system may store sensitive data such as:

- Date of birth
- Disability status
- Pregnancy status
- Booking history

This information should only be used where necessary and should not be displayed publicly.

### Safety Principles

Smart Q should avoid giving customers false promises.

For example, the system should not say:

```text
You will be assisted today.
```

if delays, capacity, or staff shortages make that impossible.

The long-term system should recalculate waiting times and reschedule customers when service delivery becomes unrealistic.

---

## Known Limitations

Current limitations:

- Most testing is still done through Django Admin.
- The full customer-facing booking flow is not complete yet.
- The employee dashboard is not complete yet.
- The waiting-time prediction engine is not complete yet.
- Real-time queue updates are not implemented yet.
- Notifications are not implemented yet.
- The pregnancy field may still appear in Django Admin for all users, even though the frontend should eventually show it only when relevant.
- Backend validation for pregnancy status still needs to be improved.
- The project currently uses SQLite for development.

---

## Roadmap

### Phase 1: Backend Foundation

- Django setup
- QueueTicket model
- Branch model
- Service model
- Booking model
- Profile model
- Model relationships
- Admin testing
- Automatic queue ticket generation
- Automatic priority decision logic

### Phase 2: Customer Booking Flow

- Customer registration
- Customer login
- Profile creation
- Branch selection
- Service selection
- Booking form
- My Ticket page

### Phase 3: Employee Queue Dashboard

- View waiting customers
- Call next customer
- Mark customer as serving
- Mark customer as completed
- Mark customer as no-show
- Pause counter

### Phase 4: Waiting-Time Engine

- Add active staff/counter tracking
- Count people ahead
- Use average service time
- Calculate estimated wait time
- Recalculate wait time after queue movement

### Phase 5: Notifications and Disruptions

- Booking confirmation notifications
- Delay alerts
- Queue pause alerts
- Rescheduling notices
- Disruption recovery logic

### Phase 6: Analytics and Feedback

- Customer feedback
- Waiting-time reports
- No-show reports
- Branch performance reports
- Staff performance insights

### Phase 7: AI Forecasting

- Collect historical queue data
- Generate synthetic test data if needed
- Train waiting-time prediction models
- Forecast demand and busy periods

---

## Author

**Katlego Mmako**

Smart Q is being developed as a practical Django software engineering project focused on backend development, system design, queue management, automation, and future intelligent waiting-time prediction.

---

## Project Vision

Smart Q is more than a queue system.

It is a platform designed to give people their time back by making queues predictable, transparent, fair, and easier to manage.

