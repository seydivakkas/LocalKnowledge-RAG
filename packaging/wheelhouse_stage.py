"""G09: hash-lock exact Windows runtime wheels and stage source notices.

Engineering evidence only: a notice copied from a wheel is NOT a license
grant for Windows system runtimes, compiled codecs, or customer redistribution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

NOTICE_NAMES = ("license", "licence", "copying", "copyright", "notice")
MAX_NOTICE = 2 * 1024 * 1024
MAX_TOTAL_NOTICES = 24 * 1024 * 1024


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exact_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        parts = list(requirement.specifier)
        if requirement.extras or requirement.marker or requirement.url or len(parts) != 1 or parts[0].operator != "==":
            raise ValueError(f"Expected one exact unmarked pin: {line}")
        name = canonicalize_name(requirement.name)
        if name in pins:
            raise ValueError(f"Duplicate distribution pin: {name}")
        pins[name] = parts[0].version
    if not pins:
        raise ValueError("Empty dependency closure")
    return pins


def verified_wheels(wheel_dir: Path, pin_file: Path) -> list[tuple[str, str, Path]]:
    pins = exact_pins(pin_file)
    tags = set(sys_tags())
    chosen: dict[str, Path] = {}
    for wheel in sorted(wheel_dir.glob("*.whl")):
        name, version, _build, candidates = parse_wheel_filename(wheel.name)
        name = canonicalize_name(name)
        if name not in pins or str(version) != pins[name] or not (tags & candidates):
            raise ValueError(f"Unexpected version or incompatible wheel: {wheel.name}")
        if name in chosen:
            raise ValueError(f"Ambiguous wheel for {name}")
        with zipfile.ZipFile(wheel) as archive:
            _safe_members(archive)
            if archive.testzip() is not None:
                raise ValueError(f"Corrupt wheel: {wheel.name}")
        chosen[name] = wheel
    if set(chosen) != set(pins):
        raise ValueError(f"Missing wheels for: {sorted(set(pins) - set(chosen))}")
    return [(name, pins[name], chosen[name]) for name in sorted(pins)]


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    seen: set[str] = set()
    output = []
    for member in archive.infolist():
        path = member.filename
        pieces = PurePosixPath(path).parts
        if (not path or "\\" in path or path.startswith("/") or
                not pieces or any(x in ("", ".", "..") for x in pieces) or
                ":" in pieces[0] or path in seen):
            raise ValueError(f"Unsafe wheel archive member: {path!r}")
        seen.add(path)
        mode = member.external_attr >> 16
        if stat.S_IFMT(mode) == stat.S_IFLNK:
            raise ValueError(f"Wheel symlink is not trusted: {path}")
        output.append(member)
    return output


def lock(wheel_dir: Path, pins: Path, output: Path) -> dict:
    wheels = verified_wheels(wheel_dir, pins)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = [(name, version, file_hash(path)) for name, version, path in wheels]
    output.write_text(
        "# G09 runtime wheel SHA-256 lock for this CI build. Not a permanent trusted upstream lock.\n" +
        "".join(f"{name}=={version} --hash=sha256:{digest}\n" for name, version, digest in rows),
        encoding="utf-8",
    )
    return {"count": len(rows), "hash_locked": True}


def _notice(member: zipfile.ZipInfo) -> bool:
    base = PurePosixPath(member.filename).name.lower()
    return (not member.is_dir() and
            any(base.startswith(prefix) for prefix in NOTICE_NAMES) and
            member.file_size <= MAX_NOTICE)


def stage_notices(wheel_dir: Path, pins: Path, dest: Path) -> dict:
    wheels = verified_wheels(wheel_dir, pins)
    if dest.exists():
        raise FileExistsError(f"Refusing to overwrite existing notice tree: {dest}")
    dest.mkdir(parents=True)
    remaining = MAX_TOTAL_NOTICES
    result = []
    missing = []
    for name, version, wheel in wheels:
        notices = []
        with zipfile.ZipFile(wheel) as archive:
            members = _safe_members(archive)
            selected = [m for m in members if _notice(m)]
            if not selected:
                missing.append(name)
            target = dest / f"{name}-{version}"
            target.mkdir()
            for n, member in enumerate(selected):
                if member.file_size > remaining:
                    raise ValueError("License notice material exceeds extraction budget")
                blob = archive.read(member)
                if len(blob) != member.file_size:
                    raise ValueError("Wheel notice size mismatch")
                remaining -= len(blob)
                safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", PurePosixPath(member.filename).name)
                path = target / f"{n:03d}_{safe_name}"
                with path.open("xb") as stream:
                    stream.write(blob)
                notices.append({
                    "wheel_member": member.filename,
                    "packaged_path": path.relative_to(dest).as_posix(),
                    "size_bytes": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                })
        result.append({
            "distribution": name,
            "version": version,
            "wheel": wheel.name,
            "wheel_sha256": file_hash(wheel),
            "notices": notices,
        })
    evidence = {
        "schema": 1, "wheel_count": len(wheels),
        "source_wheel_installation_hash_locked": True,
        "missing_notice_packages": missing,
        "distributions": result,
        "legal_clearance": False,
        "commercial_release": "HOLD",
        "note": "Notices were copied from wheel candidates installed by hash-locked CI. Native codec, PDFium, CPython, Tcl/Tk, Microsoft REDIST and end-user license rights are NOT cleared.",
    }
    (dest / "runtime_notice_manifest.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("lock")
    p.add_argument("wheels", type=Path)
    p.add_argument("pins", type=Path)
    p.add_argument("output", type=Path)
    q = sub.add_parser("notices")
    q.add_argument("wheels", type=Path)
    q.add_argument("pins", type=Path)
    q.add_argument("outdir", type=Path)
    args = parser.parse_args()
    if args.action == "lock":
        result = lock(args.wheels, args.pins, args.output)
    else:
        result = stage_notices(args.wheels, args.pins, args.outdir)
    print(json.dumps({k: v for k, v in result.items() if k not in ("distributions",)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
