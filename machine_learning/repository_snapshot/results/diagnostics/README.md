# My SmartQ Diagnostics Results

I use this folder for the machine-readable outputs from my model-diagnostics stage.

I created these files because I wanted to go beyond MAE/RMSE and understand why the models behave the way they do.

Files:

- `model_fit_by_split.csv` — my MAE, RMSE and R² results for train, validation and test;
- `residual_summary.csv` — my residual bias/spread and raw negative-prediction counts;
- `linear_ols_hc3_coefficients.csv` — my Linear Regression coefficients, HC3 robust standard errors, p-values and confidence intervals;
- `linear_assumption_tests.csv` — my heteroscedasticity, residual-normality, autocorrelation indicator and R² diagnostics;
- `vif_numeric_features.csv` — my VIF results for numeric predictors;
- `group_significance_tests.csv` — my Welch tests and Cohen's d effect sizes;
- `service_anova.csv` — my service-type ANOVA and eta-squared;
- `permutation_importance.csv` — how much XGBoost test MAE changes when I shuffle each original feature;
- `shap_importance.csv` — my mean absolute TreeSHAP contributions on a fixed 5,000-row test sample.

I do not collect these metrics just to make the project look advanced.

I use each one to answer a different question:

- MAE/RMSE: how wrong am I?
- R²: how much variation do I explain?
- p-values: are coefficient effects statistically detectable?
- VIF: are my predictors overlapping?
- residual tests: how are my errors behaving?
- permutation importance: does a feature really help prediction?
- SHAP: how is the model using the features?
