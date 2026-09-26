# My SmartQ Modelling Results

I use this folder to preserve the outputs from my waiting-time model experiment.

Files:

- `data_preparation_summary.json` — my chronological split, feature list and selected hyperparameters;
- `model_metrics.csv` — my MAE/RMSE results for baselines and models;
- `random_forest_tuning.csv` — the limited Random Forest configurations I tested;
- `xgboost_tuning.csv` — the limited XGBoost configurations I tested;
- `feature_importance.csv` — fitted selected-model feature importance;
- `scenario_performance.csv` — XGBoost performance under Low, Moderate and Busy traffic;
- `service_performance.csv` — performance by service;
- `branch_performance.csv` — performance by synthetic branch;
- `peak_performance.csv` — performance during peak and non-peak periods.

My official model-selection rule is based on **validation MAE**.

I kept XGBoost as the selected model even though Random Forest later achieved a slightly lower test MAE.

I did that because switching after seeing the test result would mean I was using the test set for model selection.

I prefer to keep the evaluation method honest.
