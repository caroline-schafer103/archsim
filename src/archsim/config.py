"""Loading architecture files and generating variations of them."""

from pathlib import Path

import yaml

from archsim.models import SimConfig, Stage, Workload


def load_config(path: Path) -> SimConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping with 'workload' and 'stages'")
    data.setdefault("name", path.stem)
    return SimConfig.model_validate(data)


VARIABLE_STAGE_FIELDS = {"workers", "service_time", "service"}
VARIABLE_WORKLOAD_FIELDS = {"rate", "duration", "arrivals"}


def parse_vary(text: str) -> tuple[str, str, list[str]]:
    """Parse 'TARGET.FIELD=V1,V2,...', e.g. 'transcode.workers=150,200,250'."""
    try:
        path, values = text.split("=", 1)
        target, field = path.split(".", 1)
    except ValueError:
        raise ValueError(f"invalid --vary '{text}': expected STAGE.FIELD=V1,V2,... e.g. transcode.workers=150,200")
    allowed = VARIABLE_WORKLOAD_FIELDS if target == "workload" else VARIABLE_STAGE_FIELDS
    if field not in allowed:
        raise ValueError(f"cannot vary '{field}' on {target}; choose from: {', '.join(sorted(allowed))}")
    return target, field, [v.strip() for v in values.split(",") if v.strip()]


def apply_vary(config: SimConfig, target: str, field: str, value: str) -> SimConfig:
    """A copy of `config` with one field changed (validated like the file)."""
    data = config.model_dump()
    if target == "workload":
        data["workload"][field] = value
    else:
        config.stage(target)  # raises a helpful KeyError if the stage doesn't exist
        stage = next(s for s in data["stages"] if s["name"] == target)
        stage[field] = value
    data["name"] = _variation_name(target, field, value)
    return SimConfig.model_validate(data)


def _variation_name(target: str, field: str, value: str) -> str:
    """A label that says which stage changed, e.g. '200 transcode workers'."""
    if target == "workload":
        return f"{field}={value}"
    if field == "workers":
        return f"{value} {target} workers"
    return f"{target} {field}={value}"


def variations(config: SimConfig, vary: str | None) -> list[SimConfig]:
    if not vary:
        return [config]
    target, field, values = parse_vary(vary)
    return [apply_vary(config, target, field, v) for v in values]


__all__ = ["load_config", "parse_vary", "apply_vary", "variations", "SimConfig", "Stage", "Workload"]
