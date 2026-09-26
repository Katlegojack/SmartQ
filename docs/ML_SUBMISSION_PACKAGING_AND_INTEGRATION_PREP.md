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


---

## 13. Live Django integration I implemented

I connected the packaged XGBoost model to the existing Customer live-queue API instead of creating a separate disconnected ML API.

The live request path is now:

```text
Customer current queue request
        ↓
SmartQ reads the live QueueTicket / Booking / Counter state
        ↓
I build the 22 trained ML inputs
        ↓
I validate that critical numeric inputs are still inside the training domain
        ↓
I run the saved preprocessing transformer
        ↓
I run the packaged XGBoost model
        ↓
I clip impossible negative waiting time to zero
        ↓
Customer receives the estimated wait
```

If ML cannot be used safely, SmartQ keeps the deterministic ETA as the fallback.

I did this because adding machine learning should not make the queue system less reliable.

## 14. Why I fixed appointment service eligibility during integration

One important engineering lesson from my abandoned Day 62 experiment was that **check-in time and service-eligibility time are not always the same thing**.

An appointment customer can check in before the appointment time.

That does not mean the customer should be called immediately.

I added a service-eligibility contract:

- Walk-in: eligible at check-in.
- Appointment: eligible at `max(check_in_at, appointment_at)`.

I then changed counter call-next logic so an early checked-in appointment is not called before the booked time.

I also changed deterministic ETA logic so an idle counter does not incorrectly turn an early appointment into a zero-minute wait.

This fix matters independently of machine learning. The model should be integrated into a queue workflow that is already logically correct.

## 15. How I build the 22 live inputs

I map the current Django queue state into the same feature names used during training.

Examples:

- `people_ahead`: eligible same-lane customers ahead;
- `general_waiting` and `priority_waiting`: live waiting counts;
- `serving_count`: customers currently being served;
- `open_general_counters` / `open_priority_counters`: live open capacity;
- `effective_open_counters`: capacity for the customer's own lane;
- `counter_utilisation`: serving customers divided by total open counters;
- `queue_pressure_index`: waiting + serving demand divided by open capacity;
- `workload_minutes_ahead`: remaining same-lane service workload plus target service time of eligible customers ahead;
- recent service/wait history: completed outcomes already known before prediction;
- `recent_throughput_60m`: services completed in the previous 60 minutes;
- branch/service/queue/time variables: taken from the current booking and local check-in time.

I deliberately do not use post-outcome fields.

## 16. One feature is currently a live proxy

The synthetic training data has a separate physical `arrival_at` and `check_in_at`.

The current SmartQ production-style Booking model stores `checked_in_at`, but it does not store a separate physical-arrival timestamp.

Because of that, for appointments I currently calculate:

`arrival_offset_minutes = checked_in_at - appointment_at`

instead of the synthetic generator's more precise:

`arrival_at - appointment_at`

In the synthetic data, check-in followed arrival by only a small handoff delay, so the values are related, but they are not literally identical.

I document this instead of pretending feature parity is perfect.

A future data-model improvement would be to add a dedicated `arrived_at` field so the live feature matches the training definition exactly.

## 17. Why I added a training-domain guard

Tree models can still return a number when I give them a queue state far outside anything they saw during training.

That does not mean the number has reliable validation evidence.

I therefore added conservative runtime bounds based on the synthetic dataset:

```text
arrival_offset_minutes       -25 to 25
people_ahead                   0 to 41
effective_open_counters        1 to 5
queue_pressure_index           0 to 14.667
workload_minutes_ahead         0 to 600.3
service_target_minutes        10 to 20
```

If a critical live numeric value falls outside those ranges, I do **not** force XGBoost to extrapolate.

I fall back to the deterministic ETA and expose the fallback reason in the prediction metadata.

I did this because a safe fallback is better than presenting an unsupported ML number as if it had the same 2.58-minute test MAE.

## 18. How I load the model

I cache the joblib model bundle with a one-item process cache.

This means I do not reload the 149 KB model file from disk every time the Customer page refreshes.

The first prediction loads the model; later predictions reuse it in that Django process.

This reduces unnecessary I/O and supports the latency requirement.

## 19. Prediction metadata returned by the API

The Customer current-queue prediction now includes both the customer-facing estimate and engineering metadata:

```text
estimated_wait_seconds
estimated_wait_time
deterministic_estimated_wait_seconds
ml_predicted_wait_minutes
prediction_model
model_status
machine_learning_enabled
prediction_fallback_reason
prediction_generated_at
```

When XGBoost succeeds:

```text
prediction_model = xgboost
model_status = active
machine_learning_enabled = true
```

If ML fails or the queue state is outside my validated training domain, the deterministic estimate remains available.

## 20. Prediction-vs-outcome logging

I extended `QueueForecastObservation` so I can save:

- the deterministic estimate;
- the ML estimate;
- which prediction model was used;
- when the prediction was generated;
- the eventual actual waiting time;
- deterministic residual;
- ML residual.

This is important because real deployment should create evidence for the next model version.

Instead of permanently trusting synthetic-data performance, I can later compare live predictions with actual waits and retrain using representative operational data.

## 21. Manager/Admin ML quality reporting

I extended the forecasting summary so management reporting can show:

- deterministic wait MAE;
- deterministic wait bias;
- ML wait MAE;
- ML wait bias;
- service-target MAE;
- service-target bias;
- whether the ML runtime is active;
- which prediction model is active.

I also updated the History & Recovery workspace so it no longer claims that no ML model is active when the runtime model is available.

## 22. Integration tests I added

I added focused tests for:

- exact 22-feature contract;
- real packaged XGBoost loading and prediction;
- warm inference below two seconds;
- deterministic fallback when ML is disabled;
- deterministic fallback outside the validated training domain;
- appointment not being called before service eligibility;
- Day 58 ETA behaviour after the eligibility fix;
- Day 59 forecasting behaviour after ML activation.

I also added a focused GitHub Actions workflow so these ML integration regressions can be checked separately from the full SmartQ suite.

## 23. What I learned from integration

I learned that model integration is not just:

> load joblib -> call predict()

The harder engineering work is making sure:

- live feature definitions match training definitions;
- the queue lifecycle itself is correct;
- the model is not given future information;
- the model is not trusted far outside its training domain;
- there is a deterministic fallback;
- prediction latency is acceptable;
- later outcomes are recorded for monitoring;
- the API and frontend tell the truth about which model is active.

That is the difference between demonstrating a model in a notebook and engineering an ML-assisted system.


## 24. Measured prediction latency

I measured the live Django prediction path in GitHub Actions using the real packaged XGBoost artifact and the same feature-building code used by SmartQ.

The measured result was:

```text
Cold prediction: 0.924552 seconds
Warm prediction: 0.018159 seconds
Requirement:     < 2.000000 seconds
```

Both measurements are below my project requirement.

### What cold and warm mean

**Cold prediction** means I first cleared the in-process model cache, so the timed call included loading the joblib bundle and making the prediction.

**Warm prediction** means the bundle was already loaded, which represents normal repeated Customer queue refreshes inside the same Django process.

The warm path was about 18 milliseconds in this CI measurement.

I treat the numbers as reproducible test-environment measurements, not a guarantee that every production server/network response will have identical timing.

The important conclusion is that the model-inference path itself is comfortably inside the two-second requirement, including the first uncached call in this test environment.
