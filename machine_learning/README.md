# SmartQ Machine-Learning Submission Snapshot

I keep the dedicated `SmartQ-Machine-Learning` repository for ML research history, but I also copy its complete tracked contents into the main SmartQ repository for submission and integration.

## Complete snapshot

The full copy is here:

`machine_learning/repository_snapshot/`

I verified it file-for-file against the ML repository:

- source tracked files: **49**
- copied tracked files: **49**
- missing files: **0**
- extra files: **0**

The snapshot includes the full 100,000-row CSV dataset, all ML notebooks, the embedded-dataset notebook, dataset DOCX documentation, project notes, EDA/model/diagnostic results, Python source code, requirements, README files and ML workflow files.

## Dataset

`machine_learning/repository_snapshot/data/SmartQ_Synthetic_Operational_Dataset_100k.csv`

- rows: **100,000**
- size: **35,059,222 bytes**

## Traceability

`machine_learning/SNAPSHOT_SOURCE.md`

records the source ML repository commit used for the copy.

I exclude only the source repository's internal `.git/` metadata because that is Git internals rather than project content.

The trained `.joblib` model is a generated runtime artifact rather than a tracked file in the ML source repository. I will package that separately during Django integration.
