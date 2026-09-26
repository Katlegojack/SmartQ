from pathlib import Path
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "models" / "smartq_wait_time_model.joblib"

REQUIRED_INPUTS = [
    "arrival_offset_minutes",
    "people_ahead",
    "general_waiting",
    "priority_waiting",
    "serving_count",
    "open_general_counters",
    "open_priority_counters",
    "effective_open_counters",
    "counter_utilisation",
    "queue_pressure_index",
    "workload_minutes_ahead",
    "recent_avg_service_minutes_10",
    "recent_avg_wait_minutes_10",
    "recent_throughput_60m",
    "service_target_minutes",
    "hour_of_day",
    "branch_code",
    "service_code",
    "booking_source",
    "queue_type",
    "day_of_week",
    "is_peak_period",
]

def load_bundle(model_path=DEFAULT_MODEL_PATH):
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model bundle not found at {model_path}. "
            "Run 'python src/train_models.py' first."
        )
    return joblib.load(model_path)

def validate_input(observation):
    missing = [field for field in REQUIRED_INPUTS if field not in observation]
    if missing:
        raise ValueError(f"Missing required SmartQ prediction fields: {missing}")

def predict_wait_minutes(observation, bundle=None, model_path=DEFAULT_MODEL_PATH):
    validate_input(observation)
    if bundle is None:
        bundle = load_bundle(model_path)

    frame = pd.DataFrame([observation], columns=bundle["features"])
    prepared = bundle["preprocessor"].transform(frame)
    prediction = float(bundle["model"].predict(prepared)[0])

    # Waiting time shown to a customer must never be negative.
    return max(0.0, prediction)

if __name__ == "__main__":
    example = {
        "arrival_offset_minutes": 0,
        "people_ahead": 4,
        "general_waiting": 5,
        "priority_waiting": 1,
        "serving_count": 4,
        "open_general_counters": 4,
        "open_priority_counters": 1,
        "effective_open_counters": 4,
        "counter_utilisation": 0.8,
        "queue_pressure_index": 2.0,
        "workload_minutes_ahead": 55.0,
        "recent_avg_service_minutes_10": 15.5,
        "recent_avg_wait_minutes_10": 14.2,
        "recent_throughput_60m": 13,
        "service_target_minutes": 15,
        "hour_of_day": 10,
        "branch_code": "PTC1",
        "service_code": "IDAPP",
        "booking_source": "APPOINTMENT",
        "queue_type": "GENERAL",
        "day_of_week": "Monday",
        "is_peak_period": True,
    }
    print(f"Predicted wait: {predict_wait_minutes(example):.2f} minutes")
