# Smart Q — Day 58: Live Service Timing and Forecasting Data

## Problem

The customer live queue could show `0 min` while another customer was already being served. The old calculation considered only waiting tickets ahead and multiplied that count by a static service average. It did not model the remaining work already occupying a counter, and it did not preserve the difference between predicted service time and actual service time.

## Engineering goal

Make queue timing operationally live while preserving high-quality observations for a future forecasting model.

Smart Q now separates two concepts:

1. **Live operational state** — what is happening at the counter right now.
2. **Learning data** — what the system predicted versus what actually happened.

## User-facing time unit

Smart Q presents queue and service timing to users in **minutes**, not seconds.

Examples:

```text
Estimated wait: 15 min
Service elapsed: 7 min
Target remaining: 13 min
```

Second-resolution timestamps and integer second values are retained internally because they are useful for accurate measurement, deterministic calculations and future model training. They are implementation data, not the customer-facing display unit.

## Service timing

When Counter Staff calls a customer, Smart Q records:

- `service_started_at`
- `service_target_seconds`

The target is a snapshot of the service average at the moment service begins. It is intentionally immutable for that visit so later configuration changes cannot rewrite historical prediction context.

While the customer is being served, the UI derives:

- elapsed service time
- target time remaining
- target overrun, when applicable

The browser may update its internal second-resolution clock so minute boundaries change promptly, but the visible values are rounded/formatted as minutes. Authoritative server state is refreshed every two seconds, so completion and counter transitions are picked up without requiring a manual refresh.

## Waiting ETA

A waiting customer's ETA now considers:

- customers waiting ahead
- customers currently being served
- the remaining target time of each active service
- the number of matching open counters
- idle open counters that can accept work immediately

Waiting tickets are projected onto the matching counter that becomes available first. This is deterministic live scheduling logic; it is not yet a machine-learning prediction.

## Completion observations for forecasting

When Counter Staff completes a service, Smart Q records:

- `service_completed_at`
- `actual_service_seconds`
- `service_variance_seconds = actual_service_seconds - service_target_seconds`

The completion QueueEvent also stores:

- `service_target_seconds`
- `actual_service_seconds`
- `service_variance_seconds`
- `service_minutes_saved`
- `service_overrun_minutes`

Example: a 20-minute target completed in 15 minutes becomes:

- target = `1200` seconds internally
- actual = `900` seconds internally
- variance = `-300` seconds internally
- minutes saved = `5.0`

The five minutes are not discarded. They become a labelled historical residual that a future model can learn from.

## Why the configured average is not automatically overwritten

One fast or slow customer is not enough evidence to change a service's configured average. Automatically updating the average after every completion would make the baseline unstable and would destroy the clean distinction between prediction and observation.

Instead, Day 58 captures immutable per-service observations. A later forecasting layer can aggregate or model these records by branch, service, queue type, counter load, time of day, day of week and other approved features.

## Real-time boundary

Smart Q does not claim WebSocket real-time behavior in Day 58.

```text
Visible time unit          minutes
Internal timing precision  seconds / timestamps
Operational API refresh    every 2 seconds
Transport                   normal HTTP polling
```

This gives users a simple minute-based estimate while keeping enough measurement precision for correct queue calculations and future forecasting work.

## Database migration

Migration `queues/0009_queueticket_service_timing.py` adds the service timing fields to `QueueTicket`.

## Regression coverage

`smartq/test_day58_realtime_service_timing.py` protects:

- current service being counted ahead of a waiting customer
- 20-minute service target decreasing to 15 minutes after five elapsed minutes
- elapsed/remaining service timing for a serving customer
- 20-minute target completed in 15 minutes retaining a `-300` second internal residual and `5.0` minutes saved
- parallel open counters reducing wait when another counter is immediately available
- minute-based Customer and Counter Staff presentation
- absence of `M:SS` / visible seconds formatting
- two-second authoritative operational refresh
- retention of second-resolution internal timing fields for forecasting

The Day 58 test gate runs before the complete Django regression suite in CI.
