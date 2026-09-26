# My SmartQ ML Submission Packaging and Integration Preparation

## Why I added this documentation

I reached the point where my machine-learning experiment was complete enough to move toward the main SmartQ application.

At this stage I did not want the project to depend on two separate repositories during submission. I also did not want to lose the clean ML research history I had already built.

So I kept the dedicated `SmartQ-Machine-Learning` repository as my ML research source, but I copied its complete tracked contents into the main SmartQ repository and then packaged the selected XGBoost model as a runtime artifact.

This gives me one submission repository that contains both:

- the SmartQ application; and
- the full machine-learning evidence used to build the prediction model.

---

## 1. Full ML repository snapshot inside SmartQ

I copied the complete tracked contents of:

`Katlegojack/SmartQ-Machine-Learning`

into:

`machine_learning/repository_snapshot/`

I verified the copy file-for-file.

Verification result:

- source tracked files: **49**
- copied tracked files: **49**
- missing files: **0**
- extra copied files: **0**

I did this because I do not want a marker or reviewer to open one repository and then discover that the dataset, notebooks or evaluation evidence are somewhere else.

---

## 2. Dataset included in the main SmartQ repository

The full synthetic dataset is included at:

`machine_learning/repository_snapshot/data/SmartQ_Synthetic_Operational_Dataset_100k.csv`

Verified properties:

- rows: **100,000**
- columns: **45**
- file size: **35,059,222 bytes**
- synthetic-data version: **smartq-synthetic-v1.0**

I include the real dataset file because the submission should contain the evidence used for EDA, training and evaluation.

I also include the self-contained embedded-dataset notebook:

`machine_learning/repository_snapshot/notebooks/SmartQ_ML_100k_Embedded_Dataset.ipynb`

and the dataset documentation:

`machine_learning/repository_snapshot/docs/SmartQ_100k_Synthetic_Dataset_Documentation.docx`

---

## 3. ML notebooks included

The main SmartQ repository now contains my complete numbered ML workflow:

- `01_Data_Understanding_EDA.ipynb`
- `02_Data_Preparation.ipynb`
- `03_Model_Training_Evaluation.ipynb`
- `04_Model_Diagnostics_Statistical_Analysis.ipynb`

I keep these because I want the submission to show the full process instead of only the final model.

The notebooks explain:

- how I understood the data;
- how I prevented leakage;
- how I prepared features;
- why I split chronologically;
- how I trained the three models;
- how I selected XGBoost;
- how I checked R², residuals, significance, VIF, permutation importance and SHAP.

---

## 4. Runtime model packaged

I also generated and committed the deployable model bundle at:

`machine_learning/runtime/smartq_wait_time_model.joblib`

Verified artifact size:

**148,707 bytes**

I did not create this binary manually.

I used GitHub Actions to re-run:

`machine_learning/repository_snapshot/src/train_models.py`

against the included dataset.

The training pipeline reproduced the same official validation results:

| Model | Validation MAE | Validation RMSE |
|---|---:|---:|
| Linear Regression | 4.1146 min | 6.1452 min |
| Random Forest | 2.6315 min | 4.4920 min |
| XGBoost | **2.6302 min** | **4.3893 min** |

The training script selected XGBoost using the same rule I had already documented:

> I select the official model with the lowest validation MAE.

The reproduced XGBoost final test result was:

- MAE: **2.5824 minutes**
- RMSE: **4.9561 minutes**

---

## 5. Why I package preprocessing with the model

The runtime joblib bundle contains:

- the fitted preprocessing transformer;
- the selected XGBoost model;
- the ordered feature list;
- the target name;
- model metadata.

I package preprocessing with the model because the live Django application must transform its inputs exactly the same way as the training pipeline.

If I trained with one encoding/imputation process and predicted with another, the model could receive the wrong feature structure.

---

## 6. Runtime compatibility versions

I pinned the versions used to build the runtime artifact:

- Python 3.12
- pandas 2.2.3
- numpy 2.3.5
- scikit-learn 1.8.0
- XGBoost 3.1.3
- joblib 1.5.3

I keep these in:

`machine_learning/runtime/requirements.txt`

I did this because serialized ML artifacts can depend on library versions.

---

## 7. Exact feature contract I still need to build from live Django state

The model expects these 22 inputs:

```text
arrival_offset_minutes
people_ahead
general_waiting
priority_waiting
serving_count
open_general_counters
open_priority_counters
effective_open_counters
counter_utilisation
queue_pressure_index
workload_minutes_ahead
recent_avg_service_minutes_10
recent_avg_wait_minutes_10
recent_throughput_60m
service_target_minutes
hour_of_day
branch_code
service_code
booking_source
queue_type
day_of_week
is_peak_period
```

The next engineering task is not simply "call XGBoost."

I first need to calculate these features correctly from the real SmartQ queue state.

I must not fake values just to make the model run.

---

## 8. Why machine learning is not active in Django yet

The model is now trained, reproduced and packaged, but I have **not yet connected it to the live queue API**.

The current main SmartQ queue flow still uses the deterministic live ETA.

The existing forecasting summary still correctly describes ML as not active.

I will only change that status after:

- live feature construction is implemented;
- the model loads successfully in Django;
- fallback behaviour works;
- prediction is exposed through the queue API;
- latency is measured;
- integration tests pass.

I keep this distinction because "model file exists" and "model is safely integrated into the system" are not the same thing.

---

## 9. Deterministic ETA remains my fallback

I do not want XGBoost to become a single point of failure.

My planned prediction flow is:

```text
Customer enters queue
        ↓
I build the 22 live features
        ↓
Try XGBoost prediction
        ↓
Prediction succeeds?
   ┌────┴────┐
  yes       no
   ↓         ↓
ML ETA   deterministic ETA
   └────┬────┘
        ↓
Customer-facing wait estimate
```

I keep the deterministic ETA because the queue should still work if:

- the model file cannot load;
- a required feature cannot be calculated;
- a prediction raises an error;
- the ML dependencies are unavailable.

---

## 10. Submission structure after this stage

The main SmartQ repository now contains:

```text
SmartQ/
├── machine_learning/
│   ├── README.md
│   ├── repository_snapshot/
│   │   ├── data/
│   │   │   └── SmartQ_Synthetic_Operational_Dataset_100k.csv
│   │   ├── notebooks/
│   │   ├── docs/
│   │   ├── results/
│   │   ├── src/
│   │   ├── .project-notes/
│   │   └── ...
│   └── runtime/
│       ├── smartq_wait_time_model.joblib
│       ├── README.md
│       └── requirements.txt
├── queues/
├── bookings/
├── counters/
├── dashboard/
├── frontend/
└── ...
```

This means my application code, dataset, ML notebooks, model evidence and deployable model are now accessible from one submission repository.

---

## 11. What I learned from this packaging stage

I learned that finishing model training is not the same as finishing ML engineering.

A useful ML project also needs:

- reproducible training;
- a versioned model artifact;
- dependency compatibility;
- a clear feature contract;
- a safe application integration path;
- fallback behaviour;
- monitoring;
- traceable documentation.

The model is now ready to be integrated, but I am deliberately not calling the ML component fully deployed until the Django integration is complete.

---

## 12. Current status

### Complete

- 100,000-row dataset generated and validated;
- EDA completed;
- data preparation completed;
- Linear Regression trained;
- Random Forest trained;
- XGBoost trained;
- validation-based model selection completed;
- final test evaluation completed;
- statistical/model diagnostics completed;
- complete ML repository copied into SmartQ;
- XGBoost runtime artifact reproduced and packaged;
- runtime dependency versions pinned.

### In progress

- live Django feature construction;
- runtime model loading inside SmartQ;
- deterministic fallback integration;
- API/UI prediction exposure;
- latency benchmark;
- integration tests;
- live prediction/outcome logging.

My next step is therefore **actual Django ML integration**, not more offline model training.
