#!/usr/bin/env python3
"""Validate a narrative scrollytelling map without third-party packages."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DRIVERS = {"discrete-intersection", "view-progress", "scroll-progress"}


def validate(data):
    errors = []
    if data.get("version") != 1:
        errors.append("version must be 1")
    if data.get("driver") not in DRIVERS:
        errors.append(f"driver must be one of {sorted(DRIVERS)}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        return errors + ["steps must be a non-empty array"]
    ids = []
    for index, step in enumerate(steps):
        at = f"steps[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{at} must be an object")
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            errors.append(f"{at}.id must be a non-empty string")
        else:
            ids.append(step_id)
        content = step.get("content")
        if not isinstance(content, dict) or not any(content.get(key) for key in ("heading", "body", "contentRef")):
            errors.append(f"{at} needs static semantic content or contentRef")
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        errors.append(f"step ids must be unique: {', '.join(duplicates)}")
    known = set(ids)
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        for key in ("next", "previous"):
            target = step.get(key)
            if target and target not in known:
                errors.append(f"steps[{index}].{key} targets unknown step {target!r}")
        transition = step.get("transition") or {}
        target = transition.get("to")
        if target and target not in known:
            errors.append(f"steps[{index}].transition.to targets unknown step {target!r}")
    fallback = data.get("fallback") or {}
    for key in ("noJs", "reducedMotion", "noMotion"):
        if not fallback.get(key):
            errors.append(f"fallback.{key} is required")
    if data.get("driver") in {"view-progress", "scroll-progress"} and not fallback.get("unsupportedDriver"):
        errors.append("progress drivers require fallback.unsupportedDriver")
    scroll = data.get("scroll") or {}
    if scroll.get("mode") != "native":
        errors.append("scroll.mode must be native")
    if scroll.get("programmaticFocus") is not False:
        errors.append("scroll.programmaticFocus must be false")
    snap = scroll.get("snap", "none")
    if snap not in {"none", "proximity", "mandatory"}:
        errors.append("scroll.snap must be none, proximity, or mandatory")
    if snap == "mandatory" and not scroll.get("auditedOverride"):
        errors.append("mandatory snap needs an auditedOverride")
    if any(key in data for key in ("soundEvent", "audio", "autoplay")):
        errors.append("passive story maps do not own sound; use an explicit micro-interaction")
    return errors


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        print("usage: validate_map.py MAP.json", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"{path}: {error}", file=sys.stderr)
        return 2
    errors = validate(data)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
