from __future__ import annotations

import csv
import json
import mimetypes
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


ROOT_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = ROOT_DIR / "scenarios"
HOST = "127.0.0.1"
PORT = int(os.environ.get("GRANULAR_GAS_API_PORT", "8000"))

CHART_FILES = [
    ("model_vs_irp", "Model vs IRP", "chart_model_vs_irp.png"),
    ("total_demand", "Total Demand", "chart_total_demand.png"),
    ("segment_demand", "Demand by Segment", "chart_segment_demand.png"),
    ("estimated_total_upc", "Estimated Total UPC", "chart_estimated_total_upc.png"),
    ("enduse_breakdown", "End-Use Breakdown", "chart_enduse_breakdown.png"),
]


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return text.strip("_") or "scenario"


def normalize_date(value: str) -> str:
    return datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    payload = handler.rfile.read(length) if length else b"{}"
    return json.loads(payload.decode("utf-8"))


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def maybe_number(value: str):
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return ""
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in text or "e" in lowered:
            return float(text)
        return int(text)
    except ValueError:
        return text


def load_csv_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {key: maybe_number(value) for key, value in row.items()}
            for row in reader
        ]


def parse_display_name(scenario_id: str) -> str:
    match = re.match(r"^(.*)_(\d{4}-\d{2}-\d{2})$", scenario_id)
    base = match.group(1) if match else scenario_id
    return base.replace("_", " ").strip().title()


def parse_scenario_date(scenario_id: str) -> str | None:
    match = re.match(r"^.*_(\d{4}-\d{2}-\d{2})$", scenario_id)
    return match.group(1) if match else None


def ensure_scenario_dir(scenario_id: str) -> Path:
    scenario_dir = (SCENARIOS_DIR / scenario_id).resolve()
    if SCENARIOS_DIR.resolve() not in scenario_dir.parents:
        raise ValueError("Scenario path escapes the scenarios directory.")
    return scenario_dir


def locate_config_copy(scenario_id: str, scenario_dir: Path) -> Path | None:
    exact = scenario_dir / f"{scenario_id}.json"
    if exact.exists():
        return exact

    root_copy = SCENARIOS_DIR / f"{scenario_id}.json"
    if root_copy.exists():
        return root_copy

    candidates = sorted(
        path for path in scenario_dir.glob("*.json")
        if path.name not in {
            "results.json",
            "metadata.json",
            "irp_comparison.json",
            "estimated_total_upc.json",
            "segment_demand.json",
            "equipment_stats.json",
            "premise_distribution.json",
            "recs_enduse_trend.json",
            "recs_non_heating_ratios.json",
            "sample_rates.json",
            "vintage_demand.json",
            "monthly_summary.json",
            "census_heating_fuel_trend.json",
            "census_segment_distribution.json",
            "census_vintage_distribution.json",
            "census_vs_model_housing.json",
            "census_b25024_segment_trend.json",
        }
    )
    return candidates[0] if candidates else None


def build_chart_manifest(scenario_id: str, scenario_dir: Path) -> list[dict]:
    charts = []
    for key, label, filename in CHART_FILES:
        chart_path = scenario_dir / filename
        if chart_path.exists():
            charts.append(
                {
                    "key": key,
                    "label": label,
                    "filename": filename,
                    "url": f"/api/results/{quote(scenario_id)}/assets/{quote(filename)}",
                }
            )
    return charts


def build_summary_metadata(
    scenario_id: str,
    config: dict,
    metadata: dict,
    yearly_summary: list[dict],
    irp_comparison: list[dict],
    estimated_total_upc: list[dict],
    charts: list[dict],
) -> dict:
    latest_year = yearly_summary[-1] if yearly_summary else {}
    latest_irp = irp_comparison[-1] if irp_comparison else {}
    latest_estimated = estimated_total_upc[-1] if estimated_total_upc else {}

    display_name = (
        config.get("display_name")
        or config.get("scenario_display_name")
        or metadata.get("display_name")
        or parse_display_name(scenario_id)
    )
    scenario_date = (
        config.get("scenario_date")
        or metadata.get("scenario_date")
        or parse_scenario_date(scenario_id)
    )

    return {
        "id": scenario_id,
        "display_name": display_name,
        "scenario_date": scenario_date,
        "saved_name": config.get("name", scenario_id),
        "description": config.get("description") or metadata.get("description") or "",
        "base_year": metadata.get("base_year") or config.get("base_year"),
        "forecast_horizon": metadata.get("forecast_horizon") or config.get("forecast_horizon"),
        "weather_assumption": metadata.get("weather_assumption") or config.get("weather_assumption"),
        "latest_year": latest_year.get("year"),
        "final_total_therms": latest_year.get("total_therms"),
        "final_upc": latest_year.get("use_per_customer"),
        "final_irp_upc": latest_irp.get("irp_upc"),
        "final_estimated_total_upc": latest_estimated.get("estimated_total_upc"),
        "final_diff_pct": latest_irp.get("diff_pct"),
        "chart_count": len(charts),
    }


def load_scenario_bundle(scenario_id: str) -> dict:
    scenario_dir = ensure_scenario_dir(scenario_id)
    if not scenario_dir.exists() or not scenario_dir.is_dir():
        raise FileNotFoundError(f"Scenario results not found: {scenario_id}")

    config_path = locate_config_copy(scenario_id, scenario_dir)
    config = load_json(config_path, default={}) if config_path else {}
    metadata = load_json(scenario_dir / "metadata.json", default={})
    yearly_summary = load_csv_records(scenario_dir / "yearly_summary.csv")
    monthly_summary = load_json(scenario_dir / "monthly_summary.json", default=None)
    if monthly_summary is None:
        monthly_summary = load_csv_records(scenario_dir / "monthly_summary.csv")
    irp_comparison = load_json(scenario_dir / "irp_comparison.json", default=None)
    if irp_comparison is None:
        irp_comparison = load_csv_records(scenario_dir / "irp_comparison.csv")
    estimated_total_upc = load_json(scenario_dir / "estimated_total_upc.json", default=None)
    if estimated_total_upc is None:
        estimated_total_upc = load_csv_records(scenario_dir / "estimated_total_upc.csv")
    segment_demand = load_json(scenario_dir / "segment_demand.json", default=None)
    if segment_demand is None:
        segment_demand = load_csv_records(scenario_dir / "segment_demand.csv")
    results = load_json(scenario_dir / "results.json", default=None)
    if results is None:
        results = load_csv_records(scenario_dir / "results.csv")
    recs_enduse_trend = load_json(scenario_dir / "recs_enduse_trend.json", default=None)
    if recs_enduse_trend is None:
        recs_enduse_trend = load_csv_records(scenario_dir / "recs_enduse_trend.csv")
    charts = build_chart_manifest(scenario_id, scenario_dir)

    scenario = build_summary_metadata(
        scenario_id,
        config,
        metadata,
        yearly_summary,
        irp_comparison,
        estimated_total_upc,
        charts,
    )

    return {
        "scenario": scenario,
        "config": config,
        "metadata": metadata,
        "results": results,
        "yearly_summary": yearly_summary,
        "monthly_summary": monthly_summary,
        "irp_comparison": irp_comparison,
        "estimated_total_upc": estimated_total_upc,
        "segment_demand": segment_demand,
        "recs_enduse_trend": recs_enduse_trend,
        "charts": charts,
    }


def list_saved_scenarios() -> list[dict]:
    scenarios = []
    for path in sorted(SCENARIOS_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        if not (path / "metadata.json").exists():
            continue
        try:
            bundle = load_scenario_bundle(path.name)
            scenarios.append(bundle["scenario"])
        except Exception:
            continue
    return scenarios


def derive_model_config(payload: dict) -> dict:
    template_name = str(payload.get("template_name") or "baseline").strip()
    template_path = SCENARIOS_DIR / f"{template_name}.json"
    template_config = load_json(template_path, default={})
    config = {**template_config, **payload}

    display_name = str(
        config.get("display_name")
        or config.get("scenario_display_name")
        or config.get("name")
        or ""
    ).strip()
    if not display_name:
        raise ValueError("Scenario name is required.")

    raw_date = config.get("scenario_date")
    if not raw_date:
        raise ValueError("Scenario date is required.")
    scenario_date = normalize_date(raw_date)

    scenario_id = f"{slugify(display_name)}_{scenario_date}"
    config["display_name"] = display_name
    config["scenario_date"] = scenario_date
    config["name"] = scenario_id
    config["template_name"] = template_name

    # ScenarioConfig does not retain template_name, so mark baseline-template
    # API runs for IRP alignment before handing the config to the model.
    if "baseline_irp_alignment" not in config and slugify(template_name) == "baseline":
        config["baseline_irp_alignment"] = True

    forecast_horizon = int(config.get("forecast_horizon", 10) or 10)
    forecast_horizon = max(forecast_horizon, 1)

    ui_targets = dict(config.get("ui_targets") or {})
    elec = config.get("electrification_rate")
    if isinstance(elec, dict):
        ui_targets["electrification_rate"] = elec
        all_electric_target = float(elec.get("space_heating", 0) or 0)
        hybrid_target = float(elec.get("hybrid_space_heating", 0) or 0)
        config["electrification_rate"] = round(all_electric_target / forecast_horizon, 4)
        config["hybrid_adoption_rate"] = round(hybrid_target / forecast_horizon, 4)

    efficiency = config.get("efficiency_improvement")
    if isinstance(efficiency, dict):
        ui_targets["efficiency_improvement"] = efficiency
        config["efficiency_improvement"] = float(efficiency.get("space_heating", 0) or 0)

    if ui_targets:
        config["ui_targets"] = ui_targets

    return config


def run_model_scenario(config: dict) -> dict:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    scenario_id = config["name"]
    config_path = SCENARIOS_DIR / f"{scenario_id}.json"
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)

    venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    python_executable = str(venv_python if venv_python.exists() else Path(sys.executable))

    command = [python_executable, "-m", "src.main", str(config_path), "--verbose"]
    completed = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            json.dumps(
                {
                    "message": "Model run failed.",
                    "stdout": completed.stdout[-8000:],
                    "stderr": completed.stderr[-8000:],
                }
            )
        )

    bundle = load_scenario_bundle(scenario_id)
    bundle["run_log"] = {
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }
    return bundle


class ScenarioApiHandler(BaseHTTPRequestHandler):
    server_version = "GranularGasScenarioAPI/0.1"

    def log_message(self, format, *args):  # noqa: A002
        # Print every request to stdout so the terminal shows live traffic.
        print(f"  {self.address_string()}  {format % args}", flush=True)

    def _log_error(self, context: str, exc: BaseException) -> None:
        """Print a full traceback to the server console for any 500-class error."""
        sep = "─" * 72
        print(f"\n{sep}", flush=True)
        print(f"  ERROR in {context}", flush=True)
        print(f"  {type(exc).__name__}: {exc}", flush=True)
        print(sep, flush=True)
        traceback.print_exc()
        print(sep, flush=True)

    def _send_json(self, payload: dict | list, status: int = HTTPStatus.OK):
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        content = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(content)

    def _send_error(self, message: str, status: int = HTTPStatus.BAD_REQUEST, details=None):
        payload = {"error": message}
        if details is not None:
            payload["details"] = details
        self._send_json(payload, status=status)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/health":
                self._send_json({"status": "ok", "root": str(ROOT_DIR), "scenarios_dir": str(SCENARIOS_DIR)})
                return

            if path == "/api/scenarios":
                self._send_json(list_saved_scenarios())
                return

            if path.startswith("/api/results/"):
                suffix = path[len("/api/results/"):]
                parts = [unquote(part) for part in suffix.split("/") if part]
                if len(parts) == 1:
                    self._send_json(load_scenario_bundle(parts[0]))
                    return

                if len(parts) >= 3 and parts[1] == "assets":
                    scenario_id = parts[0]
                    filename = parts[2]
                    scenario_dir = ensure_scenario_dir(scenario_id)
                    asset_path = (scenario_dir / filename).resolve()
                    if scenario_dir.resolve() not in asset_path.parents:
                        raise ValueError("Asset path escapes the scenario directory.")
                    if not asset_path.exists():
                        raise FileNotFoundError(f"Asset not found: {filename}")
                    self._send_file(asset_path)
                    return

                if len(parts) >= 3 and parts[1] == "export":
                    scenario_id = parts[0]
                    format_name = parts[2]
                    scenario_dir = ensure_scenario_dir(scenario_id)
                    filename = "results.csv" if format_name == "csv" else "results.json"
                    export_path = scenario_dir / filename
                    if not export_path.exists():
                        raise FileNotFoundError(f"Export not found: {filename}")
                    self._send_file(export_path)
                    return

            self._send_error("Route not found.", status=HTTPStatus.NOT_FOUND)
        except FileNotFoundError as exc:
            self._send_error(str(exc), status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_error(str(exc), status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._log_error(f"GET {path}", exc)
            self._send_error(
                "Unexpected server error.",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                details={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
            )

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/forecast":
                payload = parse_json_body(self)
                config = derive_model_config(payload)
                bundle = run_model_scenario(config)
                self._send_json(bundle, status=HTTPStatus.CREATED)
                return

            self._send_error("Route not found.", status=HTTPStatus.NOT_FOUND)
        except json.JSONDecodeError:
            self._send_error("Request body must be valid JSON.", status=HTTPStatus.BAD_REQUEST)
        except ValueError as exc:
            self._send_error(str(exc), status=HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            # RuntimeError from run_model_scenario carries a JSON-encoded dict
            # with stdout/stderr from the subprocess.
            self._log_error(f"POST {parsed.path} — model subprocess", exc)
            details = str(exc)
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                pass
            self._send_error("Model run failed.", status=HTTPStatus.INTERNAL_SERVER_ERROR, details=details)
        except Exception as exc:
            self._log_error(f"POST {parsed.path}", exc)
            self._send_error(
                "Unexpected server error.",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                details={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
            )


def main():
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), ScenarioApiHandler)
    print("─" * 72, flush=True)
    print(f"  GranularGas scenario API  →  http://{HOST}:{PORT}", flush=True)
    print(f"  Scenarios dir             →  {SCENARIOS_DIR}", flush=True)
    print(f"  Python                    →  {sys.executable}", flush=True)
    print("─" * 72, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
