# SmartQ Machine-Learning Integration Workspace

I created this folder so I can keep the main SmartQ application and the important machine-learning material in one place while I integrate the selected model.

## Why I copied the ML material here

I still keep `SmartQ-Machine-Learning` as my dedicated research and training repository.

I copied the important ML files into SmartQ because integration is easier when I can inspect the exact feature contract, training logic, diagnostics, notebooks and evaluation results beside the live Django queue code.

The files under `repository_snapshot/` are copied from the ML repository without changing their content.

## What I copied

I copied:

- my ML repository README;
- my first-person engineering worklog;
- my plain-English ML learning guide;
- EDA, evaluation, diagnostics and integration documentation;
- the four numbered ML notebooks;
- the prediction, training, diagnostics and validation source files;
- the key modelling and diagnostic result files;
- the ML requirements file.

## What I did not duplicate

I did not copy the 100,000-row training CSV into the main SmartQ repository because Django does not need the research dataset at runtime.

I also did not copy the large self-contained notebook that embeds the full dataset.

I have not yet copied the trained `.joblib` model artifact because I want to package and verify the exact integration artifact separately rather than accidentally treat a research file as a production dependency.

## How I will use this folder

I treat:

`machine_learning/repository_snapshot/`

as reference material.

I will build actual Django integration code in the main SmartQ application rather than editing the copied research files directly.

That gives me a clean separation:

```text
ML research/training evidence
        ↓
verified model artifact + feature contract
        ↓
SmartQ Django integration
        ↓
live prediction with deterministic ETA fallback
```

## Current integration state

The main SmartQ application currently has:

- deterministic live ETA logic;
- Day 59 forecasting observations;
- labelled wait/service outcomes;
- queue-state collection;
- ML still explicitly disabled in the forecasting summary.

My next step is to map live SmartQ state into the exact 22-feature ML input contract, package the selected XGBoost bundle, add safe fallback behaviour, expose the prediction through the existing queue API and measure inference latency.
