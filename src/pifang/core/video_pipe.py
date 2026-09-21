"""Video pipe DSL parser and executor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pifang.core.result import OpResult
from pifang.domains.video import ops
from pifang.errors import ValidationError


@dataclass
class PipeStage:
    name: str
    args: dict


def _reject_leftover(stage: str, tokens: list[str], consumed: set[int]) -> None:
    leftovers = [tokens[i] for i in range(len(tokens)) if i not in consumed]
    if leftovers:
        raise ValidationError(
            f"Unrecognized token(s) in video pipe stage '{stage}': {' '.join(leftovers)}",
            "INVALID_PIPE_STAGE",
            {"hint": "Separate stages with | ; check pifang pipe video --help"},
        )


def parse_video_pipe(dsl: str) -> list[PipeStage]:
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

        if name == "trim":
            for i, t in enumerate(tokens[1:], 1):
                if t.startswith("start="):
                    args["start"] = t.split("=", 1)[1]
                    consumed.add(i)
                elif t.startswith("duration="):
                    args["duration"] = t.split("=", 1)[1]
                    consumed.add(i)
                elif t.startswith("end="):
                    args["end"] = t.split("=", 1)[1]
                    consumed.add(i)
                elif "-" in t and "start" not in args:
                    start, end = t.split("-", 1)
                    args["start"] = start
                    args["end"] = end
                    consumed.add(i)
            _reject_leftover(name, tokens, consumed)

        elif name == "resize":
            if len(tokens) < 2:
                raise ValidationError("resize stage requires WxH", "PIPE_SYNTAX")
            spec = tokens[1].lower()
            consumed.add(1)
            try:
                w, h = spec.split("x", 1)
                args["width"] = int(w)
                args["height"] = int(h)
            except ValueError as exc:
                raise ValidationError(
                    f"Invalid resize size: {tokens[1]!r} (expected WxH)",
                    "PIPE_SYNTAX",
                ) from exc
            for i, t in enumerate(tokens[2:], 2):
                if t.startswith("fit="):
                    args["fit"] = t.split("=", 1)[1]
                    consumed.add(i)
            _reject_leftover(name, tokens, consumed)

        elif name == "transcode":
            if len(tokens) > 1:
                args["format"] = tokens[1]
                consumed.add(1)
            _reject_leftover(name, tokens, consumed)

        else:
            raise ValidationError(f"Unknown video pipe stage: {name}", "UNKNOWN_PIPE_STAGE")

        stages.append(PipeStage(name=name, args=args))
    return stages


def run_video_pipe(
    dsl: str,
    input_path: Path,
    output_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    stages = parse_video_pipe(dsl)
    current_in = input_path
    temp_outputs: list[Path] = []
    result: OpResult | None = None

    try:
        for i, stage in enumerate(stages):
            is_last = i == len(stages) - 1
            suffix = output_path.suffix or ".mp4"
            step_out = (
                output_path if is_last else output_path.parent / f".pifang-vpipe-{input_path.stem}-{i}{suffix}"
            )
            if not is_last:
                temp_outputs.append(step_out)

            if stage.name == "trim":
                result = ops.trim(
                    current_in,
                    step_out,
                    start=stage.args.get("start", 0),
                    end=stage.args.get("end"),
                    duration=stage.args.get("duration"),
                    force=force or not is_last,
                    dry_run=dry_run,
                )
            elif stage.name == "resize":
                result = ops.resize(
                    current_in,
                    step_out,
                    width=int(stage.args["width"]),
                    height=int(stage.args["height"]),
                    fit=stage.args.get("fit", "cover"),
                    force=force or not is_last,
                    dry_run=dry_run,
                )
            elif stage.name == "transcode":
                fmt = stage.args.get("format", "mp4")
                out = step_out if step_out.suffix else step_out.with_suffix(f".{fmt}")
                result = ops.transcode(current_in, out, format=fmt, force=force or not is_last, dry_run=dry_run)
            else:
                raise ValidationError(f"Unknown stage: {stage.name}", "UNKNOWN_PIPE_STAGE")

            if not result.ok:
                return result
            current_in = result.output_path or step_out

        if result is None:
            raise ValidationError("Pipe has no stages", "EMPTY_PIPE")

        result.command = "pipe.video"
        result.input_path = input_path
        return result
    finally:
        for tmp in temp_outputs:
            if tmp.exists() and not dry_run:
                tmp.unlink(missing_ok=True)
