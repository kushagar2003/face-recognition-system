# Face Recognition Attendance System

Local AI/ML pipeline and database layer, built with OpenCV (YuNet detection,
SFace recognition) and Neon PostgreSQL. For personal learning and portfolio use.

## Important notes

- **Consent and authorized images only.** Use images of people who have agreed.
- **Biometric data.** Face images and embeddings are sensitive. They stay out of
  Git (see `.gitignore`).
- **Model licenses.** Check the license file in each model folder on OpenCV Zoo.
- **Heuristic checks.** Quality checks are heuristics, not guarantees.

## Setup (once)

Run from the project root in PowerShell. Python 3.11 or 3.12, 64-bit.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Database settings

```powershell
python -m scripts.set_env
```

Paste the connection string from the Neon dashboard (Connect button). The input
is hidden, so it is not echoed and not stored in PowerShell history. The script
writes `.env`, then tests the connection.

### Model files

Download into `models\` (see `models\README.txt`):

```powershell
$base = "https://github.com/opencv/opencv_zoo/raw/main/models"
Invoke-WebRequest -Uri "$base/face_detection_yunet/face_detection_yunet_2023mar.onnx" -OutFile "models\face_detection_yunet_2023mar.onnx"
Invoke-WebRequest -Uri "$base/face_recognition_sface/face_recognition_sface_2021dec.onnx" -OutFile "models\face_recognition_sface_2021dec.onnx"
```

## Everyday commands

Activate the environment first; the prompt should start with `(.venv)`.

| Command | What it does |
|---|---|
| `.\.venv\Scripts\Activate.ps1` | Activate the environment |
| `python -m scripts.doctor` | Check the whole setup and report fixes |
| `python -m scripts.set_env` | Write or replace `.env` |
| `python -m scripts.check_image_loader` | Test image-loading error handling |
| `python -m scripts.check_image_loader data\sample_images\photo.jpg` | Load one image |
| `python -m database.check_connection` | Test the Neon connection |
| `python -m database.init_db` | Create the database tables (safe to repeat) |
| `python -m database.init_db --status` | Show which tables exist, change nothing |

## Status

**Step 1, AI/ML pipeline (partial)**

- [x] `ai_pipeline/config.py` — settings and thresholds
- [x] `ai_pipeline/image_loader.py` — load and validate an image
- [ ] `face_detector.py`, `quality_check.py`, `face_aligner.py`
- [ ] `embedding_generator.py`, `face_matcher.py`, `pipeline.py`
- [ ] Demos, unit tests, FAR/FRR evaluation script

**Step 2, database (partial)**

- [x] `database/config.py` — load and validate `DATABASE_URL`
- [x] `database/db.py` — connections with commit and rollback
- [x] `database/check_connection.py` — connection test
- [x] `database/schema.sql` — seven tables, constraints, indexes (tested on PostgreSQL 16)
- [x] `database/init_db.py` — safe, repeatable table creation
- [ ] `repository.py`, tests

**Step 3, FastAPI backend** — not started.
**Step 4, React frontend** — not started.

Thresholds in `ai_pipeline/config.py` are starting points, not validated values.
Tune them with the evaluation script on your own labelled test images.
