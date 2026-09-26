from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "SmartQ_Synthetic_Operational_Dataset_100k.csv"

EXPECTED_ROWS = 100_000
EXPECTED_COLUMNS = 45

def fail(message):
    print(f"FAIL: {message}")
    sys.exit(1)

df = pd.read_csv(DATA)

if len(df) != EXPECTED_ROWS:
    fail(f"expected {EXPECTED_ROWS} rows, found {len(df)}")

if df.shape[1] != EXPECTED_COLUMNS:
    fail(f"expected {EXPECTED_COLUMNS} columns, found {df.shape[1]}")

if df["record_id"].duplicated().any():
    fail("duplicate record_id values found")

completed = df[df["status"] == "COMPLETED"].copy()

if (completed["actual_wait_minutes"] < 0).any():
    fail("negative completed waiting time found")

if (completed["actual_service_minutes"] <= 0).any():
    fail("non-positive completed service duration found")

if not (
    completed["queue_position"]
    == completed["people_ahead"] + 1
).all():
    fail("queue_position is inconsistent with people_ahead")

required_statuses = {"COMPLETED", "NO_SHOW", "CANCELLED"}
if set(df["status"].unique()) != required_statuses:
    fail(f"unexpected status values: {sorted(df['status'].unique())}")

print("SmartQ dataset validation passed.")
print(f"Rows: {len(df):,}")
print(f"Columns: {df.shape[1]}")
print(f"Completed: {len(completed):,}")
