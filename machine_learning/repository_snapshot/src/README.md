# My SmartQ ML Source Code

I use this folder for reusable ML code that should not stay trapped inside notebooks.

My main files are:

- `train_models.py` — I use this to reproduce data preparation, model training, tuning, evaluation outputs and the selected model bundle;
- `predict.py` — I use this as the stable prediction interface for future SmartQ integration;
- `validate_dataset.py` — I use this to check that the main dataset still satisfies important structural rules;
- `model_diagnostics.py` — I use this to reproduce R², robust OLS statistics, VIF, significance tests, permutation importance and SHAP outputs.

I keep reusable logic here because notebooks are good for learning and exploration, but application integration needs code that I can call consistently.

My goal is that somebody can reproduce my important results from code instead of trusting manually copied numbers.

I keep this folder limited to reusable ML code that belongs to the project long-term. I remove one-off migration or documentation-rewrite helpers after they have done their job so the source folder stays clean.
