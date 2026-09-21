"""Pifang CLI entrypoint."""

from __future__ import annotations

import enum
import functools
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Callable, Optional, TypeVar

import click
import typer

from pifang import __version__
from pifang.core.batch import BatchSpec, batch_run
from pifang.core.doctor import run_doctor
from pifang.core.output import emit_error_text, emit_json, emit_progress, emit_text, format_text
from pifang.core.pipe import run_image_pipe
from pifang.core.recipe import load_recipes_detailed, run_recipe
from pifang.core.result import OpResult
from pifang.core.setup_deps import setup_report
from pifang.core.video_pipe import run_video_pipe
from pifang.domains.doc.ingest import convert_batch, ingest_batch
from pifang.domains.doc.info import pdf_info
from pifang.domains.doc.ocr import ocr_pdf
from pifang.domains.doc.pdf_ops import extract_images, merge_pdfs, split_pdf
from pifang.domains.image import ops
from pifang.domains.image.analyze import analyze_path
from pifang.domains.image.bg import flatten_background, remove_background
from pifang.domains.image.packs import run_pack
from pifang.domains.image.recolor import recolor_foreground
from pifang.domains.meta.index import build_index, validate_ingest_manifest
from pifang.domains.text.chunk import chunk_markdown_file
from pifang.domains.text.frontmatter import add_frontmatter
from pifang.domains.transcribe.ops import AUDIO_SUFFIXES, VIDEO_SUFFIXES, transcribe_media
from pifang.domains.video import ops as video_ops
from pifang.domains.video.info import video_info
from pifang.errors import (
    MISSING_DEPENDENCY,
    PARTIAL_BATCH,
    PROCESSING,
    PifangError,
    SUCCESS,
    VALIDATION,
    ValidationError,
)

app = typer.Typer(
    name="pifang",
    help="Agent-first CLI for deterministic image, document, and media processing.",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

image_app = typer.Typer(help="Image atoms, recipes, and transforms.")
video_app = typer.Typer(help="Video atoms and ffmpeg transforms.")
audio_app = typer.Typer(help="Audio helpers (transcription aliases).")
recipe_app = typer.Typer(help="Named multi-step pipelines.")
pipe_app = typer.Typer(help="Inline pipe DSL chains.")
batch_app = typer.Typer(help="Folder-scale batch processing.")
batch_run_app = typer.Typer(help="Run a command across many files.")
doc_app = typer.Typer(help="PDF → markdown (+ images). Use convert for plain export; ingest for corpus/RAG prep.")
text_app = typer.Typer(help="Post-ingest markdown helpers.")
meta_app = typer.Typer(help="Corpus indexing and manifest validation.")

app.add_typer(image_app, name="image")
app.add_typer(video_app, name="video")
app.add_typer(audio_app, name="audio")
app.add_typer(recipe_app, name="recipe")
app.add_typer(pipe_app, name="pipe")
app.add_typer(batch_app, name="batch")
app.add_typer(doc_app, name="doc")
app.add_typer(text_app, name="text")
app.add_typer(meta_app, name="meta")
batch_app.add_typer(batch_run_app, name="run")


# --- Closed-set enums (shown in --help; bad values → validation exit 1 via run()) ---


class FitMode(str, enum.Enum):
    contain = "contain"
    cover = "cover"


class Anchor(str, enum.Enum):
    center = "center"
    top = "top"
    bottom = "bottom"
    left = "left"
    right = "right"


class BgMode(str, enum.Enum):
    white = "white"
    black = "black"
    auto = "auto"
    color = "color"
    checker = "checker"


class ChunkMode(str, enum.Enum):
    heading = "heading"
    size = "size"


class DocEngine(str, enum.Enum):
    fast = "fast"
    opendataloader = "opendataloader"
    marker = "marker"
    docling = "docling"


class ImageFormat(str, enum.Enum):
    png = "png"
    jpg = "jpg"
    jpeg = "jpeg"
    webp = "webp"
    gif = "gif"
    avif = "avif"


# Shared option type aliases (leaf registration for trailing position + --help)
ForceFlag = Annotated[bool, typer.Option("--force", help="Overwrite outputs even if unchanged.")]
DryRunFlag = Annotated[bool, typer.Option("--dry-run", help="Preview without writing files.")]
VerboseFlag = Annotated[bool, typer.Option("--verbose", "-v", help="Progress on stderr.")]
JsonFlag = Annotated[
    bool,
    typer.Option("--json", help="JSON stdout (recommended for agents). Default is plain text."),
]


@dataclass
class GlobalOpts:
    json_output: bool = False
    dry_run: bool = False
    verbose: bool = False
    force: bool = False


def _opts(ctx: typer.Context) -> GlobalOpts:
    if ctx.obj is None:
        ctx.obj = GlobalOpts()
    return ctx.obj


def _merge_leaf_opts(
    ctx: typer.Context,
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> GlobalOpts:
    """OR leaf flags into root GlobalOpts (either position enables the flag)."""
    opts = _opts(ctx)
    opts.force = opts.force or force
    opts.dry_run = opts.dry_run or dry_run
    opts.verbose = opts.verbose or verbose
    return opts


def _finish(ctx: typer.Context, payload: dict | OpResult, *, exit_code: int = SUCCESS) -> None:
    if isinstance(payload, OpResult):
        data = payload.to_dict()
    else:
        data = payload
    if _opts(ctx).json_output:
        emit_json(data)
    elif isinstance(payload, OpResult) and payload.ok and (payload.output_path or payload.input_path):
        emit_text(f"OK {payload.command} -> {payload.output_path or payload.input_path}")
    else:
        emit_text(format_text(data))
    raise typer.Exit(exit_code)


def _emit_error(json_output: bool, envelope: dict[str, Any]) -> None:
    """Error envelope on stdout (--json) or message + hint on stderr (text)."""
    if json_output:
        emit_json(envelope)
        return
    emit_error_text(f"Error [{envelope.get('error_code', 'ERROR')}]: {envelope.get('message', '')}")
    hint = (envelope.get("recovery") or {}).get("hint")
    if hint:
        emit_error_text(f"Hint: {hint}")


def _handle_error(ctx: typer.Context, exc: PifangError) -> None:
    _emit_error(_opts(ctx).json_output, exc.to_dict())
    raise typer.Exit(exc.exit_code)


def _handle_internal(ctx: typer.Context, exc: BaseException) -> None:
    opts = _opts(ctx)
    if opts.verbose:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    _emit_error(
        opts.json_output,
        {
            "ok": False,
            "error_code": "INTERNAL",
            "message": f"{type(exc).__name__}: {exc}",
            "exit_code": PROCESSING,
            "recovery": {
                "hint": "Re-run with --verbose for a traceback; report a bug if this persists",
            },
        }
    )
    raise typer.Exit(PROCESSING)


F = TypeVar("F", bound=Callable[..., Any])


def safe_command(func: F) -> F:
    """Wrap a Typer command: PifangError → envelope; any other Exception → INTERNAL."""

    @functools.wraps(func)
    def wrapper(ctx: typer.Context, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("json_flag"):
            _opts(ctx).json_output = True
        try:
            return func(ctx, *args, **kwargs)
        except typer.Exit:
            raise
        except click.exceptions.Exit:
            raise
        except PifangError as exc:
            _handle_error(ctx, exc)
        except Exception as exc:  # noqa: BLE001 — last-resort JSON envelope
            _handle_internal(ctx, exc)

    return wrapper  # type: ignore[return-value]


def _version_callback(value: bool) -> None:
    if value:
        if "--json" in sys.argv[1:]:
            emit_json({"ok": True, "version": __version__})
        else:
            emit_text(f"pifang {__version__}")
        raise typer.Exit(SUCCESS)


@app.callback()
def global_options(
    ctx: typer.Context,
    json_output: JsonFlag = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing files.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Progress on stderr.")] = False,
    force: Annotated[bool, typer.Option("--force", help="Overwrite outputs even if unchanged.")] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    ctx.ensure_object(type(None))
    ctx.obj = GlobalOpts(json_output=json_output, dry_run=dry_run, verbose=verbose, force=force)


@app.command("doctor")
@safe_command
def doctor_cmd(
    ctx: typer.Context,
    doc: Annotated[bool, typer.Option("--doc", help="Also check PDF/doc ingestion deps.")] = False,
    video: Annotated[bool, typer.Option("--video", help="Also check ffmpeg/ffprobe.")] = False,
    transcribe: Annotated[bool, typer.Option("--transcribe", help="Also check Faster-Whisper.")] = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Check installed dependencies."""
    report = run_doctor(doc=doc, video=video, transcribe=transcribe)
    code = SUCCESS if report.ok else MISSING_DEPENDENCY
    _finish(ctx, report.to_dict(), exit_code=code)


@app.command("setup")
@safe_command
def setup_cmd(
    ctx: typer.Context,
    extras: Annotated[
        Optional[str],
        typer.Option(
            "--extras",
            help="Comma-separated pip extras: doc,transcribe,doc-odl,doc-heavy,fast,video",
        ),
    ] = None,
    install: Annotated[
        bool,
        typer.Option("--install", help="Run pip install for the selected extras (Python packages only)."),
    ] = False,
    system: Annotated[
        bool,
        typer.Option("--system/--no-system", help="Include ffmpeg/Java install commands (never auto-run)."),
    ] = True,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Show (or install) dependency extras. System tools (ffmpeg/Java) are printed, not installed."""
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    extra_list = [e.strip() for e in extras.split(",") if e.strip()] if extras else None
    payload = setup_report(
        extras=extra_list,
        install=install,
        dry_run=opts.dry_run,
        show_system=system,
    )
    code = SUCCESS if payload.get("ok") else MISSING_DEPENDENCY
    _finish(ctx, payload, exit_code=code)


@app.command("version")
@safe_command
def version_cmd(ctx: typer.Context, json_flag: JsonFlag = False) -> None:  # noqa: ARG001
    """Print package version."""
    _finish(ctx, {"ok": True, "version": __version__})


@recipe_app.command("list")
@safe_command
def recipe_list(ctx: typer.Context, json_flag: JsonFlag = False) -> None:  # noqa: ARG001
    """List built-in and custom recipes."""
    detailed = load_recipes_detailed()
    payload: dict[str, Any] = {
        "ok": True,
        "recipes": [
            {
                "name": r.name,
                "domain": r.domain,
                "source": r.source,
                "description": r.description,
                "steps": [list(s.keys())[0] for s in r.steps],
            }
            for r in detailed.recipes
        ],
    }
    if detailed.warnings:
        payload["warnings"] = detailed.warnings
    _finish(ctx, payload)


def _common_image(
    ctx: typer.Context,
    input_path: Path,
    output: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[GlobalOpts, Path, Path]:
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    emit_progress(f"Processing {input_path}", opts.verbose)
    return opts, input_path, output


@image_app.command("resize")
@safe_command
def image_resize(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    width: Annotated[Optional[int], typer.Option("--width")] = None,
    height: Annotated[Optional[int], typer.Option("--height")] = None,
    fit: Annotated[FitMode, typer.Option("--fit", help="contain | cover")] = FitMode.contain,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Resize an image (contain or cover)."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.resize(
        inp, out, width=width, height=height, fit=fit.value, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@image_app.command("crop")
@safe_command
def image_crop(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    width: Annotated[int, typer.Option("--width")],
    height: Annotated[int, typer.Option("--height")],
    x: Annotated[Optional[int], typer.Option("--x")] = None,
    y: Annotated[Optional[int], typer.Option("--y")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Crop to a rectangle."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.crop(inp, out, width=width, height=height, x=x, y=y, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@image_app.command("crop-square")
@safe_command
def image_crop_square(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    anchor: Annotated[Anchor, typer.Option("--anchor", help="center | top | bottom | left | right")] = Anchor.center,
    size: Annotated[Optional[int], typer.Option("--size")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Center-crop (or anchor-crop) to a square, optionally resize."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.crop_square(
        inp, out, anchor=anchor.value, size=size, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@image_app.command("fit")
@safe_command
def image_fit(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    width: Annotated[int, typer.Option("--width")],
    height: Annotated[int, typer.Option("--height")],
    color: Annotated[str, typer.Option("--color")] = "#000000",
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Fit image inside canvas with letterbox/pillarbox fill color."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.fit(
        inp, out, width=width, height=height, color=color, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@image_app.command("convert")
@safe_command
def image_convert(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    format: Annotated[ImageFormat, typer.Option("--format", "--to", help="png | jpg | jpeg | webp | gif | avif")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 85,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Convert image format."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.convert(
        inp, out, format=format.value, quality=quality, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@image_app.command("compress")
@safe_command
def image_compress(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    quality: Annotated[int, typer.Option("--quality", "-q")] = 80,
    max_kb: Annotated[Optional[int], typer.Option("--max-kb")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Compress image; optionally target a max file size in KB."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.compress(
        inp, out, quality=quality, max_kb=max_kb, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@image_app.command("strip-exif")
@safe_command
def image_strip_exif(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Remove EXIF/metadata from an image."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.strip_exif(inp, out, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@image_app.command("remove-bg")
@safe_command
def image_remove_bg(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output path (.png recommended).")],
    mode: Annotated[BgMode, typer.Option("--mode", help="white | black | auto | color | checker")] = BgMode.auto,
    color: Annotated[Optional[str], typer.Option("--color", help="Background to remove (with --mode color).")] = None,
    tolerance: Annotated[int, typer.Option("--tolerance", "-t", help="Color match fuzz 0–128.")] = 32,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Remove white, black, solid, or checkerboard background → transparent PNG."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = remove_background(
        inp,
        out,
        mode=mode.value,  # type: ignore[arg-type]
        color=color,
        tolerance=tolerance,
        force=opts.force,
        dry_run=opts.dry_run,
    )
    _finish(ctx, result)


@image_app.command("flatten-bg")
@safe_command
def image_flatten_bg(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    color: Annotated[str, typer.Option("--color", "-c", help="Fill color: white, black, or #rrggbb.")] = "white",
    format: Annotated[Optional[ImageFormat], typer.Option("--format", "--to", help="png, webp, jpg (jpg drops alpha).")] = None,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 90,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Fill transparent areas with a solid color; foreground colors stay unchanged."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = flatten_background(
        inp,
        out,
        color=color,
        format=format.value if format else None,
        quality=quality,
        force=opts.force,
        dry_run=opts.dry_run,
    )
    _finish(ctx, result)


@image_app.command("recolor")
@safe_command
def image_recolor(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output (.png or .webp to keep alpha).")],
    color: Annotated[str, typer.Option("--color", "-c", help="New foreground color: white, black, or #rrggbb.")] = "white",
    alpha_threshold: Annotated[int, typer.Option("--alpha-threshold", help="Min alpha to recolor (0–255).")] = 1,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Recolor all non-transparent pixels to one color; transparency preserved (logo → white/black)."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = recolor_foreground(
        inp,
        out,
        color=color,
        alpha_threshold=alpha_threshold,
        force=opts.force,
        dry_run=opts.dry_run,
    )
    _finish(ctx, result)


@image_app.command("info")
@safe_command
def image_info(ctx: typer.Context, input_path: Path, json_flag: JsonFlag = False) -> None:  # noqa: ARG001
    """Show image metadata (dimensions, format, EXIF count)."""
    data = ops.info(input_path)
    _finish(ctx, {"ok": True, "info": data})


@image_app.command("thumbnail")
@safe_command
def image_thumbnail(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    max_edge: Annotated[int, typer.Option("--max-edge")] = 256,
    crop: Annotated[bool, typer.Option("--crop/--no-crop")] = False,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Create a thumbnail (contain by default; --crop for square)."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = ops.thumbnail(inp, out, max_edge=max_edge, crop=crop, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@image_app.command("analyze")
@safe_command
def image_analyze(ctx: typer.Context, input_path: Path, json_flag: JsonFlag = False) -> None:  # noqa: ARG001
    """Analyze dimensions, shape, and crop hints for platform exports."""
    analysis = analyze_path(input_path)
    _finish(ctx, {"ok": True, "command": "image.analyze", "analysis": analysis.to_dict()})


def _pack_options(
    format: str,
    quality: int,
    only: Optional[str],
    skip_heavy: bool,
) -> tuple[str, int, set[str] | None, bool]:
    only_set = {s.strip() for s in only.split(",") if s.strip()} if only else None
    return format, quality, only_set, skip_heavy


def _run_pack_cmd(
    ctx: typer.Context,
    pack: str,
    input_path: Path,
    output_dir: Path,
    format: str,
    quality: int,
    only: Optional[str],
    skip_heavy: bool,
    custom: Optional[list[str]],
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    fmt, quality, only_set, skip_heavy = _pack_options(format, quality, only, skip_heavy)
    result = run_pack(
        pack,
        input_path,
        output_dir,
        only=only_set,
        custom_specs=custom,
        skip_heavy=skip_heavy,
        format=fmt,
        quality=quality,
        force=opts.force,
        dry_run=opts.dry_run,
    )
    _finish(ctx, result.to_dict())


@image_app.command("social-pack")
@safe_command
def image_social_pack(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 85,
    only: Annotated[Optional[str], typer.Option("--only", help="Filter: instagram, youtube, instagram-tall, …")] = None,
    skip_heavy: Annotated[bool, typer.Option("--skip-heavy", help="Skip targets needing heavy aspect crop.")] = False,
    custom: Annotated[Optional[list[str]], typer.Option("--custom", help="Add WxH:slug[:anchor], e.g. 1200x800:newsletter:top")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Export social sizes: Instagram square + tall 4:5 + story, Facebook, LinkedIn, X, YouTube, …"""
    _run_pack_cmd(
        ctx, "social", input_path, output, format.value, quality, only, skip_heavy, custom,
        force=force, dry_run=dry_run, verbose=verbose,
    )


@image_app.command("video-cover-pack")
@safe_command
def image_video_cover_pack(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 85,
    only: Annotated[Optional[str], typer.Option("--only", help="Filter: widescreen-thumbnail, cover-square, …")] = None,
    skip_heavy: Annotated[bool, typer.Option("--skip-heavy", help="Skip targets needing heavy aspect crop.")] = False,
    custom: Annotated[Optional[list[str]], typer.Option("--custom", help="Add WxH:slug[:anchor]")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Export video covers: widescreen thumbnail, square cover, OG preview, channel banner."""
    _run_pack_cmd(
        ctx, "video-cover", input_path, output, format.value, quality, only, skip_heavy, custom,
        force=force, dry_run=dry_run, verbose=verbose,
    )


@image_app.command("blog-pack")
@safe_command
def image_blog_pack(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 85,
    only: Annotated[Optional[str], typer.Option("--only", help="Filter: blog-featured, blog-hero, …")] = None,
    skip_heavy: Annotated[bool, typer.Option("--skip-heavy")] = False,
    custom: Annotated[Optional[list[str]], typer.Option("--custom", help="Add WxH:slug[:anchor]")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Export blog featured images: WordPress/OG, hero, Medium header, card thumbnail."""
    _run_pack_cmd(
        ctx, "blog", input_path, output, format.value, quality, only, skip_heavy, custom,
        force=force, dry_run=dry_run, verbose=verbose,
    )


@image_app.command("podcast-pack")
@safe_command
def image_podcast_pack(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 90,
    only: Annotated[Optional[str], typer.Option("--only", help="Filter: podcast-cover, podcast-cover-standard, …")] = None,
    skip_heavy: Annotated[bool, typer.Option("--skip-heavy")] = False,
    custom: Annotated[Optional[list[str]], typer.Option("--custom", help="Add WxH:slug[:anchor]")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Export podcast artwork: Apple/Spotify square covers (1400 and 3000)."""
    _run_pack_cmd(
        ctx, "podcast", input_path, output, format.value, quality, only, skip_heavy, custom,
        force=force, dry_run=dry_run, verbose=verbose,
    )


@image_app.command("custom-pack")
@safe_command
def image_custom_pack(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    custom: Annotated[list[str], typer.Option("--custom", help="WxH:slug[:anchor] — repeat for multiple")],
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 85,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Export only your --custom sizes (no built-in platform targets)."""
    _run_pack_cmd(
        ctx, "custom", input_path, output, format.value, quality, None, False, custom,
        force=force, dry_run=dry_run, verbose=verbose,
    )


@image_app.command("avatar")
@safe_command
def image_avatar(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    size: Annotated[int, typer.Option("--size", "-s")] = 256,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Avatar recipe: crop-square + resize + webp."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_recipe("avatar", inp, out, {"size": size}, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@image_app.command("hero")
@safe_command
def image_hero(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    width: Annotated[int, typer.Option("--width")] = 1920,
    height: Annotated[int, typer.Option("--height")] = 1080,
    max_kb: Annotated[int, typer.Option("--max-kb")] = 400,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Hero recipe: cover resize + compress."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_recipe(
        "hero", inp, out, {"width": width, "height": height, "max_kb": max_kb}, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@image_app.command("social-square")
@safe_command
def image_social_square(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    size: Annotated[int, typer.Option("--size", "-s")] = 1080,
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Social-square recipe: crop-square + convert."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_recipe(
        "social-square",
        inp,
        out,
        {"size": size, "format": format.value},
        force=opts.force,
        dry_run=opts.dry_run,
    )
    _finish(ctx, result)


@pipe_app.command("image")
@safe_command
def pipe_image(
    ctx: typer.Context,
    stages: Annotated[str, typer.Argument(help='Pipe DSL, e.g. "crop-square | resize 512 | to-webp"')],
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Run an image pipe DSL chain."""
    opts, inp, out = _common_image(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_image_pipe(stages, inp, out, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


def _batch_payload(result: Any, command: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": result.failed == 0,
        "command": command,
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "skipped": result.skipped,
        "not_attempted": result.not_attempted,
        "manifest": str(result.manifest_path) if result.manifest_path else None,
    }
    if result.first_error_code:
        payload["error_code"] = result.first_error_code
        payload["message"] = result.first_error_message
    return payload


@batch_run_app.command("image")
@safe_command
def batch_run_image(
    ctx: typer.Context,
    command: Annotated[str, typer.Argument(help="Recipe or command name, e.g. convert or avatar")],
    path: Path,
    output_dir: Annotated[Path, typer.Option("-o", "--output")],
    glob: Annotated[str, typer.Option("--glob")] = "*",
    recursive: Annotated[bool, typer.Option("--recursive/--no-recursive")] = False,
    jobs: Annotated[int, typer.Option("--jobs", "-j")] = 1,
    manifest: Annotated[Optional[Path], typer.Option("--manifest")] = None,
    continue_on_error: Annotated[bool, typer.Option("--continue-on-error")] = False,
    format: Annotated[ImageFormat, typer.Option("--format", "--to")] = ImageFormat.webp,
    quality: Annotated[int, typer.Option("--quality", "-q")] = 85,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Batch-run an image command or recipe over a folder."""
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    spec = BatchSpec(
        domain="image",
        command=command,
        paths=[path],
        output_dir=output_dir,
        glob_pattern=glob,
        recursive=recursive,
        jobs=jobs,
        manifest_path=manifest,
        continue_on_error=continue_on_error,
        force=opts.force,
        dry_run=opts.dry_run,
        params={"format": format.value, "quality": quality},
    )
    result = batch_run(spec)
    code = SUCCESS
    if result.failed and result.succeeded:
        code = PARTIAL_BATCH
    elif result.failed:
        code = VALIDATION
    _finish(ctx, _batch_payload(result, f"batch.image.{command}"), exit_code=code)


def _common_video(
    ctx: typer.Context,
    input_path: Path,
    output: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[GlobalOpts, Path, Path]:
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    emit_progress(f"Processing {input_path}", opts.verbose)
    return opts, input_path, output


def _run_transcribe(
    ctx: typer.Context,
    input_path: Path,
    output_dir: Path,
    *,
    model: str,
    language: str | None,
    write_vtt: bool,
    media_kind: str,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    emit_progress(f"Transcribing {input_path}", opts.verbose)
    result = transcribe_media(
        input_path,
        output_dir,
        model=model,
        language=language,
        write_vtt=write_vtt,
        force=opts.force,
        dry_run=opts.dry_run,
        media_kind=media_kind,  # type: ignore[arg-type]
    )
    _finish(ctx, result)


@app.command("transcribe")
@safe_command
def transcribe_cmd(
    ctx: typer.Context,
    input_path: Path,
    output_dir: Annotated[Path, typer.Option("-o", "--output", help="Output directory for transcript artifacts.")],
    model: Annotated[str, typer.Option("--model", help="Faster-Whisper model size.")] = "base",
    language: Annotated[Optional[str], typer.Option("--language", help="Language code (auto-detect if omitted).")] = None,
    vtt: Annotated[bool, typer.Option("--vtt", help="Also write WebVTT.")] = False,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Transcribe audio or video → timeline JSON + SRT."""
    _run_transcribe(
        ctx, input_path, output_dir, model=model, language=language, write_vtt=vtt, media_kind="auto",
        force=force, dry_run=dry_run, verbose=verbose,
    )


@video_app.command("transcribe")
@safe_command
def video_transcribe_cmd(
    ctx: typer.Context,
    input_path: Path,
    output_dir: Annotated[Path, typer.Option("-o", "--output", help="Output directory for transcript artifacts.")],
    model: Annotated[str, typer.Option("--model", help="Faster-Whisper model size.")] = "base",
    language: Annotated[Optional[str], typer.Option("--language", help="Language code (auto-detect if omitted).")] = None,
    vtt: Annotated[bool, typer.Option("--vtt", help="Also write WebVTT.")] = False,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Transcribe video (ffmpeg extract → Faster-Whisper)."""
    if input_path.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValidationError(
            f"video transcribe requires a video file, got: {input_path.suffix.lower() or input_path.name}",
            "NOT_VIDEO",
        )
    _run_transcribe(
        ctx, input_path, output_dir, model=model, language=language, write_vtt=vtt, media_kind="video",
        force=force, dry_run=dry_run, verbose=verbose,
    )


@audio_app.command("transcribe")
@safe_command
def audio_transcribe_cmd(
    ctx: typer.Context,
    input_path: Path,
    output_dir: Annotated[Path, typer.Option("-o", "--output", help="Output directory for transcript artifacts.")],
    model: Annotated[str, typer.Option("--model", help="Faster-Whisper model size.")] = "base",
    language: Annotated[Optional[str], typer.Option("--language", help="Language code (auto-detect if omitted).")] = None,
    vtt: Annotated[bool, typer.Option("--vtt", help="Also write WebVTT.")] = False,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Transcribe audio only (rejects video inputs)."""
    if input_path.suffix.lower() not in AUDIO_SUFFIXES:
        raise ValidationError(
            f"audio transcribe requires an audio file, got: {input_path.suffix.lower() or input_path.name}",
            "NOT_AUDIO",
        )
    _run_transcribe(
        ctx, input_path, output_dir, model=model, language=language, write_vtt=vtt, media_kind="audio",
        force=force, dry_run=dry_run, verbose=verbose,
    )


@video_app.command("info")
@safe_command
def video_info_cmd(ctx: typer.Context, input_path: Path, json_flag: JsonFlag = False) -> None:  # noqa: ARG001
    """Video metadata via ffprobe."""
    data = video_info(input_path)
    _finish(ctx, {"ok": True, "command": "video.info", "info": data})


@video_app.command("transcode")
@safe_command
def video_transcode(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    codec: Annotated[str, typer.Option("--codec")] = "libx264",
    crf: Annotated[int, typer.Option("--crf")] = 23,
    format: Annotated[Optional[str], typer.Option("--format")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Transcode video with ffmpeg."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.transcode(inp, out, codec=codec, crf=crf, format=format, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("trim")
@safe_command
def video_trim(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    start: Annotated[str, typer.Option("--start")] = "0",
    end: Annotated[Optional[str], typer.Option("--end")] = None,
    duration: Annotated[Optional[str], typer.Option("--duration")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Trim a video by start/end/duration."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.trim(inp, out, start=start, end=end, duration=duration, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("extract-audio")
@safe_command
def video_extract_audio(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    format: Annotated[str, typer.Option("--format")] = "mp3",
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Extract audio track from video."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.extract_audio(inp, out, format=format, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("concat")
@safe_command
def video_concat(
    ctx: typer.Context,
    inputs: Annotated[list[Path], typer.Argument(help="Two or more video files.")],
    output: Annotated[Path, typer.Option("-o", "--output")],
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Concatenate videos."""
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.concat(inputs, output, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("to-gif")
@safe_command
def video_to_gif(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    fps: Annotated[int, typer.Option("--fps")] = 10,
    width: Annotated[Optional[int], typer.Option("--width")] = 320,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Convert video to GIF."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.to_gif(inp, out, fps=fps, width=width, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("extract-frames")
@safe_command
def video_extract_frames(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    fps: Annotated[float, typer.Option("--fps")] = 1.0,
    format: Annotated[str, typer.Option("--format")] = "png",
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Extract frames from video."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.extract_frames(inp, out, fps=fps, format=format, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("resize")
@safe_command
def video_resize(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    width: Annotated[int, typer.Option("--width")],
    height: Annotated[int, typer.Option("--height")],
    fit: Annotated[FitMode, typer.Option("--fit", help="contain | cover")] = FitMode.contain,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Resize video (contain or cover)."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.resize(
        inp, out, width=width, height=height, fit=fit.value, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@video_app.command("normalize-audio")
@safe_command
def video_normalize_audio(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    target_lufs: Annotated[float, typer.Option("--target-lufs")] = -16.0,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Normalize audio loudness (LUFS)."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.normalize_audio(inp, out, target_lufs=target_lufs, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("captions")
@safe_command
def video_captions(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    srt: Annotated[Optional[Path], typer.Option("--srt")] = None,
    vtt: Annotated[Optional[Path], typer.Option("--vtt")] = None,
    burn_in: Annotated[bool, typer.Option("--burn-in/--sidecar", help="Burn into video or copy sidecar.")] = False,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Attach or burn-in captions."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = video_ops.captions(inp, out, srt=srt, vtt=vtt, burn_in=burn_in, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@video_app.command("social-clip")
@safe_command
def video_social_clip(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    width: Annotated[int, typer.Option("--width")] = 1080,
    height: Annotated[int, typer.Option("--height")] = 1920,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Social-clip recipe (vertical resize)."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_recipe(
        "social-clip", inp, out, {"width": width, "height": height}, force=opts.force, dry_run=opts.dry_run
    )
    _finish(ctx, result)


@video_app.command("podcast-audio")
@safe_command
def video_podcast_audio(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    format: Annotated[str, typer.Option("--format")] = "mp3",
    target_lufs: Annotated[float, typer.Option("--target-lufs")] = -16.0,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Podcast-audio recipe: extract + normalize."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_recipe(
        "podcast-audio",
        inp,
        out,
        {"format": format, "target_lufs": target_lufs},
        force=opts.force,
        dry_run=opts.dry_run,
    )
    _finish(ctx, result)


@pipe_app.command("video")
@safe_command
def pipe_video(
    ctx: typer.Context,
    stages: Annotated[str, typer.Argument(help='e.g. "trim 0-30 | resize 1080x1920 | transcode mp4"')],
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output")],
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Run a video pipe DSL chain."""
    opts, inp, out = _common_video(ctx, input_path, output, force=force, dry_run=dry_run, verbose=verbose)
    result = run_video_pipe(stages, inp, out, force=opts.force, dry_run=opts.dry_run)
    _finish(ctx, result)


@batch_run_app.command("video")
@safe_command
def batch_run_video(
    ctx: typer.Context,
    command: Annotated[str, typer.Argument(help="Recipe or transcode")],
    path: Path,
    output_dir: Annotated[Path, typer.Option("-o", "--output")],
    glob: Annotated[str, typer.Option("--glob")] = "*",
    recursive: Annotated[bool, typer.Option("--recursive/--no-recursive")] = False,
    jobs: Annotated[int, typer.Option("--jobs", "-j")] = 1,
    manifest: Annotated[Optional[Path], typer.Option("--manifest")] = None,
    continue_on_error: Annotated[bool, typer.Option("--continue-on-error")] = False,
    format: Annotated[str, typer.Option("--format", "--to")] = "mp4",
    crf: Annotated[int, typer.Option("--crf")] = 23,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Batch-run a video command or recipe over a folder."""
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    spec = BatchSpec(
        domain="video",
        command=command,
        paths=[path],
        output_dir=output_dir,
        glob_pattern=glob,
        recursive=recursive,
        jobs=jobs,
        manifest_path=manifest,
        continue_on_error=continue_on_error,
        force=opts.force,
        dry_run=opts.dry_run,
        params={"format": format, "crf": crf},
    )
    result = batch_run(spec)
    code = SUCCESS
    if result.failed and result.succeeded:
        code = PARTIAL_BATCH
    elif result.failed:
        code = VALIDATION
    _finish(ctx, _batch_payload(result, f"batch.video.{command}"), exit_code=code)


@doc_app.command("convert")
@safe_command
def doc_convert(
    ctx: typer.Context,
    path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    engine: Annotated[
        Optional[DocEngine],
        typer.Option("--engine", help="fast | opendataloader | marker | docling"),
    ] = None,
    recursive: Annotated[bool, typer.Option("--recursive/--no-recursive")] = False,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """PDF → markdown + images folder only (no ingest.jsonl, no engine JSON)."""
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    result = convert_batch(
        path,
        output,
        engine_name=engine.value if engine else None,
        recursive=recursive,
        dry_run=opts.dry_run,
    )
    code = SUCCESS if result.ok else PARTIAL_BATCH if any(r.ok for r in result.results) else VALIDATION
    _finish(ctx, result.to_dict(), exit_code=code)


@doc_app.command("ingest")
@safe_command
def doc_ingest(
    ctx: typer.Context,
    path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    engine: Annotated[
        Optional[DocEngine],
        typer.Option("--engine", help="fast | opendataloader | marker | docling"),
    ] = None,
    recursive: Annotated[bool, typer.Option("--recursive/--no-recursive")] = False,
    manifest: Annotated[Optional[Path], typer.Option("--manifest", help="JSONL manifest path.")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """PDF → markdown + images + ingest.jsonl (RAG / vision-LLM corpus prep)."""
    opts = _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    result = ingest_batch(
        path,
        output,
        engine_name=engine.value if engine else None,
        recursive=recursive,
        manifest_path=manifest,
        dry_run=opts.dry_run,
    )
    code = SUCCESS if result.ok else PARTIAL_BATCH if any(r.ok for r in result.results) else VALIDATION
    _finish(ctx, result.to_dict(), exit_code=code)


@doc_app.command("info")
@safe_command
def doc_info(ctx: typer.Context, path: Path, json_flag: JsonFlag = False) -> None:  # noqa: ARG001
    """PDF metadata (pages, encryption, title)."""
    data = pdf_info(path)
    _finish(ctx, {"ok": True, "command": "doc.info", "info": data})


@doc_app.command("split")
@safe_command
def doc_split(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory.")],
    pages: Annotated[Optional[str], typer.Option("--pages", help="Page range e.g. 1,3-5 (1-based). Omit for all pages.")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Split a PDF into single-page files."""
    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    data = split_pdf(input_path, output, pages=pages)
    _finish(ctx, {"ok": True, "command": "doc.split", **data})


@doc_app.command("merge")
@safe_command
def doc_merge(
    ctx: typer.Context,
    inputs: Annotated[list[Path], typer.Argument(help="Two or more PDFs to merge.")],
    output: Annotated[Path, typer.Option("-o", "--output", help="Merged PDF path.")],
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Merge PDFs in order."""
    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    data = merge_pdfs(inputs, output)
    _finish(ctx, {"ok": True, "command": "doc.merge", **data})


@doc_app.command("extract-images")
@safe_command
def doc_extract_images(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory for images.")],
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Extract embedded images from a PDF."""
    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    data = extract_images(input_path, output)
    _finish(ctx, {"ok": True, "command": "doc.extract-images", **data})


@doc_app.command("ocr")
@safe_command
def doc_ocr(
    ctx: typer.Context,
    input_path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output markdown path.")],
    lang: Annotated[str, typer.Option("--lang", help="Tesseract language code.")] = "eng",
    dpi: Annotated[int, typer.Option("--dpi", help="Render DPI for OCR.")] = 300,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """OCR a scanned PDF to markdown via Tesseract."""
    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    data = ocr_pdf(input_path, output, lang=lang, dpi=dpi)
    _finish(ctx, {"ok": True, "command": "doc.ocr", **data})


@text_app.command("chunk")
@safe_command
def text_chunk(
    ctx: typer.Context,
    path: Path,
    output: Annotated[Path, typer.Option("-o", "--output", help="Output directory for chunks.")],
    mode: Annotated[ChunkMode, typer.Option("--mode", help="heading | size")] = ChunkMode.heading,
    max_chars: Annotated[int, typer.Option("--max-chars", help="Max chars per chunk (size mode).")] = 4000,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Split markdown into RAG-sized chunks."""
    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    data = chunk_markdown_file(path, output, mode=mode.value, max_chars=max_chars)
    _finish(ctx, {"ok": True, "command": "text.chunk", **data})


@text_app.command("frontmatter")
@safe_command
def text_frontmatter(
    ctx: typer.Context,
    path: Path,
    fields_json: Annotated[str, typer.Option("--fields", help="JSON object of frontmatter fields.")],
    output: Annotated[Optional[Path], typer.Option("-o", "--output", help="Write to new file instead of in-place.")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Prepend YAML frontmatter to a markdown file."""
    import json as _json

    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    fields = _json.loads(fields_json)
    if not isinstance(fields, dict):
        raise ValidationError("JSON fields must be an object", "INVALID_FIELDS")
    if output:
        data = add_frontmatter(path, fields, in_place=False, output=output)
    else:
        data = add_frontmatter(path, fields, in_place=True)
    _finish(ctx, {"ok": True, "command": "text.frontmatter", **data})


@meta_app.command("index")
@safe_command
def meta_index(
    ctx: typer.Context,
    root: Path,
    output: Annotated[Optional[Path], typer.Option("-o", "--output", help="index.jsonl path (default: root/index.jsonl).")] = None,
    force: ForceFlag = False,
    dry_run: DryRunFlag = False,
    verbose: VerboseFlag = False,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Build JSONL index of ingested markdown + image folders."""
    _merge_leaf_opts(ctx, force=force, dry_run=dry_run, verbose=verbose)
    data = build_index(root, output)
    _finish(ctx, {"ok": True, "command": "meta.index", **data})


@meta_app.command("validate")
@safe_command
def meta_validate(
    ctx: typer.Context,
    manifest: Path,
    root: Annotated[Optional[Path], typer.Option("--root", help="Also flag markdown files not listed in manifest.")] = None,
    json_flag: JsonFlag = False,  # noqa: ARG001
) -> None:
    """Validate ingest.jsonl entries against files on disk."""
    data = validate_ingest_manifest(manifest, root)
    code = SUCCESS if data["valid"] else VALIDATION
    _finish(ctx, {"ok": data["valid"], "command": "meta.validate", **data}, exit_code=code)


def run() -> None:
    """CLI entry: usage errors and unexpected escapes honor --json (envelope) or text (stderr).

    With standalone_mode=False, Click returns Exit.exit_code as an int instead of
    raising SystemExit — convert that to a real process exit status.
    """
    json_output = "--json" in sys.argv[1:]
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int):
            raise SystemExit(result)
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.exit_code) from None
    except click.exceptions.UsageError as exc:
        msg = exc.format_message() if hasattr(exc, "format_message") else str(exc)
        _emit_error(
            json_output,
            {
                "ok": False,
                "error_code": "VALIDATION_ERROR",
                "message": msg,
                "exit_code": VALIDATION,
                "recovery": {"hint": "Run with --help to see valid options and usage"},
            }
        )
        raise SystemExit(VALIDATION) from None
    except PifangError as exc:
        _emit_error(json_output, exc.to_dict())
        raise SystemExit(exc.exit_code) from None
    except Exception as exc:  # noqa: BLE001
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        _emit_error(
            json_output,
            {
                "ok": False,
                "error_code": "INTERNAL",
                "message": f"{type(exc).__name__}: {exc}",
                "exit_code": PROCESSING,
                "recovery": {
                    "hint": "Re-run with --verbose for a traceback; report a bug if this persists",
                },
            }
        )
        raise SystemExit(PROCESSING) from None


if __name__ == "__main__":
    run()
