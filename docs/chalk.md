# Chalk for Tell (blind leak)

Tell can read its coordinator-view feature matrix from Chalk instead of building it inline.
It is **off by default**: with `TELL_FEATURES` unset, Tell builds features locally exactly as before.

## Deploy

`chalk_project/` is the deploy unit: exactly 9 files (its own `chalk.yaml`, `chalk_requirements.txt`, and
copies of `engine/blind_leak/{__init__,contract,features}.py` and `tell_chalk/`). Deploy from that folder
only, so nothing else in the repository can be uploaded. There is deliberately no `chalk.yaml` or
`.chalkignore` at the repository root (a test enforces this): Chalk's `.chalkignore` did not honor a
deny-all allow-list the way gitignore does, and a root deploy uploaded extra files.

```bash
cp engine/blind_leak/{__init__,contract,features}.py chalk_project/engine/blind_leak/
cp tell_chalk/{__init__,features,vector}.py chalk_project/tell_chalk/
.venv/bin/python -m pytest tests/test_tell_chalk.py   # checks chalk_project/ is the 9 files and in sync
cd chalk_project && PATH="$PWD/../.venv/bin:$HOME/.chalk/bin:$PATH" chalk apply
```

`chalk_requirements.txt` pins `pandas==2.3.3` (Chalk's runtime requires pandas < 3) and `numpy==2.4.6`.

## Use

```bash
TELL_FEATURES=chalk .venv/bin/python ...   # run_blind now reads features from Chalk's offline query
```

The arm label is never a Chalk feature and is never sent; Tell joins it locally from ground truth.

## Numbers

On `tr_2026_B` coordinator, features from Chalk give accuracy 0.74875 / AUC 0.8529375, identical to Tell's
result measured on Linux (Daytona). On macOS the local path gives 0.75875 / 0.8494: 18 std/slope columns
differ in the last floating-point bits (about 1e-15) between Linux and macOS math libraries, which moves
a handful of borderline patients across LightGBM split thresholds. The control `tr_2026_B_off` is at
chance either way (0.511 Chalk, 0.501 local).
