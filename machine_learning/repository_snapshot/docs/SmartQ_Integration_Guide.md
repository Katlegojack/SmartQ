# My SmartQ ML Integration Guide

## Why I wrote this guide

I separated the machine-learning repository from the main SmartQ Django application.

I did that so I could train, evaluate and document the model independently without mixing experimental ML work into the main application code.

The next step is to connect the selected model to SmartQ safely.

This guide records how I plan to do that.

## Model artifact

I generate the trained model bundle by running:

```bash
python src/train_models.py
```

This creates:

```text
models/smartq_wait_time_model.joblib
```

The bundle contains:

- the fitted preprocessing transformer;
- the selected XGBoost model;
- the feature list;
- the target name;
- model metadata.

I package preprocessing and the model together because prediction must use exactly the same transformations that were used during training.

## Inputs I require at prediction time

My integration layer must build one observation using information that is already known when the customer needs the estimate.

The required fields are:

```text
arrival_offset_minutes
people_ahead
general_waiting
priority_waiting
serving_count
open_general_counters
open_priority_counters
effective_open_counters
counter_utilisation
queue_pressure_index
workload_minutes_ahead
recent_avg_service_minutes_10
recent_avg_wait_minutes_10
recent_throughput_60m
service_target_minutes
hour_of_day
branch_code
service_code
booking_source
queue_type
day_of_week
is_peak_period
```

I deliberately do not allow future/outcome fields.

## Prediction helper

I created:

`src/predict.py`

My helper:

1. checks that all required inputs are present;
2. loads the trained model bundle;
3. applies the saved preprocessing;
4. makes the prediction;
5. prevents negative customer-facing waits.

The customer-facing result is:

`max(0, prediction)`

I do this because waiting time cannot be negative.

## How I want to connect it to Django

The main SmartQ backend should calculate the live queue features from its own database and queue services.

Conceptually:

```python
observation = build_live_queue_features(ticket)
predicted_minutes = predict_wait_minutes(observation)
```

Then the existing API can return something like:

```json
{
  "predicted_wait_minutes": 12.7,
  "prediction_model": "xgboost",
  "model_status": "active"
}
```

I do not want to create a second unrelated API if the current SmartQ API can carry the prediction cleanly.

## My engineering rules for integration

### 1. I will not send future information to the model

I must never use actual wait, completion time or any other outcome field when making the live prediction.

### 2. I should load the model once per application process

I do not want to read the model from disk for every HTTP request.

That would waste time and make prediction slower.

### 3. I want a fallback

If ML prediction fails, I want SmartQ to fall back to the existing deterministic ETA.

I do this because ML should improve the application, not become a single point of failure.

### 4. I will separate display value from stored raw value

I can round the waiting time for customer display, but I still want the raw numeric prediction available for logging and later evaluation.

### 5. I must measure latency

My proposal requires the prediction response to stay under two seconds.

I therefore need an actual timing test after Django integration.

### 6. I want to log predictions and later outcomes

Once SmartQ is running, I want to record:

- what the model predicted;
- what the actual waiting time became.

That future data is how I can eventually move away from synthetic-only training.

## Current limitation

My selected model was trained entirely on synthetic SmartQ data.

Connecting it to Django will prove that the end-to-end ML workflow works.

It will **not** prove that the model is production-ready for a real organisation.

I will need representative live data before I make real-world accuracy claims.
