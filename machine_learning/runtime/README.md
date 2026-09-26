# SmartQ XGBoost Runtime Model

I keep the deployable waiting-time model for SmartQ in this folder.

## Runtime artifact

`smartq_wait_time_model.joblib`

I generated this file directly from the copied ML training pipeline on the `feature/ml-integration` branch.

The GitHub Actions build re-ran `machine_learning/repository_snapshot/src/train_models.py` against the full 100,000-row synthetic dataset and reproduced the official model comparison before packaging the selected model.

## Model selection reproduced during packaging

The build reproduced these validation results:

- Linear Regression MAE: **4.1146 min**
- Random Forest MAE: **2.6315 min**
- XGBoost MAE: **2.6302 min**

The training script therefore selected **XGBoost**, using the same validation-MAE rule documented in my ML work.

The selected XGBoost test result reproduced during the build was:

- MAE: **2.5824 min**
- RMSE: **4.9561 min**

## Artifact size

The tracked runtime model is approximately **149 KB**.

## What is inside the bundle

The joblib bundle contains:

- the fitted preprocessing transformer;
- the selected XGBoost model;
- the ordered feature list;
- the target name;
- selected-model metadata.

I package preprocessing with the model because live SmartQ inputs must be transformed exactly the same way as the training data.

## Runtime compatibility

I built the artifact with:

- Python 3.12
- pandas 2.2.3
- numpy 2.3.5
- scikit-learn 1.8.0
- XGBoost 3.1.3
- joblib 1.5.3

I keep those versions in `requirements.txt` beside the model.

## Safety rule

I will not make the ML model the only way SmartQ can estimate waiting time.

During Django integration I will keep the deterministic SmartQ ETA as a fallback if the model cannot load, an input feature cannot be built safely, or prediction fails.

## Next step

The remaining integration work is to build the 22 live model inputs from the Django queue state, load this artifact once per application process, return the ML estimate through the existing queue API, and verify end-to-end latency.
