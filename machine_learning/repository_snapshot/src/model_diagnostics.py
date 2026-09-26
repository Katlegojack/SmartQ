from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import jarque_bera, durbin_watson
from xgboost import XGBRegressor, DMatrix

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "SmartQ_Synthetic_Operational_Dataset_100k.csv"
OUT = ROOT / "results" / "diagnostics"
OUT.mkdir(parents=True, exist_ok=True)

TARGET = "actual_wait_minutes"

NUMERIC_FEATURES = [
    "arrival_offset_minutes", "people_ahead", "general_waiting", "priority_waiting",
    "serving_count", "open_general_counters", "open_priority_counters",
    "effective_open_counters", "counter_utilisation", "queue_pressure_index",
    "workload_minutes_ahead", "recent_avg_service_minutes_10",
    "recent_avg_wait_minutes_10", "recent_throughput_60m",
    "service_target_minutes", "hour_of_day",
]

CATEGORICAL_FEATURES = [
    "branch_code", "service_code", "booking_source",
    "queue_type", "day_of_week", "is_peak_period",
]

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

df = pd.read_csv(DATA, parse_dates=["scenario_date"])
completed = df[df["status"] == "COMPLETED"].copy()

dates = sorted(completed["scenario_date"].dt.normalize().unique())
n = len(dates)

train_end = pd.Timestamp(dates[int(n * 0.70) - 1])
val_start = pd.Timestamp(dates[int(n * 0.70)])
val_end = pd.Timestamp(dates[int(n * 0.85) - 1])
test_start = pd.Timestamp(dates[int(n * 0.85)])

train = completed[completed["scenario_date"] <= train_end].copy()
validation = completed[
    (completed["scenario_date"] >= val_start)
    & (completed["scenario_date"] <= val_end)
].copy()
test = completed[completed["scenario_date"] >= test_start].copy()

preprocessor = ColumnTransformer([
    ("num", Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
    ]), NUMERIC_FEATURES),
    ("cat", Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ]), CATEGORICAL_FEATURES),
])

X_train, y_train = train[FEATURES], train[TARGET].to_numpy()
X_val, y_val = validation[FEATURES], validation[TARGET].to_numpy()
X_test, y_test = test[FEATURES], test[TARGET].to_numpy()

Xtr = preprocessor.fit_transform(X_train)
Xv = preprocessor.transform(X_val)
Xt = preprocessor.transform(X_test)

models = {
    "Linear Regression": LinearRegression(),
    "Random Forest": RandomForestRegressor(
        n_estimators=150,
        max_depth=14,
        min_samples_leaf=2,
        max_features=1.0,
        random_state=42,
        n_jobs=-1,
    ),
    "XGBoost": XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=-1,
        objective="reg:squarederror",
        tree_method="hist",
    ),
}

for model in models.values():
    model.fit(Xtr, y_train)

def clipped_metrics(y_true, raw_prediction):
    prediction = np.clip(np.asarray(raw_prediction), 0, None)
    return {
        "MAE": mean_absolute_error(y_true, prediction),
        "RMSE": mean_squared_error(y_true, prediction) ** 0.5,
        "R2": r2_score(y_true, prediction),
    }

fit_rows = []
residual_rows = []

for model_name, model in models.items():
    for split_name, X, y in [
        ("train", Xtr, y_train),
        ("validation", Xv, y_val),
        ("test", Xt, y_test),
    ]:
        raw = model.predict(X)
        prediction = np.clip(raw, 0, None)
        residual = y - prediction

        fit_rows.append({
            "model": model_name,
            "split": split_name,
            **clipped_metrics(y, raw),
        })

        residual_rows.append({
            "model": model_name,
            "split": split_name,
            "mean_residual": residual.mean(),
            "median_residual": np.median(residual),
            "residual_std": residual.std(),
            "p05": np.quantile(residual, 0.05),
            "p95": np.quantile(residual, 0.95),
            "negative_prediction_count_raw": int((raw < 0).sum()),
        })

pd.DataFrame(fit_rows).to_csv(OUT / "model_fit_by_split.csv", index=False)
pd.DataFrame(residual_rows).to_csv(OUT / "residual_summary.csv", index=False)

# Statistical OLS companion model with robust standard errors.
train_ols = train.copy()
for column in NUMERIC_FEATURES:
    if train_ols[column].isna().any():
        train_ols[column] = train_ols[column].fillna(train_ols[column].median())

formula = TARGET + " ~ " + " + ".join(
    NUMERIC_FEATURES + [f"C({c})" for c in CATEGORICAL_FEATURES]
)

ols = smf.ols(formula, data=train_ols).fit(cov_type="HC3")

coef_table = pd.DataFrame({
    "term": ols.params.index,
    "coefficient": ols.params.values,
    "std_error_HC3": ols.bse.values,
    "p_value": ols.pvalues.values,
    "ci_low": ols.conf_int()[0].values,
    "ci_high": ols.conf_int()[1].values,
})
coef_table["significant_0_05"] = coef_table["p_value"] < 0.05
coef_table.to_csv(OUT / "linear_ols_hc3_coefficients.csv", index=False)

# VIF for numeric predictors.
numeric_train = train[NUMERIC_FEATURES].copy()
numeric_train = numeric_train.fillna(numeric_train.median(numeric_only=True))
vif_input = sm.add_constant(numeric_train.astype(float), has_constant="add")

vif_rows = []
for i, column in enumerate(vif_input.columns):
    if column == "const":
        continue
    vif_rows.append({
        "feature": column,
        "VIF": variance_inflation_factor(vif_input.values, i),
    })

pd.DataFrame(vif_rows).sort_values("VIF", ascending=False).to_csv(
    OUT / "vif_numeric_features.csv", index=False
)

# Linear assumption diagnostics.
bp_lm, bp_lm_p, bp_f, bp_f_p = het_breuschpagan(ols.resid, ols.model.exog)
jb_stat, jb_p, jb_skew, jb_kurtosis = jarque_bera(ols.resid)
dw = durbin_watson(ols.resid)

assumptions = pd.DataFrame([
    ["Breusch-Pagan LM", bp_lm, bp_lm_p],
    ["Breusch-Pagan F", bp_f, bp_f_p],
    ["Jarque-Bera", jb_stat, jb_p],
    ["Residual skewness", jb_skew, np.nan],
    ["Residual kurtosis", jb_kurtosis, np.nan],
    ["Durbin-Watson", dw, np.nan],
    ["OLS R2", ols.rsquared, np.nan],
    ["OLS adjusted R2", ols.rsquared_adj, np.nan],
], columns=["diagnostic", "statistic", "p_value"])

assumptions.to_csv(OUT / "linear_assumption_tests.csv", index=False)

# Group significance tests with effect sizes.
def welch_and_d(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
    pooled_sd = np.sqrt(
        ((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1))
        / (len(a)+len(b)-2)
    )
    return t_stat, p_value, (a.mean() - b.mean()) / pooled_sd

comparison_rows = []
for label, column, a_value, b_value in [
    ("General vs Priority", "queue_type", "GENERAL", "PRIORITY"),
    ("Appointment vs Walk-in", "booking_source", "APPOINTMENT", "WALK_IN"),
    ("Peak vs Non-peak", "is_peak_period", True, False),
]:
    a = completed.loc[completed[column] == a_value, TARGET]
    b = completed.loc[completed[column] == b_value, TARGET]
    t_stat, p_value, d = welch_and_d(a, b)
    comparison_rows.append({
        "comparison": label,
        "n_a": len(a),
        "n_b": len(b),
        "mean_a": a.mean(),
        "mean_b": b.mean(),
        "welch_t": t_stat,
        "p_value": p_value,
        "cohens_d": d,
    })

pd.DataFrame(comparison_rows).to_csv(
    OUT / "group_significance_tests.csv", index=False
)

service_groups = [
    group[TARGET].to_numpy()
    for _, group in completed.groupby("service_name")
]

f_stat, service_p = stats.f_oneway(*service_groups)
grand_mean = completed[TARGET].mean()
ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in service_groups)
ss_total = ((completed[TARGET] - grand_mean) ** 2).sum()
eta_squared = ss_between / ss_total

pd.DataFrame([{
    "test": "One-way ANOVA",
    "groups": 3,
    "f_stat": f_stat,
    "p_value": service_p,
    "eta_squared": eta_squared,
}]).to_csv(OUT / "service_anova.csv", index=False)

# Permutation importance using the selected XGBoost model.
xgb_model = models["XGBoost"]
xgb_test_pred = np.clip(xgb_model.predict(Xt), 0, None)
baseline_mae = mean_absolute_error(y_test, xgb_test_pred)

rng = np.random.default_rng(42)
permutation_rows = []
X_test_raw = test[FEATURES].copy()

for feature in FEATURES:
    shuffled = X_test_raw.copy()
    values = shuffled[feature].to_numpy(copy=True)
    rng.shuffle(values)
    shuffled[feature] = values

    prediction = np.clip(
        xgb_model.predict(preprocessor.transform(shuffled)),
        0,
        None,
    )
    mae = mean_absolute_error(y_test, prediction)

    permutation_rows.append({
        "feature": feature,
        "permuted_mae": mae,
        "mae_increase": mae - baseline_mae,
    })

pd.DataFrame(permutation_rows).sort_values(
    "mae_increase", ascending=False
).to_csv(OUT / "permutation_importance.csv", index=False)

# XGBoost TreeSHAP global importance.
feature_names = preprocessor.get_feature_names_out()
rng = np.random.default_rng(42)
sample_idx = rng.choice(len(Xt), size=min(5000, len(Xt)), replace=False)

dmatrix = DMatrix(Xt[sample_idx], feature_names=list(feature_names))
contributions = xgb_model.get_booster().predict(
    dmatrix, pred_contribs=True
)

pd.DataFrame({
    "feature": feature_names,
    "mean_abs_shap": np.abs(contributions[:, :-1]).mean(axis=0),
}).sort_values("mean_abs_shap", ascending=False).to_csv(
    OUT / "shap_importance.csv", index=False
)

print("SmartQ model diagnostics completed.")
print(f"Outputs written to: {OUT}")
