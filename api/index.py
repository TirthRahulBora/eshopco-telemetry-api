import json
import os
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).resolve().parents[1] / "telemetry.json"


class MetricsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = 180


def percentile95(values):
    if not values:
        return None
    values = sorted(values)
    position = 0.95 * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (
        position - lower
    )


@app.post("/")
def calculate_metrics(request: MetricsRequest):
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            records = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=500,
            detail="Unable to load telemetry data"
        )

    result = {}

    for region in request.regions:
        rows = [
            r for r in records
            if r["region"].lower() == region.lower()
        ]

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for region {region}"
            )

        latencies = [float(r["latency_ms"]) for r in rows]
        uptimes = [float(r["uptime"]) for r in rows]

        result[region] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": percentile95(latencies),
            "avg_uptime": sum(uptimes) / len(uptimes),
            "breaches": sum(
                latency > request.threshold_ms
                for latency in latencies
            ),
        }

    return result
