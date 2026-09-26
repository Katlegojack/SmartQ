# My SmartQ Machine-Learning Engineering Worklog

> I keep this file as my detailed internal record of what I did, why I did it, what alternatives I considered, what trade-offs I accepted, what I learned, and what I still need to finish.
>
> I wrote it in plain English because I want to understand and defend the work myself. I do not want this project to become a collection of results that I cannot explain.

---

## 1. Why I created a separate ML repository

I created a separate machine-learning repository because I wanted to keep model experiments away from the main SmartQ application until the ML work was stable enough to integrate.

This gave me:

- a clean ML commit history;
- a safe place for the dataset and notebooks;
- separate documentation;
- reproducible training scripts;
- clear experiment outputs;
- a simpler path for learning.

The trade-off is that I now have two repositories to keep aligned, but I think that is better than mixing experimental ML code directly into the production-style SmartQ application too early.

---

## 2. The ML problem I decided to solve

I am predicting:

`actual_wait_minutes`

This is the number of minutes between customer check-in and the customer being called.

I chose this because it directly supports the SmartQ user experience.

I am not predicting total time inside the branch because that would include service duration and answer a different question.

---

## 3. Why I used synthetic data

I do not yet have enough real production SmartQ data.

I therefore created a synthetic operational dataset with 100,000 rows and 45 columns.

I included:

- appointments;
- walk-ins;
- General and Priority lanes;
- multiple branches;
- multiple services;
- early, on-time and late arrivals;
- no-shows;
- cancellations;
- queue position;
- people ahead;
- open counters;
- queue pressure;
- service duration;
- waiting-time outcomes;
- time-based variables.

I used synthetic data because my proposal allows simulated/prototype-generated data and because I needed enough records to complete the full ML pipeline.

The main trade-off is obvious:

> I can demonstrate the method, but I cannot claim real-world production accuracy yet.

---

## 4. What I did before modelling

I started with EDA and data-quality checks.

I checked:

- dataset size;
- status counts;
- missing values;
- waiting-time distribution;
- branch patterns;
- time patterns;
- lane differences;
- booking-source differences;
- queue-pressure relationships;
- impossible timestamps;
- negative waits;
- broken queue positions.

I found zero structural queue/timestamp violations in the checks I defined.

I did this because a model can learn bad data perfectly well. A low error means very little if the records are logically impossible.

---

## 5. Why I used completed visits only

The full dataset contains:

- 92,655 completed visits;
- 5,096 no-shows;
- 2,249 cancellations.

For waiting-time regression, I used only completed visits.

I did not give no-shows or cancellations a waiting time of zero.

Zero would mean that the customer arrived and was served immediately, which is not true.

I kept those records in the master dataset because they may be useful later for different problems such as no-show prediction.

---

## 6. My data-leakage rule

I only use information that would really be available when the prediction is made.

I excluded:

- call time;
- actual wait;
- actual service duration;
- service start time;
- service completion time;
- outcome-derived flags;
- final counter assignment.

I did this because using future information would create data leakage and make the model look much better than it really is.

---

## 7. Why I excluded the existing deterministic ETA from ML inputs

The dataset contains `baseline_eta_minutes`.

I kept it as a benchmark instead of feeding it to the official ML models.

I did this because I wanted to know whether Linear Regression, Random Forest and XGBoost could learn waiting time directly from queue conditions.

A hybrid model that learns the error of the deterministic ETA could be useful later, but I kept it out of the official experiment to keep the methodology clean and easy to defend.

---

## 8. How I handled missing values

The main missing values inside completed visits are recent-history fields.

For example, early in the day there may not yet be enough completed customers to calculate a recent average.

I did not delete those rows.

For numeric missing values, I used the training-set median.

I chose the median because queue data can be skewed by extreme congestion and the median is less sensitive to those extremes than the mean.

For categorical missing values, I used the most frequent training category.

I fitted these rules on training data only so validation/test information could not leak backward.

---

## 9. How I encoded categories

I used one-hot encoding for categories such as:

- branch;
- service;
- booking source;
- queue type;
- weekday;
- peak-period flag.

I did not use ordinal encoding because there is no valid numerical order between branch names or service codes.

I also avoided target encoding because it would add complexity and create more leakage risk.

---

## 10. Why I did not scale every numeric feature

I did not add StandardScaler to the official pipeline.

Random Forest and XGBoost do not need scaled features because they work through tree splits.

Linear Regression can still fit the numeric ranges I have.

Scaling could help coefficient comparability, but that was not my main goal.

I chose simplicity and explainability over adding a transformation that was not necessary for this comparison.

---

## 11. My chronological split

I split completed visits by whole operating dates:

| Split | Rows | Dates |
|---|---:|---|
| Train | 64,074 | 2 Jan – 16 Jun |
| Validation | 14,665 | 17 Jun – 22 Jul |
| Test | 13,916 | 23 Jul – 27 Aug |

I did not randomly shuffle all customers.

I wanted the experiment to resemble real deployment:

> I learn from earlier queue behaviour and predict later queue behaviour.

I also wanted to stop customers from the same operating day appearing in both training and test data.

The trade-off is that chronological splitting can be harder than random splitting, but I prefer the more realistic evaluation.

---

## 12. Why I kept separate validation and test sets

I use validation data to make decisions.

I use test data as the final unseen exam.

I used validation for:

- model comparison;
- limited parameter tuning;
- official model selection.

I used the final test period after the selection rule was fixed.

I later calculated diagnostic test metrics for all models, but I did not use them to change the winner.

---

## 13. Why I used baselines

I used a mean-wait baseline because I needed to prove that ML was better than simply predicting one average for everyone.

I also kept the existing deterministic SmartQ ETA as an engineering benchmark.

This lets me answer two different questions:

1. Does ML beat a simple guess?
2. Does ML improve on the queue logic I already had?

---

## 14. Why I trained Linear Regression

I trained Linear Regression because it is simple, fast and statistically interpretable.

It gave me a useful reference before moving to more complex nonlinear models.

Its weakness is that queue behaviour is not perfectly linear.

---

## 15. Why I trained Random Forest

I trained Random Forest because it can capture nonlinear interactions.

Instead of one tree, it builds many trees and averages their predictions.

This makes it more flexible than Linear Regression.

Its trade-off is that it is larger, less directly interpretable and can fit training data aggressively.

---

## 16. Why I trained XGBoost

I trained XGBoost because it is strong on structured/tabular data and can learn nonlinear relationships.

It builds trees sequentially so later trees correct earlier mistakes.

Its trade-off is higher complexity and greater tuning risk.

---

## 17. How much tuning I did

I intentionally kept tuning limited.

For Random Forest I compared two controlled configurations.

For XGBoost I compared two controlled configurations.

I did not run a massive hyperparameter search.

I did this because:

- the proposal calls for limited tuning;
- I wanted to avoid overfitting validation;
- I wanted to understand the settings;
- I wanted the work to stay appropriate for the project scope.

---

## 18. My validation results

| Model | MAE | RMSE |
|---|---:|---:|
| Linear Regression | 4.1146 | 6.1452 |
| Random Forest | 2.6315 | 4.4920 |
| XGBoost | **2.6302** | **4.3893** |

I selected XGBoost because I had already decided to use lowest validation MAE.

I do not describe XGBoost as dramatically better than Random Forest because the difference is tiny.

---

## 19. My final test results

| Model | MAE | RMSE |
|---|---:|---:|
| Mean baseline | 14.9850 | 24.8143 |
| Deterministic ETA | 4.6386 | 6.3683 |
| Linear Regression | 4.0645 | 6.4606 |
| Random Forest | 2.5231 | 4.6425 |
| Selected XGBoost | 2.5824 | 4.9561 |

Random Forest happened to have a slightly lower test MAE.

I did not switch models because that would mean using the final test set for model selection.

The difference is only around 3.5 seconds of MAE anyway.

I preferred a clean method over chasing a tiny post-test advantage.

---

## 20. What I learned from busy traffic

XGBoost test MAE:

- Low traffic: 1.22 min
- Moderate traffic: 2.95 min
- Busy traffic: 7.94 min

This is one of the most important limitations in my project.

The model is much weaker under severe congestion.

I do not hide that result.

---

## 21. What I learned from R²

Test R²:

- Linear Regression: 0.9313
- Random Forest: 0.9645
- XGBoost: 0.9596

This tells me all three explain a large amount of variation in the synthetic test data.

I still use MAE and RMSE because R² does not tell me the average error in customer-facing minutes.

---

## 22. What I learned about overfitting

Random Forest:

- Train MAE: 1.82
- Validation MAE: 2.63

XGBoost:

- Train MAE: 2.45
- Validation MAE: 2.63

Random Forest fits training data more aggressively.

I do not see catastrophic overfitting because validation/test performance remains strong, but the gap is useful evidence about model behaviour.

---

## 23. Why I added statistical inference

I fitted a companion OLS model because I wanted:

- p-values;
- confidence intervals;
- robust standard errors;
- R²;
- adjusted R².

I used HC3 robust standard errors after I found heteroscedasticity.

---

## 24. What I learned from p-values

Most terms were statistically significant at p < 0.05.

But Monday, Tuesday, Wednesday and the peak-period indicator were not significant after controlling for the other predictors.

This taught me that a raw group difference can become weak after stronger queue-state variables are included.

I also learned that statistical significance does not automatically mean practical importance.

---

## 25. What I learned from effect sizes

I compared p-values with Cohen's d.

Some group differences had extremely small p-values but small effect sizes.

This happened because the dataset is large.

I now separate:

- statistically detectable;
- practically large;
- predictively useful.

Those are different ideas.

---

## 26. What I learned from VIF

Some queue features have very high VIF because they overlap.

Examples include:

- queue pressure;
- people ahead;
- counter utilisation;
- general waiting;
- workload ahead.

I kept them in tree models because prediction is my main goal.

I simply avoid over-interpreting individual Linear Regression coefficients as independent causal effects.

---

## 27. What I learned from residual tests

I found heteroscedasticity and non-normal residuals in the Linear Regression diagnostics.

That means error behaviour changes across queue conditions and has heavy tails.

I therefore use robust standard errors for inference and judge prediction mainly on unseen data.

---

## 28. What I learned from negative predictions

Raw XGBoost can produce small negative predictions.

I clip customer-facing predictions to zero.

I do this because the real-world quantity cannot be negative.

Random Forest produced no negative test predictions, while Linear Regression produced many more.

---

## 29. What I learned from permutation importance

When I shuffled `workload_minutes_ahead`, XGBoost test MAE became much worse.

The largest MAE increases came from:

- workload ahead;
- people ahead;
- arrival offset;
- effective open counters;
- queue pressure.

This gave me strong evidence that these variables carry real predictive information inside the synthetic dataset.

---

## 30. What I learned from SHAP

TreeSHAP told me a similar story.

The largest average contributions came from:

- workload ahead;
- people ahead;
- arrival timing;
- effective counters;
- queue pressure.

I like this because two different diagnostics support the same operational explanation.

---

## 31. Why I did not add a neural network

I did not add deep learning because it is outside the proposal scope and unnecessary for this tabular problem.

I wanted to finish the declared models properly rather than add complexity just to sound advanced.

---

## 32. Why I did not turn this into a time-series project

My current question is individual waiting-time prediction.

A time-series model would answer a different question, such as future queue length or future arrivals.

Those can be future SmartQ features, but I kept this project focused.

---

## 33. Why I kept extreme valid waits

I did not delete long waits just because they made RMSE worse.

If a long wait is logically valid, it represents an important congestion case.

I only want to remove outliers when I have evidence that they are bad data.

---

## 34. Why I generate the binary model instead of treating it as source code

I keep code, parameters, data and results under version control.

I generate the `.joblib` model from the training script.

I do this because a binary model is hard to review and can depend on library versions.

The reproducible source of truth is more useful to me than an unexplained binary file.

---

## 35. My planned integration behaviour

I want Django to:

1. calculate live queue features;
2. call the predictor;
3. return the ML estimate;
4. fall back to deterministic ETA if ML fails;
5. log predictions and later actual waits;
6. measure prediction latency.

I do not want ML failure to break the queue application.

---

## 36. What I will not claim

I will not claim:

- XGBoost is always the best queue model;
- the 100,000 rows are real customers;
- the synthetic test MAE is guaranteed in a real branch;
- feature importance proves causation;
- Random Forest failed;
- the test set selected XGBoost.

I will say:

> I selected XGBoost because it narrowly achieved the lowest validation MAE in my synthetic SmartQ experiment.

---

## 37. What is still left

My main remaining ML engineering work is integration.

I still need to:

- connect the model to SmartQ Django;
- calculate the live feature values correctly;
- add fallback behaviour;
- expose the prediction through the API/UI;
- measure latency;
- add integration tests;
- log future real outcomes.

---

## 38. My biggest lesson

The model itself is only part of machine learning.

Most of the important work was:

- defining the target;
- validating the data;
- avoiding leakage;
- splitting data correctly;
- keeping a baseline;
- choosing metrics;
- controlling tuning;
- preserving the test set;
- understanding assumptions;
- documenting limitations;
- making the process reproducible.

I would rather have a slightly worse score with a method I can defend than a slightly better score produced by bad evaluation.

---

## 39. How I document work from now on

Whenever I make a meaningful change, I want evidence in one or more of these places:

- notebooks for exploration;
- `src/` for reusable code;
- `results/` for machine-readable outputs;
- `docs/` for formal documentation;
- this file for my detailed engineering reasoning;
- `ML_LEARNING_GUIDE.md` for plain-English ML learning.

I want the repository to show not only what I built, but how I thought about it.
