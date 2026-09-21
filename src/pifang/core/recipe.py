"""Recipe loading and execution."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pifang.core.result import OpResult
from pifang.domains.image import ops
from pifang.domains.video import ops as video_ops
from pifang.errors import ValidationError


@dataclass
class Recipe:
    name: str
    domain: str
    description: str = ""
    source: str = "builtin"
    params: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RecipeLoadResult:
    recipes: list[Recipe]
    warnings: list[str]
    # name/stem of custom files that failed to parse → path + error message
    broken: dict[str, tuple[Path, str]] = field(default_factory=dict)


def _recipe_dirs() -> list[Path]:
    dirs: list[Path] = []
    local = Path.cwd() / ".pifang" / "recipes"
    if local.is_dir():
        dirs.append(local)
    user = Path.home() / ".config" / "pifang" / "recipes"
    if user.is_dir():
        dirs.append(user)
    return dirs


def _load_yaml_file(path: Path, source: str) -> Recipe | None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "name" not in data:
        return None
    return Recipe(
        name=str(data["name"]),
        domain=str(data.get("domain", "image")),
        description=str(data.get("description", "")),
        source=source,
        params=data.get("params") or {},
        steps=list(data.get("steps") or []),
    )


def _load_builtin() -> list[Recipe]:
    recipes: list[Recipe] = []
    root = Path(__file__).resolve().parent.parent / "recipes" / "builtin"
    if root.is_dir():
        for path in sorted(root.glob("*.yaml")):
            loaded = _load_yaml_file(path, "builtin")
            if loaded:
                recipes.append(loaded)
    return recipes


def load_recipes_detailed() -> RecipeLoadResult:
    """Load recipes; skip malformed custom files with warnings (builtins must load cleanly)."""
    by_name: dict[str, Recipe] = {}
    warnings: list[str] = []
    broken: dict[str, tuple[Path, str]] = {}

    for r in _load_builtin():
        by_name[r.name] = r

    for directory in _recipe_dirs():
        for path in sorted(directory.glob("*.yaml")):
            try:
                loaded = _load_yaml_file(path, "custom")
            except Exception as exc:  # noqa: BLE001 — isolate bad custom recipes
                msg = f"Skipped malformed recipe file {path}: {exc}"
                warnings.append(msg)
                broken[path.stem] = (path, str(exc))
                sys.stderr.write(f"pifang: warning: {msg}\n")
                continue
            if loaded is None:
                msg = f"Skipped invalid recipe file {path}: missing name or not a mapping"
                warnings.append(msg)
                broken[path.stem] = (path, "missing name or not a mapping")
                sys.stderr.write(f"pifang: warning: {msg}\n")
                continue
            by_name[loaded.name] = loaded
            # Also index by stem so direct-run of broken names can be diagnosed
            if loaded.name != path.stem:
                pass

    return RecipeLoadResult(recipes=list(by_name.values()), warnings=warnings, broken=broken)


def load_recipes() -> list[Recipe]:
    return load_recipes_detailed().recipes


def get_recipe(name: str) -> Recipe:
    detailed = load_recipes_detailed()
    for recipe in detailed.recipes:
        if recipe.name == name:
            return recipe
    if name in detailed.broken:
        path, err = detailed.broken[name]
        raise ValidationError(
            f"Recipe file is malformed: {path} ({err})",
            "INVALID_RECIPE",
            {"hint": f"Fix YAML syntax in {path}"},
        )
    # Also match broken files whose YAML name couldn't be read (stem only)
    for stem, (path, err) in detailed.broken.items():
        if stem == name:
            raise ValidationError(
                f"Recipe file is malformed: {path} ({err})",
                "INVALID_RECIPE",
                {"hint": f"Fix YAML syntax in {path}"},
            )
    raise ValidationError(f"Recipe not found: {name}", "RECIPE_NOT_FOUND", {"hint": "pifang recipe list"})


def _render(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            default = match.group(2)
            if key in params:
                return str(params[key])
            if default is not None:
                return default.strip()
            return match.group(0)

        return re.sub(r"\{\{\s*(\w+)(?:\|\s*default\(([^)]+)\))?\s*\}\}", repl, value)
    if isinstance(value, dict):
        return {k: _render(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, params) for v in value]
    return value


def _run_step(step: dict[str, Any], input_path: Path, output_path: Path, *, force: bool, dry_run: bool) -> OpResult:
    if len(step) != 1:
        raise ValidationError("Each recipe step must have exactly one operation key")
    op, cfg = next(iter(step.items()))
    cfg = cfg or {}
    if op == "crop-square":
        return ops.crop_square(
            input_path,
            output_path,
            anchor=cfg.get("anchor", "center"),
            size=int(cfg["size"]) if cfg.get("size") else None,
            force=force,
            dry_run=dry_run,
        )
    if op == "resize":
        return ops.resize(
            input_path,
            output_path,
            width=int(cfg["width"]) if cfg.get("width") else None,
            height=int(cfg["height"]) if cfg.get("height") else None,
            fit=cfg.get("fit", "contain"),
            force=True,
            dry_run=dry_run,
        )
    if op == "convert":
        return ops.convert(
            input_path,
            output_path,
            format=cfg.get("format", "webp"),
            quality=int(cfg.get("quality", 85)),
            force=True,
            dry_run=dry_run,
        )
    if op == "compress":
        return ops.compress(
            input_path,
            output_path,
            quality=int(cfg.get("quality", 80)),
            max_kb=int(cfg["max_kb"]) if cfg.get("max_kb") else None,
            force=True,
            dry_run=dry_run,
        )
    if op == "strip-exif":
        return ops.strip_exif(input_path, output_path, force=True, dry_run=dry_run)
    raise ValidationError(f"Unknown recipe step: {op}", "UNKNOWN_STEP")


def _run_video_step(step: dict[str, Any], input_path: Path, output_path: Path, *, force: bool, dry_run: bool) -> OpResult:
    if len(step) != 1:
        raise ValidationError("Each recipe step must have exactly one operation key")
    op, cfg = next(iter(step.items()))
    cfg = cfg or {}
    if op == "trim":
        dur = cfg.get("duration")
        return video_ops.trim(
            input_path,
            output_path,
            start=cfg.get("start", 0),
            end=cfg.get("end"),
            duration=dur if dur else None,
            force=force,
            dry_run=dry_run,
        )
    if op == "resize":
        return video_ops.resize(
            input_path,
            output_path,
            width=int(cfg["width"]),
            height=int(cfg["height"]),
            fit=cfg.get("fit", "cover"),
            force=force,
            dry_run=dry_run,
        )
    if op == "transcode":
        fmt = cfg.get("format", "mp4")
        out = output_path if output_path.suffix else output_path.with_suffix(f".{fmt}")
        return video_ops.transcode(
            input_path,
            out,
            codec=cfg.get("codec", "libx264"),
            audio_codec=cfg.get("audio_codec", "aac"),
            crf=int(cfg.get("crf", 23)),
            format=fmt,
            force=force,
            dry_run=dry_run,
        )
    if op == "extract-audio":
        fmt = cfg.get("format", "mp3")
        out = output_path if output_path.suffix else output_path.with_suffix(f".{fmt}")
        return video_ops.extract_audio(input_path, out, format=fmt, force=force, dry_run=dry_run)
    if op == "normalize-audio":
        return video_ops.normalize_audio(
            input_path,
            output_path,
            target_lufs=float(cfg.get("target_lufs", -16)),
            force=force,
            dry_run=dry_run,
        )
    raise ValidationError(f"Unknown video recipe step: {op}", "UNKNOWN_STEP")


def run_recipe(
    name: str,
    input_path: Path,
    output_path: Path,
    params: dict[str, Any] | None = None,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    recipe = get_recipe(name)
    if recipe.domain not in ("image", "video"):
        raise ValidationError(f"Recipe domain not supported: {recipe.domain}")

    merged = {k: (v.get("default") if isinstance(v, dict) else v) for k, v in recipe.params.items()}
    merged.update(params or {})
    rendered_steps = [_render(step, merged) for step in recipe.steps]

    current_in = input_path
    temp_outputs: list[Path] = []
    result: OpResult | None = None
    run_step = _run_video_step if recipe.domain == "video" else _run_step

    try:
        for i, step in enumerate(rendered_steps):
            is_last = i == len(rendered_steps) - 1
            suffix = output_path.suffix or (
                ".mp3" if recipe.domain == "video" and name == "podcast-audio" else ".mp4"
            )
            step_out = (
                output_path if is_last else output_path.parent / f".pifang-tmp-{input_path.stem}-{i}{suffix}"
            )
            if not is_last:
                temp_outputs.append(step_out)
            result = run_step(step, current_in, step_out, force=force or not is_last, dry_run=dry_run)
            if not result.ok:
                return result
            current_in = result.output_path or step_out

        if result is None:
            raise ValidationError("Recipe has no steps", "EMPTY_RECIPE")

        result.command = f"{recipe.domain}.{name}"
        result.input_path = input_path
        return result
    finally:
        for tmp in temp_outputs:
            if tmp.exists() and not dry_run:
                tmp.unlink(missing_ok=True)
