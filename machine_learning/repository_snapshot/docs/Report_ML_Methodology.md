# My SmartQ Machine-Learning Methodology

## Data understanding

I started with a synthetic SmartQ dataset containing 100,000 operational queue records.

The dataset represents appointments, walk-ins, General and Priority queues, multiple service types, active counters, queue-state measurements and final service outcomes.

Before modelling, I performed EDA because I wanted to understand the data before trusting any model result.

I inspected:

- record distributions;
- missing values;
- waiting-time behaviour;
- queue patterns;
- data-quality rules;
- possible leakage.

For the regression task, I kept only the **92,655 completed visits**.

I excluded cancelled and no-show records because those records do not have a genuine completed waiting-time outcome.

## Target definition

My prediction target is:

`actual_wait_minutes`

I define it as the time from customer check-in until the customer is called for service.

I chose this target because it directly matches the SmartQ customer question:

> How long am I likely to wait before I am called?

## Feature selection

I used only information that would be available at prediction time.

Examples include:

- people ahead;
- queue pressure;
- workload ahead;
- active counters;
- recent average service duration;
- recent average waiting time;
- throughput;
- service type;
- branch;
- queue lane;
- time features.

I excluded post-outcome fields such as:

- actual waiting time;
- call time;
- actual service duration;
- service start time;
- completion time.

I did this to prevent data leakage.

## Missing values

I found that some recent-history variables are naturally missing early in an operating day.

I did not delete those valid records.

Instead:

- I used the training-set median for numeric missing values;
- I used the most frequent training category for categorical missing values.

I fit the imputation rules using training data only so validation and test information could not leak backward into preprocessing.

## Categorical encoding

I one-hot encoded categorical variables.

I chose one-hot encoding because variables such as branch code and service code do not have a natural numeric order.

I avoided ordinal encoding because it would incorrectly imply an order between categories.

## Train / validation / test split

I split completed visits chronologically by whole operating dates:

- Training: 64,074 rows, 2 Jan to 16 Jun 2026
- Validation: 14,665 rows, 17 Jun to 22 Jul 2026
- Test: 13,916 rows, 23 Jul to 27 Aug 2026

I chose this instead of a random row split because SmartQ will learn from past operational behaviour and predict later behaviour.

I also wanted to prevent same-day queue conditions from appearing in both training and test data.

## Baselines

I used two baselines.

### Mean baseline

I predicted the same training-set mean wait for every customer.

I used this because a complex ML model should easily beat a simple average if it is genuinely useful.

### Existing SmartQ deterministic ETA

I also evaluated the current formula-style ETA as an engineering benchmark.

I did not use that ETA as an ML feature because I wanted the official models to learn directly from queue conditions.

## Models I trained

I trained the three regression models defined in the project proposal:

1. Linear Regression
2. Random Forest
3. XGBoost

I used the same prepared data and the same validation/test periods so the comparison would be fair.

## Why I kept tuning limited

I tested a small number of understandable parameter combinations for Random Forest and XGBoost.

I did not run a huge grid search.

I made that decision because:

- the proposal calls for limited tuning;
- I wanted to avoid overfitting the validation set;
- I wanted the experiment to stay understandable;
- this is a third-year capstone rather than a benchmark competition.

## Evaluation metrics

I used:

- MAE
- RMSE
- R² for diagnostics

I used MAE as the official model-selection metric because it is easy to interpret in minutes.

I fixed the rule before test evaluation:

> Lowest validation MAE among the three official models wins.

## Validation results

Validation MAE:

- Linear Regression: 4.1146 min
- Random Forest: 2.6315 min
- XGBoost: **2.6302 min**

I therefore selected XGBoost.

Random Forest and XGBoost are effectively very close, so I do not claim a dramatic difference.

## Final test results

My selected XGBoost model achieved:

- Test MAE: **2.5824 min**
- Test RMSE: **4.9561 min**
- Test R²: **0.9596**

The mean baseline produced:

- Test MAE: **14.9850 min**

The deterministic SmartQ ETA produced:

- Test MAE: **4.6386 min**

Random Forest happened to produce a slightly lower test MAE of 2.5231 minutes.

I kept XGBoost because the test set was not supposed to select the model.

## Diagnostics I added

I later expanded the analysis with:

- train/validation/test fit comparison;
- R² and adjusted R²;
- Linear Regression p-values;
- robust confidence intervals;
- VIF;
- residual diagnostics;
- heteroscedasticity testing;
- group significance tests;
- effect sizes;
- permutation importance;
- TreeSHAP.

I added these because I wanted to understand the models, not just submit an error score.

## Main diagnostic finding

My XGBoost model performs strongly overall on synthetic data but degrades under heavy congestion.

Traffic-specific test MAE:

- Low: 1.22 min
- Moderate: 2.95 min
- Busy: 7.94 min

I treat this as a real limitation.

## Final interpretation

My results show that the three models can learn the operational patterns present in the synthetic SmartQ dataset.

I do **not** claim that the same accuracy is guaranteed in a real government office, university, clinic or business.

I treat the current work as a prototype demonstration of a correct ML process.

Before real deployment, I would need representative operational data, live validation, monitoring and retraining.
