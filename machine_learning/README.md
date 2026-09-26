# SmartQ Machine-Learning Submission & Integration Workspace

I keep the dedicated `SmartQ-Machine-Learning` repository for my ML research history, but I also copied its complete tracked contents into the main SmartQ repository for submission and integration.

## Why I keep both

I use the dedicated ML repository to preserve a clean research history.

For submission, I also want one repository that contains:

- the SmartQ application;
- the full 100,000-row dataset;
- all ML notebooks;
- all model evaluation and diagnostics;
- my learning/engineering notes;
- the deployable XGBoost model.

That is why this folder exists.

## Complete ML snapshot

The full copied ML repository is here:

`machine_learning/repository_snapshot/`

I verified the copy file-for-file against the ML repository:

- source tracked files: **49**
- copied tracked files: **49**
- missing files: **0**
- extra copied files: **0**

The copied source version came from:

- repository: `Katlegojack/SmartQ-Machine-Learning`
- branch: `main`
- source commit: `3c1b703ab3f4e9495117c6c5ad2d458120d1ca42`

I exclude only the source repository's internal `.git/` metadata because that is version-control metadata rather than project content.

## Dataset included

The full dataset is here:

`machine_learning/repository_snapshot/data/SmartQ_Synthetic_Operational_Dataset_100k.csv`

Verified properties:

- rows: **100,000**
- columns: **45**
- size: **35,059,222 bytes**

The snapshot also includes the large embedded-dataset notebook and the Word dataset documentation.

## Runtime XGBoost model included

I also packaged the selected deployable model here:

`machine_learning/runtime/smartq_wait_time_model.joblib`

Verified artifact size:

**148,707 bytes**

I generated this artifact by re-running the copied training pipeline through GitHub Actions.

The build reproduced the official validation comparison:

- Linear Regression MAE: **4.1146 min**
- Random Forest MAE: **2.6315 min**
- XGBoost MAE: **2.6302 min**

The script therefore selected XGBoost using my pre-defined lowest-validation-MAE rule.

The reproduced XGBoost final test result was:

- MAE: **2.5824 min**
- RMSE: **4.9561 min**

## Runtime compatibility

I keep the exact runtime versions beside the model:

`machine_learning/runtime/requirements.txt`

The packaged model was built with:

- Python 3.12
- pandas 2.2.3
- numpy 2.3.5
- scikit-learn 1.8.0
- XGBoost 3.1.3
- joblib 1.5.3

## Important current status

The packaged XGBoost model is now integrated into the logged-in Customer live queue prediction path.

I now:

- build the 22 live model inputs from Django queue state;
- load the model bundle once per Django process;
- return XGBoost predictions through the existing current-queue API;
- keep the deterministic ETA as fallback;
- reject unsafe numeric extrapolation outside the synthetic training domain;
- prevent early appointment customers from being called before service eligibility;
- log ML prediction-vs-outcome evidence;
- report ML quality to Manager/Admin;
- measure cold and warm prediction latency in CI.

The deterministic ETA remains part of SmartQ because I want the application to stay operational if ML is disabled, unavailable or outside its validated input range.

## Detailed documentation

My full explanation of this stage is here:

`docs/ML_SUBMISSION_PACKAGING_AND_INTEGRATION_PREP.md`

The runtime-specific explanation is here:

`machine_learning/runtime/README.md`
