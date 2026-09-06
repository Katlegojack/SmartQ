# Smart Q — Day 59: Forecasting Observation Foundation

## Status

Day 59 builds the data foundation required before Smart Q introduces a machine-learning wait-time model.

The milestone does **not** turn on machine learning. The live queue still uses the deterministic Day 58 scheduling calculation. Day 59 adds a separate observation pipeline that records what Smart Q knew at queue entry and what actually happened later.

That distinction is intentional:

```text
LIVE OPERATIONAL SYSTEM
    deterministic queue ETA
            |
            | captures prediction context
            v
FORECAST OBSERVATION
    queue-entry features
            |
            | later receives outcomes
            v
LABELLED HISTORY
    actual wait + actual service
            |
            v
FUTURE MODEL TRAINING / EVALUATION
```

## Why this comes before a neural network

A model cannot learn useful queue behaviour from a number such as `20 min` alone. It needs repeated examples containing both:

1. the information that was available when the prediction was made; and
2. the outcome that happened afterward.

Without that separation it is easy to build a model that accidentally sees the answer during training, which is called target leakage. A leaked model may look excellent in a notebook and fail in the real queue.

Day 59 therefore treats data collection as an engineering feature, not as an afterthought.

## Observation lifecycle

Every live queue activation already produces a `QueueEvent.CHECKED_IN` event. Every service start produces `QueueEvent.CALLED`, and every successful completion produces `QueueEvent.COMPLETED`.

Day 59 subscribes to those append-only events instead of adding separate data-collection code to Customer, Reception and Counter workflows.

```text
CHECKED_IN
    |
    +--> create QueueForecastObservation
          - branch
          - service
          - queue lane
          - online/walk-in source
          - check-in timestamp
          - people ahead
          - open matching counters
          - customers already being served
          - deterministic baseline ETA

CALLED
    |
    +--> attach wait outcome
          - called_at
          - actual_wait_seconds
          - wait_variance_seconds
          - service target snapshot

COMPLETED
    |
    +--> attach service outcome
          - service_completed_at
          - actual_service_seconds
          - service_variance_seconds
```

This event-driven boundary matters because Smart Q has several valid queue-entry paths:

- registered Customer walk-in;
- Customer appointment check-in;
- Reception staff check-in;
- Reception guest walk-in.

All of them already converge on the authoritative queue event lifecycle. Capturing observations at that boundary reduces the chance that one workflow collects modelling data while another silently does not.

## New model: `QueueForecastObservation`

The model stores one queue-entry observation and the labels that become known later.

A `QueueTicket` can have multiple observations over its lifetime. That is deliberate: a booking can be rescheduled and activated again, and an earlier observation should not be overwritten by a later attempt.

### Queue-entry features

These values are recorded when the customer enters the live queue:

```text
ticket
branch
service
queue_type
booking_source
checked_in_at
baseline_estimated_wait_seconds
people_ahead
open_counter_count
serving_count
```

They represent facts that were available at prediction time.

### Wait-time outcome

When the ticket is called:

```text
actual_wait_seconds = called_at - checked_in_at

wait_variance_seconds =
    actual_wait_seconds
    - baseline_estimated_wait_seconds
```

Interpretation:

```text
negative residual  -> customer waited less than predicted
zero residual      -> baseline was exact
positive residual  -> customer waited longer than predicted
```

### Service-duration outcome

When service completes:

```text
service_variance_seconds =
    actual_service_seconds
    - service_target_seconds
```

This keeps the Day 58 distinction between the expected service duration and the real observed duration.

## Example: the five-minute saving now becomes training evidence

Assume one barber counter and a 20-minute target service.

```text
09:00  A001 begins service
09:05  A002 joins queue
```

At 09:05 Smart Q can see that A001 has approximately 15 minutes remaining, therefore A002 receives a 15-minute baseline estimate.

If A001 actually finishes at 09:15, A002 is called after only 10 minutes.

Day 59 records:

```text
A002 baseline wait   15 min
A002 actual wait     10 min
A002 residual        -5 min
```

The operational queue immediately benefits because A002 can be served at 09:15. The unused five minutes are also retained as labelled error data instead of disappearing.

If A002 then completes a 20-minute service target in 13 minutes:

```text
service target       20 min
actual service       13 min
service residual     -7 min
```

Those are exactly the kinds of repeated observations a future model needs.

## Internal precision versus user-facing units

The product remains minute-based for users.

```text
Customer UI      15 min
Counter UI        7 min elapsed
Manager UI        minutes / counts
```

Internally, Day 59 keeps integer seconds and exact timestamps. This is measurement precision, not a decision to display seconds.

For example, a real duration of 13 minutes 34 seconds should not be permanently reduced to 13 or 14 minutes before modelling. Exact internal measurements let later analysis decide how to aggregate the data.

## Privacy and modelling boundary

The exported forecasting dataset is intentionally PII-minimised.

It does **not** export:

```text
customer name
username
email
phone number
date of birth
gender
disability status
pregnancy status
```

The queue lane (`general` or `priority`) is retained because it is an operational queue state that changes which counter pool serves a ticket. The protected attributes that may have produced the lane are not exported as model features.

This is an important engineering rule: the forecasting model should predict operational time, not learn personal identity.

## Training-row schema

The approved Day 59 export columns are:

```text
observation_id
ticket_id
branch_id
service_id
queue_type
booking_source
checked_in_at
checked_in_weekday
checked_in_hour
people_ahead
open_counter_count
serving_count
baseline_estimated_wait_seconds
actual_wait_seconds
wait_variance_seconds
service_target_seconds
actual_service_seconds
service_variance_seconds
```

The timestamp is converted to Smart Q local time before weekday/hour extraction.

Outcome columns may be empty for observations whose customer has not yet been called or whose service has not yet completed. That is normal for a live operational dataset.

## Dataset export command

Day 59 adds:

```bash
python manage.py export_forecasting_dataset
```

Optional filters:

```bash
python manage.py export_forecasting_dataset \
  --branch-id 3 \
  --start-date 2026-09-01 \
  --end-date 2026-09-30 \
  --output data/smartq_forecasting.csv
```

The command validates date formats, rejects reversed date ranges, validates branch IDs and creates parent output directories when needed.

The exported CSV is designed as a controlled engineering input for analysis. It is not exposed as a public Customer API.

## Forecasting quality API

Branch Managers and System Admins can inspect collection quality through:

```http
GET /api/v1/queues/branches/<branch_id>/reports/forecasting/
```

It uses the same branch permission model and date-range validation as historical operational reporting.

The response intentionally says:

```json
{
  "model_status": "data_collection",
  "machine_learning_enabled": false
}
```

This prevents Smart Q from pretending that a machine-learning predictor exists before one has been trained and evaluated.

## Baseline metrics

Day 59 calculates simple error metrics against the deterministic baseline.

### Mean absolute error (MAE)

```text
MAE = average(abs(actual - predicted))
```

MAE answers:

> On average, how many minutes away was the prediction, regardless of whether it was early or late?

### Bias

```text
Bias = average(actual - predicted)
```

Interpretation:

```text
negative bias -> Smart Q tends to overestimate waits
positive bias -> Smart Q tends to underestimate waits
near zero      -> over/under errors are balanced
```

Day 59 reports both wait-baseline error and configured-service-target error.

These metrics give us a benchmark that any later statistical or machine-learning model must beat. A complicated model is not an improvement simply because it is more complicated.

## Manager/Admin UI

The History & Recovery workspace now includes a compact **Forecasting foundation — Data collection quality** section.

It shows:

```text
Observations
Wait labels
Service labels
Wait baseline MAE
Service target MAE
```

It also explicitly states that Smart Q is collecting labelled observations and that no machine-learning model is active yet.

This gives operational users visibility into whether enough real outcomes are being collected without exposing raw customer data or technical second counters.

## Migration

Migration:

```text
queues/0010_queueforecastobservation.py
```

It creates the observation table and two time-oriented indexes:

```text
branch + checked_in_at
service + checked_in_at
```

These support the main future analysis patterns: performance over time for one branch and performance over time for one service.

## Regression scenario

`smartq/test_day59_forecasting_observations.py` uses a real two-customer lifecycle:

```text
09:00  first customer joins and is called
09:05  second customer joins while first is serving
09:15  first customer finishes early
09:15  second customer is called
09:28  second customer completes service
```

The suite protects:

- the 15-minute queue-entry baseline for customer two;
- the 10-minute actual wait;
- the retained `-5 min` wait residual;
- the retained `-7 min` service residual for customer two;
- collection of open-counter and serving-count features;
- PII exclusion from exported rows;
- Branch Manager scoping;
- System Admin global access;
- CSV export columns;
- the event-driven CHECKED_IN/CALLED/COMPLETED integration;
- the explicit `machine_learning_enabled = false` state.

## Engineering lessons

### 1. Collect data at a domain boundary, not in every screen

If Customer, Reception and Counter code each wrote their own analytics records, they would eventually disagree. QueueEvent already defines the operational lifecycle, so it is the safest integration point.

### 2. Prediction and outcome are different facts

The baseline estimate must be frozen before the outcome occurs. If we recalculate the historical baseline after knowing when the customer was called, we would corrupt the training label and create leakage.

### 3. Residuals are valuable data

An early completion is not merely “five minutes disappeared.” It is evidence that the current service target was five minutes too high for that observation.

### 4. Internal precision does not dictate UI precision

Seconds are useful for measurement. Minutes are better for the product interface. Both can coexist cleanly.

### 5. A model needs a benchmark

Before training a neural network, Smart Q needs to know how well the deterministic baseline already performs. MAE and bias establish that benchmark.

### 6. More features are not automatically better

Personal or protected customer attributes may improve an offline score while creating fairness, privacy and governance problems. Day 59 deliberately starts from operational queue context instead.

### 7. Null labels are normal in live data

A customer who is still waiting has no actual wait label yet. A customer currently being served has no final service-duration label yet. The data pipeline must tolerate partial observations and complete them later.

## Trade-offs

### Event signal versus direct service calls

**Chosen:** subscribe to `QueueEvent` creation.

Advantages:

- one integration point for all workflows;
- less duplication;
- existing audit lifecycle remains the source of truth;
- future entry paths automatically participate if they emit the standard events.

Trade-off:

- the relationship is less obvious than a direct function call inside every workflow, so regression tests and documentation are important.

### Separate observation model versus only QueueEvent metadata

**Chosen:** dedicated `QueueForecastObservation` model.

Advantages:

- clean feature/label schema;
- efficient date/branch/service queries;
- easier CSV export;
- avoids repeatedly reconstructing a training row from several event records;
- supports more than one activation attempt for the same ticket.

Trade-off:

- one additional table and migration.

### Raw protected attributes versus operational features

**Chosen:** exclude raw protected/personal attributes.

Advantages:

- lower privacy risk;
- clearer modelling purpose;
- easier governance;
- prevents the first forecasting experiment from depending on customer identity.

Trade-off:

- some predictive signal may be intentionally unavailable to the model. That is an acceptable trade for a safer first modelling baseline.

## What Day 59 does not do

Day 59 does not:

- train a neural network;
- deploy a machine-learning estimator;
- overwrite `Service.average_service_time` automatically;
- display second-by-second time to users;
- expose personal customer data as forecasting features;
- replace the Day 58 deterministic ETA.

## Way forward

The correct sequence after this foundation is:

```text
1. Run real queue journeys
2. Accumulate labelled observations
3. Inspect missingness and distributions
4. Establish deterministic baseline MAE/bias by branch/service/time
5. Create train/validation/test splits by time
6. Build simple statistical/ML baselines
7. Compare them against the deterministic baseline
8. Only then test a neural network if the data volume and non-linearity justify it
9. Deploy a model only if it improves accuracy reliably without violating operational/fairness constraints
```

That keeps Smart Q's modelling work evidence-driven rather than adding AI for presentation value.
