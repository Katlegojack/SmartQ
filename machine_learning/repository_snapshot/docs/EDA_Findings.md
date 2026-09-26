# My SmartQ Data Understanding / EDA Findings

## Why I did EDA first

Before I trained any model, I needed to understand whether my data made sense.

EDA means **Exploratory Data Analysis**. I used it to inspect the data, understand the waiting-time target, find missing values, check whether queue behaviour looked logical, and identify possible modelling problems before I trusted any model score.

I did not want to train a model on data I had not inspected.

## What I found in the dataset

My dataset contains:

- **100,000 total records**
- **45 columns**
- **92,655 completed visits**
- **5,096 no-shows**
- **2,249 cancelled visits**

For waiting-time regression, I used only completed visits because no-shows and cancelled visits do not have a genuine completed waiting-time outcome.

## My prediction target

I used:

`actual_wait_minutes`

This represents the time between customer check-in and the customer being called for service.

For completed visits I found:

- mean wait: **16.03 minutes**
- median wait: **7.50 minutes**
- 95th percentile: **61.73 minutes**
- maximum: **358.10 minutes**

The mean is much higher than the median, which told me the waiting-time distribution is right-skewed. In simple English, most customers wait relatively little, but a smaller number of congested cases wait much longer.

This is one reason I later used both MAE and RMSE. MAE gives me the average error in minutes, while RMSE reacts more strongly to very large mistakes.

## Service-time profile

For actual service duration I found:

- mean: **16.00 minutes**
- median: **15.10 minutes**
- 95th percentile: **27.30 minutes**

This helped me confirm that service duration itself also has variation and should not be treated as a fixed constant.

## Queue-lane pattern

Average completed wait:

- General: **16.90 minutes**
- Priority: **9.66 minutes**

In my synthetic scenario, Priority customers wait less on average.

I do not treat this as proof of how a real organisation behaves. It is a property of the synthetic SmartQ scenario I generated.

## Appointment vs walk-in pattern

Average completed wait:

- Appointment: **16.97 minutes**
- Walk-in: **12.97 minutes**

Appointments have a higher raw mean wait in this generated dataset.

I do not interpret that as "appointments are worse." The groups can arrive under different queue conditions, so raw averages do not explain the full reason.

## Peak vs non-peak pattern

Average completed wait:

- Peak: **16.97 minutes**
- Non-peak: **14.47 minutes**

Peak periods are worse on average, but later significance testing showed that the standardised effect is small.

This taught me that a visible difference in averages does not automatically mean a variable is strongly useful once other queue variables are included.

## Branch pattern

In my generated dataset, Centurion has the highest observed average wait at about **26.99 minutes**, while Johannesburg Central has the lowest at about **8.66 minutes**.

I keep these branch results clearly labelled as synthetic. I do not present them as measurements of real service centres.

## Time pattern

Friday has the highest mean weekday wait in the generated data at about **21.40 minutes**.

The hourly analysis also shows congestion increasing during parts of the morning and afternoon, with the highest average around 15:00 at about **22.21 minutes**.

This told me that time features are worth keeping as possible predictors.

## Missing values

The main expected missing values among completed visits are:

- `appointment_at`: **21,864** rows, because walk-ins do not have appointment times;
- `recent_avg_service_minutes_10`: **2,775** rows, mainly early in the day before enough recent service history exists;
- `recent_avg_wait_minutes_10`: **313** rows, mainly when there is not enough recent waiting-time history yet.

I did not delete these rows automatically.

I treated the recent-history gaps as valid operational missingness and later handled them using training-set median imputation.

## Data-quality checks I ran

I checked for impossible or broken records.

I found **zero violations** for:

- negative actual waiting time;
- non-positive service duration;
- queue position not matching people ahead + 1;
- customer called before service eligibility;
- service starting before the call;
- service ending before it started;
- appointment becoming eligible before booked time;
- walk-in eligibility not matching check-in.

I ran these checks because a model can learn bad data just as easily as good data.

## Existing ETA benchmark

Before training the ML models, I also measured the existing deterministic SmartQ ETA.

It produced approximately:

- MAE: **4.72 minutes**
- RMSE: **6.56 minutes**

I kept this as an engineering benchmark instead of using it as an input feature.

I wanted the official ML models to learn from queue conditions themselves.

## My data-leakage rule

I excluded future/outcome fields from model inputs.

Examples:

- `call_time`
- `actual_wait_minutes`
- `actual_service_minutes`
- `service_started_at`
- `service_completed_at`

I did this because those values are not known when the customer checks in.

Using them would make the model look artificially strong.

## What I learned from this stage

My main lessons from EDA were:

1. The dataset is logically consistent enough to model.
2. Waiting time is strongly skewed by congestion.
3. Some raw group differences are visible.
4. Missing recent-history values are expected rather than corrupted.
5. Queue state and capacity variables are likely to matter.
6. I need to be careful about data leakage.
7. I should keep extreme but valid waits because they represent the difficult queue conditions I actually care about.
