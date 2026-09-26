# My SmartQ Model Diagnostics and Statistical Analysis

## Why I added this stage

I did not want to stop after getting a low MAE and RMSE.

Those metrics tell me how wrong a model is, but they do not fully explain whether the model is stable, whether it is overfitting, whether the variables make sense, or where the model still fails.

So I added a separate diagnostics stage.

The main questions I wanted to answer were:

- Does each model still perform well on later unseen dates?
- Is any model overfitting?
- How much of the variation in waiting time does each model explain?
- Which Linear Regression variables are statistically significant?
- Are some variables repeating the same information?
- Are the main Linear Regression assumptions reasonable?
- Which variables actually matter to XGBoost prediction?
- Where does the selected model still struggle?

The most important lesson I took from this stage is:

> Statistical significance, model fit, feature usefulness and predictive accuracy are related, but they are not the same thing.

---

## 1. How well each model fits

I compared MAE, RMSE and R² across training, validation and test data.

| Model | Split | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| Linear Regression | Train | 4.2204 | 6.4640 | 0.9515 |
| Linear Regression | Validation | 4.1146 | 6.1452 | 0.9433 |
| Linear Regression | Test | 4.0645 | 6.4606 | 0.9313 |
| Random Forest | Train | 1.8234 | 2.8922 | 0.9903 |
| Random Forest | Validation | 2.6315 | 4.4920 | 0.9697 |
| Random Forest | Test | 2.5231 | 4.6425 | 0.9645 |
| XGBoost | Train | 2.4457 | 3.9787 | 0.9816 |
| XGBoost | Validation | 2.6302 | 4.3893 | 0.9711 |
| XGBoost | Test | 2.5824 | 4.9561 | 0.9596 |

### What I learned from the train/validation/test gaps

Random Forest has the biggest training advantage:

- Train MAE: 1.82
- Validation MAE: 2.63

That tells me Random Forest fits the training data more aggressively.

XGBoost has:

- Train MAE: 2.45
- Validation MAE: 2.63

Its gap is smaller.

I do not see catastrophic overfitting because all three models still perform well on later validation and test dates.

However, Random Forest looks more eager to fit the training data closely.

### What R² means to me

R² tells me how much of the variation in waiting time the model explains.

For XGBoost:

- Test R²: **0.9596**

I interpret that as the fitted predictions explaining about 96% of the variation in waiting time in the synthetic test period.

I do not use R² by itself because it does not tell me the average customer-facing error in minutes.

That is why I still need MAE and RMSE.

---

## 2. Why I fitted a statistical Linear Regression model

The scikit-learn Linear Regression is useful for prediction, but I also wanted a version that could give me:

- p-values;
- confidence intervals;
- robust standard errors;
- R²;
- adjusted R².

So I fitted a companion OLS model using the same underlying predictor ideas.

For categorical variables, I used reference-category encoding so the model matrix would be identifiable.

Because I later found heteroscedasticity, I used **HC3 robust standard errors**.

My statistical training fit was:

- R²: **0.94855**
- Adjusted R²: **0.94853**
- Training rows: **64,074**
- Estimated terms including intercept: **30**

Adjusted R² is almost the same as R², which tells me that adding the current terms is not artificially inflating the score by a large amount.

---

## 3. What I learned from p-values

Using HC3 robust standard errors, I found that 26 of the 30 estimated terms had p < 0.05.

Four terms were not statistically significant at the 5% level:

- Monday indicator
- Tuesday indicator
- Wednesday indicator
- Peak-period indicator

This does not mean those concepts are useless.

For example, my EDA clearly showed that peak periods have higher raw average waiting times.

However, once I already control for stronger queue-state variables such as:

- people ahead;
- workload ahead;
- open counters;
- queue pressure;

the simple peak-period flag adds little independent linear information.

That taught me something important:

> A variable can show a raw group difference and still become weak after I control for better explanatory variables.

I also learned not to worship p-values.

With more than 64,000 training rows, very small effects can become statistically significant.

So I do not translate:

`p < 0.05`

into:

"this feature is automatically important."

I also look at effect size, prediction error, permutation importance and SHAP.

---

## 4. Group significance tests and effect size

I ran simple group comparisons so I could understand the difference between statistical significance and practical size.

### General vs Priority

I found:

- General mean wait: 16.90 min
- Priority mean wait: 9.66 min
- p-value: effectively below 0.001
- Cohen's d: **0.258**

The difference is statistically clear, but the standardised effect is small-to-moderate rather than massive.

### Appointment vs Walk-in

I found:

- Appointment mean wait: 16.97 min
- Walk-in mean wait: 12.97 min
- p-value: 1.21e-74
- Cohen's d: **0.142**

The p-value is extremely small because I have a very large dataset, but the effect size is small.

### Peak vs Non-peak

I found:

- Peak mean wait: 16.97 min
- Non-peak mean wait: 14.47 min
- p-value: 3.16e-36
- Cohen's d: **0.089**

Again, the difference is statistically detectable, but the standardised effect is very small.

### Service type

I also ran a one-way ANOVA across:

- Collections
- ID Applications
- Passport Applications

I found:

- F = 0.4303
- p = **0.6503**
- eta-squared ≈ **0.000009**

I therefore did not find a meaningful raw overall waiting-time difference between the three service types.

This was useful because it reminded me that a feature can still participate in a multivariable model even when its simple raw group means are almost identical.

---

## 5. Multicollinearity and VIF

### What multicollinearity means to me

Multicollinearity means that several predictors carry very similar information.

This matters most when I want to interpret individual Linear Regression coefficients.

### Why I calculated VIF

VIF means **Variance Inflation Factor**.

I used it to measure how strongly each numeric predictor could be explained by the other predictors.

A rough interpretation is:

- around 1: little overlap
- above 5: noticeable overlap
- above 10: strong overlap

My largest VIF values were:

| Feature | VIF |
|---|---:|
| queue_pressure_index | 44.14 |
| people_ahead | 38.91 |
| serving_count | 38.76 |
| counter_utilisation | 38.54 |
| general_waiting | 35.16 |
| workload_minutes_ahead | 33.18 |
| open_general_counters | 7.79 |

### Why I am not surprised

These are engineered queue variables.

For example:

- queue pressure depends on demand and capacity;
- workload ahead is closely related to people ahead;
- counter utilisation is related to how many counters are active and serving.

So I expected some overlap.

### My decision

I did **not** automatically remove these variables from Random Forest or XGBoost.

VIF is mainly warning me that I should not interpret every Linear Regression coefficient as a clean independent causal effect.

If my main research goal later becomes coefficient interpretation, I could build a reduced Linear Regression with fewer overlapping features.

For the current project, prediction is the main goal.

---

## 6. Linear Regression assumptions

### Heteroscedasticity

I ran the Breusch-Pagan test.

I found:

- LM statistic ≈ 13,674.78
- p-value ≈ 0

This tells me the residual variance is not constant.

In simple English:

> My Linear Regression errors are not equally spread under all queue conditions.

That makes sense because quiet queues are easier to predict than extreme congestion.

### Residual normality

I ran the Jarque-Bera test.

I found:

- statistic ≈ 163,042
- p-value ≈ 0
- residual skewness ≈ 0.85
- residual kurtosis ≈ 10.63

So the residuals are not normally distributed and they have heavy tails.

With a dataset this large, formal tests are very sensitive, but the high kurtosis also confirms that the error distribution has extreme cases.

### Durbin-Watson

I found:

- Durbin-Watson ≈ **1.91**

A value near 2 does not show obvious strong first-order autocorrelation in the fitted row order.

I do not treat that as a complete time-series test.

My main protection against unrealistic temporal leakage is still the chronological split.

### What I changed because of these tests

Because heteroscedasticity is present, I use HC3 robust standard errors for the Linear Regression p-values and confidence intervals.

I still judge prediction mainly using unseen validation/test performance.

---

## 7. Negative predictions

A regression model can mathematically predict a value below zero even when the real-world quantity cannot be negative.

On my test set:

- Linear Regression produced 2,192 raw negative predictions.
- XGBoost produced 962 raw negative predictions.
- Random Forest produced 0.

For XGBoost, the negative values are usually small:

- minimum ≈ -1.04 min
- median negative prediction ≈ -0.10 min

A customer cannot wait -0.10 minutes, so I explicitly clip customer-facing predictions using:

`max(0, prediction)`

I see this as a practical constraint, not hidden model manipulation.

---

## 8. Permutation importance

I wanted a feature-importance method that measures actual predictive damage.

So I used **permutation importance**.

The idea is simple:

1. I measure normal test MAE.
2. I shuffle one feature.
3. I predict again.
4. I see how much worse MAE becomes.

If shuffling a feature destroys performance, that feature was useful.

My baseline XGBoost test MAE was:

**2.5824 minutes**

Largest MAE increases after shuffling:

| Feature | MAE increase |
|---|---:|
| workload_minutes_ahead | +7.54 min |
| people_ahead | +4.15 min |
| arrival_offset_minutes | +3.30 min |
| effective_open_counters | +2.70 min |
| queue_pressure_index | +0.54 min |
| open_general_counters | +0.31 min |
| counter_utilisation | +0.22 min |
| queue_type | +0.20 min |

This gave me strong evidence that workload, queue position and serving capacity really matter for prediction.

---

## 9. SHAP / TreeSHAP

I also used XGBoost TreeSHAP.

SHAP helps me answer:

> How much did each feature push the prediction up or down?

On a fixed 5,000-row test sample, my strongest average absolute SHAP contributions were:

| Feature | Mean absolute SHAP contribution |
|---|---:|
| workload_minutes_ahead | 7.10 |
| people_ahead | 5.74 |
| arrival_offset_minutes | 3.88 |
| effective_open_counters | 2.59 |
| queue_pressure_index | 1.47 |
| open_general_counters | 0.76 |

The useful thing is that SHAP and permutation importance tell me a similar story.

Both say that the main predictive signals are:

- how much work is ahead;
- how many people are ahead;
- how much serving capacity is available;
- how pressured the queue is.

That makes operational sense.

---

## 10. Do I think XGBoost is a good fit?

For my **synthetic SmartQ dataset**, yes.

My evidence is:

- validation MAE ≈ 2.63 min;
- test MAE ≈ 2.58 min;
- test R² ≈ 0.960;
- validation and test performance are close;
- it strongly beats the mean baseline;
- it improves on the deterministic SmartQ ETA;
- permutation importance and SHAP point to sensible operational variables.

But I also keep the limitations visible:

- all training/evaluation data is synthetic;
- busy-traffic MAE is much worse;
- some engineered queue variables overlap heavily;
- raw XGBoost can produce small negative values;
- real-world accuracy is still unknown.

So my conclusion is:

> I consider XGBoost a strong prototype fit for the synthetic SmartQ data and a reasonable integration candidate. I do not treat it as proven production performance until I validate it on representative live data.

---

## 11. Did diagnostics change my selected model?

No.

I kept XGBoost.

The diagnostics did not give me a strong methodological reason to break my predefined validation-MAE selection rule.

Instead, they helped me understand the choice better.

I learned that:

- XGBoost generalises well on later synthetic dates;
- Random Forest fits the training data more aggressively;
- Linear Regression coefficient interpretation is affected by multicollinearity;
- the classical constant-variance and normal-error assumptions are not perfect;
- HC3 robust inference is more appropriate;
- p-values are not the same as predictive usefulness;
- workload ahead, people ahead and serving capacity are strong signals;
- busy queues remain my biggest modelling weakness.

That is exactly why I added diagnostics: not to force a different winner, but to understand what my model is doing.
