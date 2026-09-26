# My SmartQ EDA Visual Analysis

## Why I added more visuals

I did not want my EDA notebook to contain charts only for decoration.

I wanted each chart to answer a specific question about the data.

I therefore expanded the EDA so I could understand and explain the dataset visually before discussing model results.

## Visuals I included

I now use charts for:

- waiting-time distribution;
- average wait by branch;
- average wait by hour;
- average wait by weekday;
- queue pressure vs actual waiting time;
- General vs Priority waiting time;
- Appointment vs Walk-in waiting time;
- Peak vs Non-peak waiting time;
- waiting time by service type;
- missing values among completed visits;
- correlation between selected numeric queue-state variables.

## What I learned from General vs Priority

Average completed wait:

- General: **16.90 minutes**
- Priority: **9.66 minutes**

The visual makes the difference easy to see.

Later, I also tested the difference statistically. It is clearly detectable, but the effect size is not enormous.

This taught me not to stop at the chart itself.

## What I learned from Appointment vs Walk-in

Average completed wait:

- Appointment: **16.97 minutes**
- Walk-in: **12.97 minutes**

The visual shows that appointments have a higher raw average wait in my generated data.

I avoid saying that appointments "cause" longer waits because the groups can experience different queue conditions.

## What I learned from Peak vs Non-peak

Average completed wait:

- Peak: **16.97 minutes**
- Non-peak: **14.47 minutes**

The chart shows a difference, but later I found that the standardised effect size is small.

This was a good example of why visual difference, statistical significance and practical importance are three different questions.

## What I learned from service type

Average completed wait:

- Collections: **16.11 minutes**
- ID Applications: **16.05 minutes**
- Passport Applications: **15.90 minutes**

The chart shows that these raw averages are almost identical.

I confirmed that with a one-way ANOVA:

- p-value: **0.6503**
- eta-squared: about **0.000009**

That means I did not find a meaningful raw overall waiting-time difference between the three service types in this synthetic dataset.

## Why I visualised missing values

I wanted to distinguish expected missingness from bad data.

The main missing values among completed visits are:

- `appointment_at`: expected for walk-ins;
- `recent_avg_service_minutes_10`: expected early in the day;
- `recent_avg_wait_minutes_10`: expected when recent history is not yet available.

The chart helped me see that the missingness pattern is explainable.

## Why I added a correlation matrix

Correlation measures how strongly two numeric variables move together.

I added the matrix because I suspected that some engineered queue variables were carrying similar information.

The visual showed strong relationships among features such as:

- people ahead;
- workload ahead;
- queue pressure;
- general waiting;
- serving count;
- counter utilisation.

That observation later led me to the VIF and multicollinearity analysis.

## What I learned about charts

My biggest lesson here is that a useful EDA chart should answer a question.

I now use the EDA visuals to answer:

1. What does the target distribution look like?
2. Do branches and time periods behave differently?
3. Does congestion relate to waiting time?
4. Do important operational groups differ?
5. Where are values missing?
6. Which numeric features move together?
7. Are the differences statistically detectable?
8. Are the differences large enough to matter in practice?

That gives me a much stronger Data Understanding stage than simply producing graphs and moving on.
