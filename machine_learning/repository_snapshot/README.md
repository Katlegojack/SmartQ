# SmartQ Machine Learning

This repository is where I am building and documenting the machine-learning part of **SmartQ: A Machine-Learning-Assisted Queue Management System for Waiting-Time Prediction**.

I created this repository separately from the main SmartQ application because I wanted the ML work to have its own clean history, its own experiments, its own results, and its own documentation. I also wanted every important decision to be reproducible instead of having model training hidden inside a notebook that only works on my machine.

## What I am trying to predict

My main prediction target is:

`actual_wait_minutes`

In simple English, I am trying to estimate how long a customer will wait from check-in until they are called for service.

I treated this as a **regression problem** because the answer I want is a number of minutes.

## Models I trained

I trained the three regression models defined in my project proposal:

- Linear Regression
- Random Forest Regressor
- XGBoost Regressor

I also kept two baselines:

- a simple mean-wait baseline;
- the existing deterministic SmartQ ETA.

I used the baselines because a machine-learning model only becomes useful if it improves on something simpler.

## How I judged the models

I mainly used:

- **MAE — Mean Absolute Error:** how many minutes wrong I am on average;
- **RMSE — Root Mean Squared Error:** similar to MAE, but large mistakes are punished more heavily;
- **R²:** how much of the variation in waiting time the model explains.

For official model selection, I used the rule I fixed before looking at the final test results:

> I select the model with the lowest validation MAE.

That rule selected **XGBoost**.

## Repository structure

```text
SmartQ-Machine-Learning/
├── .github/workflows/
│   └── ml-quality.yml
├── .project-notes/
│   ├── README.md
│   └── ML_LEARNING_GUIDE.md
├── data/
│   └── SmartQ_Synthetic_Operational_Dataset_100k.csv
├── notebooks/
│   ├── 01_Data_Understanding_EDA.ipynb
│   ├── 02_Data_Preparation.ipynb
│   ├── 03_Model_Training_Evaluation.ipynb
│   ├── 04_Model_Diagnostics_Statistical_Analysis.ipynb
│   └── SmartQ_ML_100k_Embedded_Dataset.ipynb
├── docs/
│   ├── EDA_Findings.md
│   ├── EDA_Visual_Analysis.md
│   ├── Model_Card.md
│   ├── Model_Diagnostics_Statistical_Analysis.md
│   ├── Model_Evaluation.md
│   ├── Report_ML_Methodology.md
│   ├── SmartQ_Integration_Guide.md
│   └── SmartQ_100k_Synthetic_Dataset_Documentation.docx
├── models/
├── results/
│   ├── eda/
│   ├── diagnostics/
│   └── modeling/
├── src/
│   ├── model_diagnostics.py
│   ├── predict.py
│   ├── train_models.py
│   └── validate_dataset.py
├── requirements.txt
└── README.md
```

## My dataset

I created and validated a synthetic SmartQ operational dataset with:

- **100,000 rows**
- **45 columns**
- appointments and walk-ins
- General and Priority queues
- multiple branches
- multiple service types
- early, on-time and late arrivals
- no-shows and cancellations
- active-counter information
- queue-pressure information
- waiting-time and service-time outcomes

I used synthetic data because I do not yet have a large real SmartQ production dataset. The synthetic data lets me complete the full ML process now, but I do **not** treat synthetic accuracy as proof of real-world production accuracy.

## My most important data rule

I only allow the model to use information that would actually be known at prediction time.

I excluded post-outcome fields such as:

- `call_time`
- `actual_wait_minutes`
- `actual_service_minutes`
- `service_started_at`
- `service_completed_at`

I did this to prevent **data leakage**, which would make the model appear more accurate by giving it information from the future.

## My modelling population

The full dataset contains:

- 92,655 completed visits
- 5,096 no-shows
- 2,249 cancellations

For waiting-time regression, I used only the **92,655 completed visits**.

I did not replace no-shows or cancellations with zero waiting time because zero would falsely mean that the customer arrived and was served immediately.

## My train / validation / test split

I split the completed visits chronologically by whole operating dates:

| Split | Rows | Dates |
|---|---:|---|
| Training | 64,074 | 2 Jan 2026 – 16 Jun 2026 |
| Validation | 14,665 | 17 Jun 2026 – 22 Jul 2026 |
| Test | 13,916 | 23 Jul 2026 – 27 Aug 2026 |

I chose a chronological split because SmartQ will learn from past behaviour and predict later behaviour. I did not want customers from the same operating day to appear in both training and test data.

## My main model results

Validation results:

| Model | MAE | RMSE |
|---|---:|---:|
| Linear Regression | 4.1146 | 6.1452 |
| Random Forest | 2.6315 | 4.4920 |
| **XGBoost** | **2.6302** | **4.3893** |

I selected XGBoost because it had the lowest validation MAE.

Final test results:

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Linear Regression | 4.0645 | 6.4606 | 0.9313 |
| Random Forest | 2.5231 | 4.6425 | 0.9645 |
| **Selected XGBoost** | **2.5824** | **4.9561** | **0.9596** |

Random Forest happened to produce a slightly lower test MAE, but I did not switch models after seeing the test results because that would turn the test set into another model-selection set.

## What I learned from diagnostics

I did not stop at MAE and RMSE.

I also checked:

- R² and adjusted R²;
- train/validation/test gaps;
- p-values and confidence intervals for Linear Regression;
- multicollinearity using VIF;
- heteroscedasticity;
- residual normality;
- residual bias;
- negative raw predictions;
- permutation importance;
- TreeSHAP feature contributions.

The diagnostics showed that workload ahead, people ahead and available serving capacity are some of the most useful predictive signals.

They also showed that several engineered queue variables overlap strongly, so I must be careful when interpreting individual Linear Regression coefficients.

## My biggest current limitation

My selected XGBoost model performs much worse during very busy conditions.

Test MAE by traffic level:

- Low: about 1.22 minutes
- Moderate: about 2.95 minutes
- Busy: about 7.94 minutes

I am keeping this limitation visible because the goal is to understand where the model fails, not just to show the best overall number.

## Current status

I have completed:

- dataset generation and validation;
- EDA / Data Understanding;
- data preparation;
- leakage prevention;
- chronological splitting;
- Linear Regression;
- Random Forest;
- XGBoost;
- limited tuning;
- baseline comparison;
- MAE/RMSE/R² evaluation;
- model diagnostics;
- significance tests;
- VIF analysis;
- permutation importance;
- TreeSHAP;
- reusable training code;
- reusable prediction code;
- automated data-quality checks;
- detailed documentation.

My next major step is to connect the selected model to the main SmartQ Django backend and verify that prediction latency stays below the project requirement.

## Detailed learning notes

I keep my detailed engineering reasoning in:

`.project-notes/README.md`

I keep the plain-English ML learning guide in:

`.project-notes/ML_LEARNING_GUIDE.md`

I use those files to explain what I did, why I did it, what alternatives I considered, what trade-offs I accepted, and what I learned from each stage.
