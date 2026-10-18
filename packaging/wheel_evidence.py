"""G09: Exact Windows wheel candidates, bundled-native hash matching and notices.

Engineering evidence only. Matching bytes and notices is NOT a redistribution grant.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import tomllib
import zipfile

from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

NATIVE_SUFFIXES = (".dll", ".pyd", ".so", ".dylib")
NOTICE_WORDS = ("license", "licence", "copying", "notice", "copyright")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_closure(project_file: Path) -> list[dict]:
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))
    roots = [Requirement(raw) for raw in project["project"]["dependencies"]]
    pending = list(roots)
    found: dict[str, dict] = {}
    while pending:
        requirement = pending.pop(0)
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        key = canonicalize_name(requirement.name)
        if key in found:
            continue
        dist = metadata.distribution(requirement.name)
        if not requirement.specifier.contains(dist.version, prereleases=True):
            raise ValueError(f"Installed runtime mismatch: {key} {dist.version} / {requirement.specifier}")
        found[key] = {"name": key, "version": dist.version}
        for item in dist.requires or []:
            dependency = Requirement(item)
            if not dependency.marker or dependency.marker.evaluate({"extra": ""}):
                pending.append(dependency)
    return [found[key] for key in sorted(found)]


def plan(project_file: Path, output: Path) -> list[dict]:
    specs = runtime_closure(project_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{item['name']}=={item['version']}\n" for item in specs), encoding="utf-8")
    return specs


def audit(wheel_dir: Path, plan_file: Path, native_inventory: Path) -> dict:
    specs = {}
    for line in plan_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        req = Requirement(line)
        if len(req.specifier) != 1 or next(iter(req.specifier)).operator != "==":
            raise ValueError(f"Not an exact pin: {line}")
        name = canonicalize_name(req.name)
        if name in specs:
            raise ValueError(f"Duplicate runtime requirement: {name}")
        specs[name] = next(iter(req.specifier)).version
    if not specs:
        raise ValueError("Empty runtime closure")
    supported_tags = set(sys_tags())
    matches = {}
    for wheel in sorted(wheel_dir.glob("*.whl")):
        name, version, _build, tags = parse_wheel_filename(wheel.name)
        name = canonicalize_name(name)
        if name not in specs:
            raise ValueError(f"Unexpected wheel: {wheel.name}")
        if str(version) != specs[name] or not (supported_tags & tags):
            raise ValueError(f"Wrong version/platform wheel: {wheel.name}")
        if name in matches:
            raise ValueError(f"Ambiguous wheel candidates for {name}")
        matches[name] = wheel
    if set(matches) != set(specs):
        raise ValueError(f"Missing wheels: {sorted(set(specs) - set(matches))}")
    native_hashes: dict[str, list[dict]] = {}
    wheel_rows = []
    for name in sorted(matches):
        wheel = matches[name]
        notices, native = [], []
        with zipfile.ZipFile(wheel) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Corrupt wheel: {wheel.name}")
            for member in archive.namelist():
                base = member.rsplit("/", 1)[-1].lower()
                if not base or member.endswith("/"):
                    continue
                if any(word in base for word in NOTICE_WORDS):
                    notices.append(member)
                if base.endswith(NATIVE_SUFFIXES):
                    blob = archive.read(member)
                    digest = sha256_bytes(blob)
                    native.append({"path": member, "sha256": digest, "size_bytes": len(blob)})
                    native_hashes.setdefault(digest, []).append(
                        {"distribution": name, "wheel": wheel.name, "member": member})
        wheel_rows.append({
            "distribution": name, "version": specs[name], "wheel": wheel.name,
            "wheel_sha256": sha256_bytes(wheel.read_bytes()),
            "license_notice_paths": sorted(notices),
            "native_members": native,
            "notice_review_required": not bool(notices),
        })
    inventory = json.loads(native_inventory.read_text(encoding="utf-8"))
    native_rows = []
    for item in inventory.get("native_files", []):
        evidence = native_hashes.get(item["sha256"], [])
        native_rows.append({
            "path": item["path"], "sha256": item["sha256"],
            "exact_wheel_candidates": evidence,
            "classification": "BYTE_MATCH_WHEEL_CANDIDATE" if evidence else "UNMATCHED_REQUIRES_REVIEW",
        })
    return {
        "schema_version": 1,
        "project_runtime_requirements": sorted(specs),
        "wheel_count": len(wheel_rows),
        "bundled_native_count": len(native_rows),
        "matched_bundled_native_count": sum(bool(row["exact_wheel_candidates"]) for row in native_rows),
        "wheels": wheel_rows,
        "bundled_native": native_rows,
        "legal_clearance": False,
        "commercial_release": "HOLD",
        "source_provenance_verified": False,
        "note": "Wheel candidate byte equality does not prove build source, origin, Visual C++ REDIST entitlement, third-party codec obligations, or customer redistribution permission.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("pyproject", type=Path)
    p.add_argument("output", type=Path)
    a = sub.add_parser("audit")
    a.add_argument("wheel_dir", type=Path)
    a.add_argument("plan_file", type=Path)
    a.add_argument("native_inventory", type=Path)
    a.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(args.pyproject, args.output)
        print(f"Runtime dependency closure: {len(result)} installed exact versions")
    else:
        result = audit(args.wheel_dir, args.plan_file, args.native_inventory)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"Wheel audit: {result['wheel_count']} wheels, {result['matched_bundled_native_count']}/{result['bundled_native_count']} native exact matches; commercial HOLD")


if __name__ == "__main__":
    main()
