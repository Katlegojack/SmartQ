# Smart Q - Day 41 Engineering Documentation

## Frontend Foundation and Design System

## 1. Day 41 goal

Day 41 starts the Smart Q frontend phase after backend v1 completion.

The objective is to establish a disciplined frontend foundation before role-specific screens are built.

The frontend stack is intentionally simple:

```text
HTML5
CSS3
Vanilla JavaScript with ES modules
Django templates/static assets
```

No React, Tailwind, Bootstrap or frontend framework is introduced.

---

## 2. Design direction

Smart Q must look like a serious queue-management and civic-operations product rather than a generic template or visually noisy prototype.

The approved visual direction is:

```text
white-dominant surfaces
light blue structural backgrounds
medium blue primary actions
small amounts of green for positive/active states
dark blue-grey text
subtle borders
restrained shadows
modest corner radii
consistent spacing
```

The interface deliberately avoids:

```text
emoji-based interface decoration
large gradients as primary decoration
glassmorphism
oversized rounded cards
floating decorative blobs
excessive shadows
random dashboard tiles
inconsistent page styles
fake AI labels
```

---

## 3. Color system

Day 41 introduces named CSS variables so future screens reuse one controlled palette.

Primary values include:

```text
#FFFFFF  main white
#F4FAFF  light blue page surface
#EAF6FF  light blue status/surface
#2878C8  primary action blue
#163B5C  dark blue text/navigation
#2F9E67  positive green
```

Green is intentionally limited to success, availability, active and healthy states.

---

## 4. Shared component language

The first design system includes reusable patterns for:

```text
brand/header
primary navigation
buttons
status badges
panels
forms
help text
tables
queue metrics
status indicators
toasts
responsive layout
```

The objective is not to build every future screen on Day 41. It is to ensure every future screen uses the same visual grammar.

---

## 5. Layout principles

The page foundation uses a centered maximum-width container and responsive grid behavior.

Desktop layouts may use multi-column structures where appropriate, while mobile layouts collapse into one readable column.

The system avoids arbitrary spacing. Repeated spacing, radius and color values are controlled through CSS variables and reusable classes.

---

## 6. Accessibility foundation

Day 41 includes basic accessibility requirements from the beginning:

```text
semantic HTML structure
skip-to-content link
visible keyboard focus states
proper table headers
accessible navigation labels
button elements for actions
reduced-motion support
responsive text/layout behavior
```

Accessibility is treated as a structural requirement rather than a final visual polish task.

---

## 7. Frontend/backend boundary

The frontend will not recreate Smart Q business rules in JavaScript.

The backend remains authoritative for:

```text
check-in timing
priority rules
booking capacity
live ETA
roles and permissions
queue state
reporting access
final-state validation
```

JavaScript is responsible for presenting backend state, collecting user input and coordinating API calls.

This protects the stable backend contract completed on Day 40.

---

## 8. Day 41 landing/foundation page

A new root frontend page establishes the visual system and proves Django can serve the frontend assets.

The page demonstrates:

```text
Smart Q branding
hero hierarchy
primary and secondary actions
queue status presentation
status badges
form controls
operational table layout
responsive behavior
```

The content is intentionally a foundation preview rather than a fake fully functional dashboard.

Authentication actions display a temporary informational message because authentication interface work begins on Day 42.

---

## 9. Static asset structure

Day 41 introduces shared frontend assets:

```text
static/css/smartq.css
static/js/app.js
templates/frontend/index.html
```

Future JavaScript should be split into focused modules as functionality grows instead of expanding one large script indefinitely.

Planned structure:

```text
static/js/api/
static/js/auth/
static/js/components/
static/js/pages/
static/js/utils/
```

---

## 10. Django integration

The root page is served through Django templates while the existing API routes remain unchanged.

Django static-file discovery is configured to include the project-level `static/` directory.

The existing backend API remains under `/api/v1/` and is not moved or renamed for frontend convenience.

---

## 11. Automated verification

Day 41 adds focused tests proving that:

```text
the frontend home route returns HTTP 200
Smart Q frontend content renders
shared CSS is referenced
shared JavaScript is referenced
CSS and JavaScript are discoverable by Django staticfiles
```

The focused frontend suite is added to GitHub Actions before the full regression suite.

---

## 12. Product consistency rules

The following rules apply to the frontend phase:

```text
No emoji in the interface.
No fake data presented as real operational state.
No frontend-only authorization decisions.
No duplicate implementation of backend business rules.
No one-off visual language per role.
No unnecessary frontend framework.
```

Role-specific pages may differ in information density, but they must still look like one Smart Q product.

---

## 13. Day 41 completion boundary

Day 41 is complete when:

```text
frontend foundation route exists
shared design-system CSS exists
shared JavaScript entry point exists
responsive foundation is established
accessibility baseline is present
focused frontend tests pass
full backend regression remains green
exact branch head passes GitHub Actions
```

---

## 14. Next milestone - Day 42

Day 42 will build the authentication and application shell layer:

```text
CSRF bootstrap
login
registration
logout
session restoration
current-user loading
role-aware routing
shared authenticated shell
global API/error handling
```

The Day 41 design system becomes the visual base for those screens.
