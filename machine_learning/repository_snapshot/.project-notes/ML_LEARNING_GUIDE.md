# My SmartQ ML Learning Guide

> I use this file to learn the machine-learning concepts behind my own project.
>
> I do not assume that knowing a term means I understand it. For every important term, I want to know what it means, why it matters, how I used it, and what its limitation is.

---

## 1. What machine learning means in my project

I give a model examples of past queue situations together with the waiting time that actually happened.

Example:

- people ahead: 8
- counters open: 3
- queue pressure: high
- service: ID application
- actual wait: 24 minutes

The model studies many examples like this.

Later, when a new customer checks in, I give the model the current queue situation and ask it to estimate the waiting time.

That is supervised machine learning.

---

## 2. Supervised learning

Supervised learning means I have:

1. input variables;
2. the correct answer.

In SmartQ:

- inputs = queue conditions;
- correct answer = actual waiting time.

---

## 3. Dataset

A dataset is the collection of records I use for analysis and training.

My main SmartQ dataset has 100,000 synthetic operational records.

---

## 4. Observation / row

One row is one recorded SmartQ queue event or customer visit.

---

## 5. Feature

A feature is an input variable I give the model.

Examples:

- people ahead;
- open counters;
- queue pressure;
- service type;
- branch;
- time of day.

I think of features as the clues the model receives.

---

## 6. Target

The target is the answer I want the model to predict.

My target is:

`actual_wait_minutes`

---

## 7. Regression

Regression means predicting a number.

My SmartQ problem is regression because I predict a number of minutes.

---

## 8. Classification

Classification means predicting a category.

A future SmartQ example could be:

- no-show;
- not a no-show.

That would be a classification problem, not waiting-time regression.

---

## 9. Training data

Training data is what the model learns from.

I think of it as the study material.

I use 64,074 completed visits for training.

---

## 10. Validation data

Validation data is what I use while deciding which model/settings are best.

I think of it as a practice exam.

I use 14,665 visits for validation.

---

## 11. Test data

Test data is the final unseen exam.

I use 13,916 visits.

I do not want to choose the winning model using the test set.

---

## 12. Baseline

A baseline is a simple method I use for comparison.

I use:

- mean waiting time;
- deterministic SmartQ ETA.

If my complex model cannot beat something simple, then the complexity is difficult to justify.

---

## 13. MAE

MAE means **Mean Absolute Error**.

It answers:

> On average, how many minutes wrong am I?

If MAE = 2.5, I am about 2.5 minutes wrong on average.

Lower is better.

---

## 14. RMSE

RMSE means **Root Mean Squared Error**.

It is another prediction-error measure, but it punishes large mistakes more heavily.

I use it because a model that is usually accurate but sometimes makes huge mistakes should not look completely safe.

Lower is better.

---

## 15. R²

R² means **R-squared**.

It asks:

> How much of the variation in waiting time does my model explain?

For XGBoost, test R² is about 0.960.

I read that as about 96% of the variation in the synthetic test waiting times being explained by the fitted predictions.

I still need MAE/RMSE because R² does not tell me the error in minutes.

---

# LINEAR REGRESSION

## 16. How I understand Linear Regression

Linear Regression tries to create one mathematical relationship between inputs and the target.

A simplified example is:

`wait = base + people_ahead effect - open_counter effect + queue_pressure effect`

The real model has more variables.

---

## 17. Coefficient

A coefficient is the weight Linear Regression gives a variable.

A positive coefficient pushes the prediction upward.

A negative coefficient pushes it downward.

I do not automatically interpret a coefficient as causation.

---

## 18. Why I trained Linear Regression

I used it because it is:

- simple;
- fast;
- easy to compare;
- useful for statistics;
- a good lower-complexity benchmark.

Its weakness is that real queue behaviour is not perfectly linear.

---

## 19. R² vs adjusted R²

Regular R² can increase when I add variables, even weak ones.

Adjusted R² penalises unnecessary terms.

My OLS model has:

- R² ≈ 0.94855;
- adjusted R² ≈ 0.94853.

Because they are almost identical, I do not see a large artificial increase from simply adding more terms.

---

## 20. Residual

A residual is:

`actual - predicted`

If actual wait is 20 minutes and I predicted 16, the residual is +4.

Residuals help me see how the model fails.

---

## 21. p-value

A p-value helps me ask:

> If there were really no coefficient effect, how surprising would my result be?

A common threshold is p < 0.05.

I learned that a small p-value does not automatically mean a feature is practically important.

With a large dataset, very small effects can become statistically significant.

---

## 22. Confidence interval

A confidence interval gives me a plausible range for a coefficient estimate.

It reminds me that the coefficient is an estimate, not an exact universal truth.

---

## 23. Multicollinearity

Multicollinearity means several predictors carry similar information.

My queue variables have a lot of this because features such as people ahead, workload and queue pressure are naturally related.

This makes individual Linear Regression coefficients harder to interpret.

---

## 24. VIF

VIF means **Variance Inflation Factor**.

I use it to detect overlapping predictors.

Some of my queue features have VIF values above 30 or 40.

I do not automatically remove them from tree models, but I use the result as a warning when I interpret Linear Regression coefficients.

---

## 25. Heteroscedasticity

Heteroscedasticity means the error spread changes across conditions.

In my project, quiet queues can be easier to predict than severe congestion.

I found strong evidence of heteroscedasticity in the Linear Regression residuals.

That is why I use HC3 robust standard errors.

---

## 26. Robust standard error

A robust standard error is a safer estimate of coefficient uncertainty when classical variance assumptions do not hold perfectly.

It does not change the fitted coefficient.

It changes how I judge uncertainty, confidence intervals and p-values.

---

# RANDOM FOREST

## 27. Decision tree

A decision tree asks a sequence of questions.

Example:

> Are more than 5 people ahead?

Then:

> Are fewer than 3 counters open?

Then:

> Is queue pressure high?

The path ends in a prediction.

---

## 28. How I understand Random Forest

Random Forest builds many decision trees and averages their predictions.

Instead of trusting one tree, I combine many.

That generally makes prediction more stable.

---

## 29. n_estimators

This is the number of trees.

My selected Random Forest configuration uses 150 trees.

More trees usually improve stability but also increase computation.

---

## 30. max_depth

This limits how deep each tree can grow.

A very deep tree can memorise training data.

A very shallow tree can miss useful patterns.

---

## 31. min_samples_leaf

This controls how many examples must remain in a final tree leaf.

Larger values can make the model less eager to memorise tiny groups.

---

## 32. Overfitting

Overfitting means the model learns training data too specifically.

I think of it as memorising the revision sheet instead of learning the topic.

My Random Forest has a lower training MAE than validation MAE, which shows it fits training more aggressively.

---

# XGBOOST

## 33. Boosting

Boosting builds models sequentially.

Each new tree tries to correct mistakes left by earlier trees.

That is different from Random Forest, where many trees are mostly built independently.

---

## 34. XGBoost

XGBoost means **Extreme Gradient Boosting**.

I use it because it is a strong algorithm for structured/tabular data and can learn nonlinear interactions.

---

## 35. learning_rate

The learning rate controls how strongly each new tree changes the current prediction.

My selected XGBoost learning rate is 0.08.

A smaller value usually means slower, more careful learning.

---

## 36. subsample

My `subsample = 0.9`.

That means each tree uses about 90% of training rows.

I use this randomness to reduce overfitting risk.

---

## 37. colsample_bytree

My `colsample_bytree = 0.9`.

That means each tree gets about 90% of the available transformed features.

Again, I use randomness to improve generalisation.

---

## 38. reg_lambda

This is L2 regularisation strength.

I use it to discourage unnecessary model complexity.

My selected value is 2.0.

---

## 39. Why XGBoost won my official selection

Validation MAE:

- Linear Regression: 4.1146
- Random Forest: 2.6315
- XGBoost: 2.6302

I had already decided to select the lowest validation MAE.

XGBoost narrowly won.

I do not claim that the difference is large.

---

# MODEL QUALITY

## 40. Generalisation

Generalisation means the model works on new data it did not train on.

I use chronological validation/test periods to measure this.

---

## 41. Underfitting

Underfitting means the model is too simple to capture the real pattern.

Linear Regression can underfit nonlinear queue behaviour.

---

## 42. Train-vs-validation gap

I compare training and validation errors to understand overfitting.

Random Forest has a larger gap than XGBoost.

That tells me Random Forest fits training data more aggressively.

---

# FEATURE QUALITY

## 43. Feature importance

Feature importance tells me which variables the fitted model relied on.

It does not prove cause and effect.

---

## 44. Permutation importance

Permutation importance asks:

> What happens if I destroy one feature's information by shuffling it?

For XGBoost, shuffling workload ahead increases test MAE by about 7.54 minutes.

That tells me workload ahead is highly useful for prediction.

---

## 45. SHAP

SHAP helps me understand how much each feature pushes a prediction up or down.

My strongest average SHAP signals are:

- workload ahead;
- people ahead;
- arrival timing;
- effective counters;
- queue pressure.

I use SHAP to understand model behaviour, not to claim causation.

---

# STATISTICAL SIGNIFICANCE VS PRACTICAL IMPORTANCE

## 46. The difference I learned

A feature can be statistically significant but practically weak.

My peak vs non-peak comparison has a tiny p-value but a very small Cohen's d.

That happened because I have a large dataset.

So I now ask three questions:

1. Is the effect statistically detectable?
2. Is the effect large enough to matter?
3. Does the feature improve prediction?

---

# MY FULL WORKFLOW

## 47. The order I follow

```text
I define the problem
        ↓
I understand the data
        ↓
I validate the data
        ↓
I define the target
        ↓
I remove leakage
        ↓
I choose features
        ↓
I split train / validation / test
        ↓
I fit preprocessing on training only
        ↓
I build baselines
        ↓
I train Linear Regression
        ↓
I train Random Forest
        ↓
I train XGBoost
        ↓
I compare validation MAE/RMSE
        ↓
I select the model
        ↓
I evaluate the later test period
        ↓
I run diagnostics
        ↓
I integrate the model
        ↓
I monitor and retrain later
```

I follow this order because skipping early steps can make later accuracy numbers misleading.

---

# MY CURRENT RESULTS IN PLAIN ENGLISH

## 48. What my XGBoost score means

Selected XGBoost test:

- MAE ≈ 2.58 min
- RMSE ≈ 4.96 min
- R² ≈ 0.960

I interpret this as:

> On my synthetic test period, the selected model is about 2.6 minutes wrong on average, but some larger mistakes still exist.

---

## 49. My biggest weakness

Busy traffic MAE is about 7.94 minutes.

This means the model is much less reliable during severe congestion.

I treat that as an important limitation rather than hiding it.

---

## 50. What I want to be able to explain without notes

I want to be able to answer:

- Why is this regression?
- Why did I exclude no-shows?
- Why did I split chronologically?
- Why do I need validation data?
- Why do I keep the test set separate?
- Why do I use MAE and RMSE?
- Why did I train Linear Regression?
- Why did Random Forest help?
- How does XGBoost differ from Random Forest?
- What is overfitting?
- What is R²?
- What is a p-value?
- What is VIF?
- Why is multicollinearity important?
- What is a residual?
- What does permutation importance tell me?
- What does SHAP tell me?
- Why did I keep XGBoost after Random Forest had a slightly lower test MAE?
- Why can I not claim real-world accuracy yet?

If I can explain those clearly, then I understand the project instead of only owning the code.
