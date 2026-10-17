
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "true", "1", "yes", "on"
    }


def coerce(key, value):
    try:
        if key in ("port", "workers"):
            return int(value)
        if key == "debug":
            return to_bool(value)
        return str(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value for {key}"
        )


@app.get("/effective-config")
def effective_config(
    set_values: list[str] | None = Query(
        default=None, alias="set"
    )
):
    config = DEFAULTS.copy()

    # Layer 2: YAML
    yaml_path = BASE_DIR / "config.development.yaml"
    try:
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not read YAML configuration"
        ) from exc

    if not isinstance(yaml_config, dict):
        raise HTTPException(
            status_code=500,
            detail="YAML must contain a mapping"
        )

    config.update(yaml_config)

    # Layer 3: .env
    file_env = dotenv_values(BASE_DIR / ".env")

    for name, value in file_env.items():
        if value is None:
            continue

        if name == "NUM_WORKERS":
            key = "workers"
        elif name.startswith("APP_"):
            key = name[4:].lower()
        else:
            continue

        config[key] = value

    # Layer 4: OS environment variables
    for name, value in os.environ.items():
        if name.startswith("APP_"):
            config[name[4:].lower()] = value

    # Layer 5: URL overrides
    if set_values:
        for item in set_values:
            if "=" not in item:
                raise HTTPException(
                    status_code=400,
                    detail="Use set=key=value"
                )

            key, value = item.split("=", 1)
            key = key.strip().lower()

            if not key:
                raise HTTPException(
                    status_code=400,
                    detail="Configuration key cannot be empty"
                )

            config[key] = value

    result = {
        key: coerce(key, value)
        for key, value in config.items()
    }

    result["api_key"] = "****"

    return result
