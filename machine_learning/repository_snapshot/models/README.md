# My Trained SmartQ Model

I selected **XGBoost** as my waiting-time model because it achieved the lowest validation MAE among the three official proposal models.

My selected XGBoost results are:

- Validation MAE: **2.6302 minutes**
- Final test MAE: **2.5824 minutes**
- Final test RMSE: **4.9561 minutes**
- Final test R²: **0.9596**

I generate the binary model bundle by running:

```bash
python src/train_models.py
```

That command creates:

`models/smartq_wait_time_model.joblib`

The bundle contains both the fitted preprocessing transformer and the selected model.

I generate the binary instead of treating it as the main source of truth because I want the repository to preserve the reproducible ingredients:

- dataset;
- feature list;
- preprocessing logic;
- split rules;
- random seed;
- model parameters;
- training code;
- evaluation results.

I can regenerate the model from those ingredients.

I do not claim that the trained binary is production-ready for a real organisation because my training data is synthetic.
