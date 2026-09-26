# My SmartQ Waiting-Time Model Card

## Model I selected

I selected:

**XGBoost Regressor**

My goal is to predict:

`actual_wait_minutes`

at customer check-in.

## Data I trained on

I used the **92,655 completed synthetic SmartQ visits** for regression.

I split them chronologically into:

- Training: 64,074
- Validation: 14,665
- Test: 13,916

I used whole operating dates so one day could not appear in more than one split.

## My model-selection rule

Before looking at final test results, I fixed this rule:

> I select the official model with the lowest validation MAE.

Validation MAE:

- Linear Regression: 4.1146 min
- Random Forest: 2.6315 min
- XGBoost: **2.6302 min**

I therefore selected XGBoost.

## Final test result

For the selected XGBoost model:

- Test MAE: **2.5824 minutes**
- Test RMSE: **4.9561 minutes**
- Test R²: **0.9596**

In simple English, the selected model is wrong by about 2.6 minutes on average on the synthetic test period.

## Inputs I allow

I use queue-state and operational information that can be known at prediction time.

Examples include:

- people ahead;
- queue pressure;
- workload ahead;
- active counters;
- recent average service time;
- recent average wait;
- recent throughput;
- service type;
- branch;
- booking source;
- queue lane;
- time of day.

## Inputs I deliberately exclude

I exclude post-outcome information such as:

- actual wait;
- call time;
- actual service duration;
- service start time;
- completion time.

I also exclude the existing deterministic SmartQ ETA from the official ML feature set.

I do this to keep the experiment clean and prevent data leakage.

## Important behaviour I discovered

The raw XGBoost model can sometimes predict a slightly negative wait.

On the test set I found 962 raw negative predictions, but they were generally small.

Because a real customer cannot wait -0.2 minutes, I apply:

`max(0, prediction)`

before showing the result to a customer.

## Biggest limitation

The model performs much worse during very busy synthetic conditions.

Busy-traffic MAE is about **7.94 minutes**.

I treat that as an important limitation because heavy congestion is exactly when SmartQ predictions matter most.

## What I do not claim

I do **not** claim that this model will automatically achieve 2.58-minute MAE in a real organisation.

All current training and evaluation data is synthetic.

I treat this model as a strong prototype integration candidate, not as proof of production accuracy.

For real deployment, I would need representative live data, monitoring, validation and retraining.
