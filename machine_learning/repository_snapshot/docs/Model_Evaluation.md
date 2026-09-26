# My SmartQ Model Evaluation

## What I am evaluating

My ML task is to predict customer waiting time in minutes using information available at check-in time.

My target is:

`actual_wait_minutes`

I use completed visits only because no-shows and cancellations do not have a genuine completed wait outcome.

## How I split the data

I used a chronological split by whole operating days.

| Split | Rows | Date range |
|---|---:|---|
| Training | 64,074 | 2026-01-02 to 2026-06-16 |
| Validation | 14,665 | 2026-06-17 to 2026-07-22 |
| Test | 13,916 | 2026-07-23 to 2026-08-27 |

I chose this because SmartQ will learn from past behaviour and predict later behaviour.

I also wanted to avoid customers from the same operating day appearing across different splits.

## How I prepared the data

For numeric missing values, I used the median learned from the training data only.

For categorical missing values, I used the most frequent training value.

I one-hot encoded categorical variables so the models could work with branch, service, booking source, queue lane, weekday and peak-period labels.

I deliberately excluded the existing `baseline_eta_minutes` from the official ML features.

I also excluded post-outcome fields to prevent data leakage.

## My validation results

| Model | MAE (min) | RMSE (min) |
|---|---:|---:|
| Mean baseline | 15.9560 | 25.8235 |
| SmartQ deterministic ETA | 4.6871 | 6.3250 |
| Linear Regression | 4.1146 | 6.1452 |
| Random Forest | 2.6315 | 4.4920 |
| **XGBoost** | **2.6302** | **4.3893** |

Before I looked at the final test set, I had already decided that the official model would be whichever of Linear Regression, Random Forest and XGBoost had the lowest validation MAE.

XGBoost won by a very small margin.

The difference between Random Forest and XGBoost validation MAE is only about 0.0013 minutes.

So I do **not** describe XGBoost as dramatically better.

I describe the result as:

> Random Forest and XGBoost performed almost identically on validation MAE, with XGBoost narrowly achieving the lowest value.

## Final test results

After I fixed the selection decision, I evaluated the later test period.

| Model | MAE (min) | RMSE (min) |
|---|---:|---:|
| Mean baseline | 14.9850 | 24.8143 |
| SmartQ deterministic ETA | 4.6386 | 6.3683 |
| Linear Regression | 4.0645 | 6.4606 |
| Random Forest | 2.5231 | 4.6425 |
| **Selected XGBoost** | **2.5824** | **4.9561** |

Random Forest happened to have a slightly lower test MAE.

I did not switch models after seeing this.

If I changed the winner after seeing the test results, I would be using the test set for model selection.

That would weaken the credibility of my evaluation.

The difference is also tiny in practical terms: about 0.059 minutes, which is roughly 3.5 seconds.

I preferred to keep the evaluation method honest.

## Traffic-condition performance

I grouped test rows using `queue_pressure_index`:

- Low: below 1.0
- Moderate: 1.0 to below 2.5
- Busy: 2.5 or above

For selected XGBoost:

| Traffic | Rows | MAE (min) | RMSE (min) |
|---|---:|---:|---:|
| Low | 6,216 | 1.22 | 2.40 |
| Moderate | 6,575 | 2.95 | 4.43 |
| Busy | 1,125 | 7.94 | 12.54 |

This is one of the most important findings in my project.

The overall MAE is strong, but the model becomes much less accurate during severe congestion.

I keep this limitation visible because busy queues are exactly where waiting-time prediction matters most.

## Service performance

XGBoost test MAE is similar across my three synthetic service types:

| Service | MAE (min) |
|---|---:|
| Collections | 2.61 |
| ID Applications | 2.54 |
| Passport Applications | 2.60 |

I also found that the raw average waiting times of the service types are not statistically different in a meaningful way.

## Branch performance

The synthetic scenario produces different error levels across branches.

For example:

- Centurion Service Centre: about 4.07 min MAE
- Pretoria Central: about 2.00 min MAE

I do not present these as real service-centre performance.

They are results from the synthetic data I generated.

## Feature importance

My tree-model diagnostics consistently point to:

- workload ahead;
- people ahead;
- effective serving capacity;
- queue pressure;

as important prediction signals.

I treat feature importance as evidence about how the model uses the synthetic data.

I do not treat it as causal proof.

## Why I selected XGBoost

I selected XGBoost because:

1. it was one of the three proposal models;
2. it achieved the lowest validation MAE;
3. it also achieved the lowest validation RMSE of the three official ML models;
4. its test performance remained strong;
5. it beat the mean baseline by a large margin;
6. it improved on the deterministic ETA benchmark;
7. I can package it for backend prediction.

My selected configuration is:

- n_estimators: 200
- max_depth: 5
- learning_rate: 0.08
- subsample: 0.9
- colsample_bytree: 0.9
- reg_lambda: 2.0

## What I do not claim

I do not claim that these numbers prove real-world production accuracy.

My experiment shows that the models can learn the patterns I deliberately represented in the synthetic SmartQ dataset.

Real deployment would still require:

- representative live queue data;
- external validation;
- monitoring;
- retraining.
