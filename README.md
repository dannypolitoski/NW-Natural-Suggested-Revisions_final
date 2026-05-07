# NW Natural Scenario Studio Workspace

This repository packages the current scenario-planning frontend with the GranularGas forecasting backend in one shareable workspace.

## What is included

- `frontend/`
  Standalone browser UI for creating scenarios, saving them with `name_date`, browsing saved runs, and comparing two scenarios.
- `backend/`
  The GranularGas Python model code, scenario API server, tests, and starter scenario template JSON files.
- `NW-Natural-Scenario-Studio.code-workspace`
  A simple multi-folder workspace file for opening the frontend and backend together.

## What is intentionally not included

- Proprietary NW Natural source data
- Large generated outputs
- Local Python environments and caches

The backend expects internal model data under:

```text
backend/Data/NWNatural Data/
```

At minimum, the current model code looks for files such as:

- `premise_data_blinded.csv`
- `equipment_data_blinded.csv`
- `equipment_codes.csv`
- `segment_data_blinded.csv`
- `billing_data_blinded.csv`

## Local startup

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python dashboard_api_server.py
```

The API serves on `http://127.0.0.1:8000`.

### 2. Frontend

Open `frontend/index.html` in a browser after the backend is running.

The frontend will:

- require a scenario name and date
- save new runs as `name_date`
- list saved scenario result folders from `backend/scenarios`
- load saved charts and summaries
- compare two saved scenarios side by side

## Notes

- This workspace is set up for collaboration and code review first; a full model run still requires the internal NW Natural input data.
- Saved scenario result folders generated locally should remain uncommitted unless you intentionally want to share derived outputs.
