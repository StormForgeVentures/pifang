"""Image pipe DSL parser and executor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pifang.core.result import OpResult
from pifang.errors import ValidationError


@dataclass
class PipeStage:
    name: str
    args: dict


def _reject_leftover(stage: str, tokens: list[str], consumed: set[int]) -> None:
    leftovers = [tokens[i] for i in range(len(tokens)) if i not in consumed]
    if leftovers:
        raise ValidationError(
            f"Unrecognized token(s) in pipe stage '{stage}': {' '.join(leftovers)}",
            "INVALID_PIPE_STAGE",
            {"hint": "Separate stages with | ; check pifang pipe image --help"},
        )


def parse_image_pipe(dsl: str) -> list[PipeStage]:
    if not dsl.strip():
        raise ValidationError("Pipe DSL is empty", "EMPTY_PIPE")
    stages: list[PipeStage] = []
    for raw in dsl.split("|"):
        part = raw.strip()
        if not part:
            continue
        tokens = part.split()
        name = tokens[0]
        args: dict = {}
        consumed: set[int] = {0}

        if name == "crop-square":
            i = 1
            while i < len(tokens):
                t = tokens[i]
                if t.startswith("--anchor="):
                    args["anchor"] = t.split("=", 1)[1]
                    consumed.add(i)
                    i += 1
                elif t == "--anchor":
                    if i + 1 >= len(tokens):
                        raise ValidationError("crop-square --anchor requires a value", "PIPE_SYNTAX")
                    args["anchor"] = tokens[i + 1]
                    consumed.update({i, i + 1})
                    i += 2
                elif not t.startswith("--") and "anchor" not in args:
                    args["anchor"] = t
                    consumed.add(i)
                    i += 1
                else:
                    i += 1
            _reject_leftover(name, tokens, consumed)

        elif name == "resize":
            if len(tokens) < 2:
                raise ValidationError("resize stage requires size", "PIPE_SYNTAX")
            spec = tokens[1]
            consumed.add(1)
            try:
                if "x" in spec.lower():
                    w, h = spec.lower().split("x", 1)
                    args["width"] = int(w)
                    args["height"] = int(h)
                else:
                    size = int(spec)
                    args["width"] = size
                    args["height"] = size
            except ValueError as exc:
                raise ValidationError(
                    f"Invalid resize size: {spec!r}",
                    "PIPE_SYNTAX",
                    {"hint": "Use N or WxH, e.g. resize 512 or resize 800x600"},
                ) from exc
            # optional fit=
            for i, t in enumerate(tokens[2:], 2):
                if t.startswith("fit="):
                    args["fit"] = t.split("=", 1)[1]
                    consumed.add(i)
            _reject_leftover(name, tokens, consumed)

        elif name.startswith("to-"):
            fmt = name.removeprefix("to-")
            args["format"] = fmt
            for i, t in enumerate(tokens[1:], 1):
                if t.startswith("q") and t[1:].isdigit():
                    args["quality"] = int(t[1:])
                    consumed.add(i)
            _reject_leftover(name, tokens, consumed)

        elif name == "compress":
            i = 1
            while i < len(tokens):
                t = tokens[i]
                if t.startswith("q") and len(t) > 1 and t[1:].isdigit():
                    args["quality"] = int(t[1:])
                    consumed.add(i)
                    i += 1
                elif t.startswith("max-kb="):
                    try:
                        args["max_kb"] = int(t.split("=", 1)[1])
                    except ValueError as exc:
                        raise ValidationError(f"Invalid max-kb value in compress stage: {t}", "PIPE_SYNTAX") from exc
                    consumed.add(i)
                    i += 1
                elif t == "max-kb":
                    if i + 1 >= len(tokens):
                        raise ValidationError("compress max-kb requires a value", "PIPE_SYNTAX")
                    try:
                        args["max_kb"] = int(tokens[i + 1])
                    except ValueError as exc:
                        raise ValidationError(
                            f"Invalid max-kb value: {tokens[i + 1]!r}",
                            "PIPE_SYNTAX",
                        ) from exc
                    consumed.update({i, i + 1})
                    i += 2
                else:
                    i += 1
            _reject_leftover(name, tokens, consumed)

        elif name == "strip-exif":
            _reject_leftover(name, tokens, consumed)
        else:
            raise ValidationError(f"Unknown pipe stage: {name}", "UNKNOWN_PIPE_STAGE")

        stages.append(PipeStage(name=name, args=args))
    return stages


def _stage_to_step(stage: PipeStage) -> dict:
    if stage.name == "crop-square":
        return {
            "crop-square": {
                "anchor": stage.args.get("anchor", "center"),
                **({} if "size" not in stage.args else {"size": stage.args["size"]}),
            }
        }
    if stage.name == "resize":
        return {
            "resize": {
                "width": stage.args.get("width"),
                "height": stage.args.get("height"),
                "fit": stage.args.get("fit", "contain"),
            }
        }
    if stage.name.startswith("to-"):
        return {
            "convert": {
                "format": stage.args.get("format", stage.name.removeprefix("to-")),
                "quality": stage.args.get("quality", 85),
            }
        }
    if stage.name == "compress":
        return {
            "compress": {
                "quality": stage.args.get("quality", 80),
                **({} if "max_kb" not in stage.args else {"max_kb": stage.args["max_kb"]}),
            }
        }
    if stage.name == "strip-exif":
        return {"strip-exif": {}}
    raise ValidationError(f"Unknown stage: {stage.name}")


def run_image_pipe(
    dsl: str,
    input_path: Path,
    output_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    from pifang.core.recipe import _run_step

    stages = parse_image_pipe(dsl)
    current_in = input_path
    temp_outputs: list[Path] = []
    result: OpResult | None = None

    try:
        for i, stage in enumerate(stages):
            is_last = i == len(stages) - 1
            step = _stage_to_step(stage)
            step_out = (
                output_path
                if is_last
                else output_path.parent / f".pifang-pipe-{input_path.stem}-{i}{output_path.suffix or '.webp'}"
            )
            if not is_last:
                temp_outputs.append(step_out)
            result = _run_step(step, current_in, step_out, force=True, dry_run=dry_run)
            if not result.ok:
                return result
            current_in = step_out

        if result is None:
            raise ValidationError("Pipe has no stages", "EMPTY_PIPE")

        result.command = "pipe.image"
        result.input_path = input_path
        return result
    finally:
        for tmp in temp_outputs:
            if tmp.exists() and not dry_run:
                tmp.unlink(missing_ok=True)
