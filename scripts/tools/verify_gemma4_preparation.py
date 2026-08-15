#!/usr/bin/env python3
"""Write or verify the immutable Gemma 4 model preparation record."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from typing import Any


MODEL_ID = "google/gemma-4-12B-it"
MODEL_REVISION = "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
EXPECTED_PACKAGES = {
    "torch": "2.5.1",
    "torchvision": "0.20.1",
    "transformers": "5.15.0",
    "openai": "2.54.0",
    "Pillow": "11.0.0",
}
EXPECTED_WEIGHT_BYTES = 23_919_549_408
HASH_LIMIT_BYTES = 128 * 1024 * 1024
REQUIRED_METADATA_FILES = (
    "chat_template.jinja",
    "config.json",
    "generation_config.json",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    metadata: dict[str, Any] = {"size": size}
    if size <= HASH_LIMIT_BYTES:
        metadata["sha256"] = sha256(path)
    return metadata


def weight_files(model_dir: Path) -> list[Path]:
    single = model_dir / "model.safetensors"
    index = model_dir / "model.safetensors.index.json"
    if single.is_file() and index.exists():
        raise ValueError("both single-file and sharded weight layouts are present")
    if single.is_file():
        return [single]
    if not index.is_file():
        raise ValueError(
            "model weights are missing: expected model.safetensors or "
            "model.safetensors.index.json"
        )

    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
        declared_names = sorted(set(payload["weight_map"].values()))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid model weight index: {index}") from exc
    if not declared_names or any(Path(name).name != name for name in declared_names):
        raise ValueError(f"invalid shard name in model weight index: {index}")

    declared = [model_dir / name for name in declared_names]
    missing = [path for path in declared if not path.is_file()]
    if missing:
        raise ValueError(f"declared weight shard is missing: {missing[0]}")
    observed_names = sorted(path.name for path in model_dir.glob("model-*.safetensors"))
    if observed_names != declared_names:
        raise ValueError(
            "weight shards do not exactly match model.safetensors.index.json"
        )
    return [index, *declared]


def inspect_files(model_dir: Path) -> dict[str, dict[str, Any]]:
    if not model_dir.is_dir():
        raise ValueError(f"model directory does not exist: {model_dir}")
    incomplete = sorted(model_dir.rglob("*.incomplete"))
    if incomplete:
        raise ValueError(f"incomplete download files remain: {incomplete[:3]}")

    files: dict[str, dict[str, Any]] = {}
    for relative in REQUIRED_METADATA_FILES:
        path = model_dir / relative
        if not path.is_file():
            raise ValueError(f"required model file is missing: {path}")
        files[relative] = file_metadata(path)

    try:
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("model config.json is not valid JSON") from exc
    if config.get("architectures") != ["Gemma4UnifiedForConditionalGeneration"]:
        raise ValueError("model architecture is not Gemma4 Unified 12B")
    if config.get("model_type") != "gemma4_unified" or config.get("dtype") != "bfloat16":
        raise ValueError("model type or dtype does not match the pinned checkpoint")

    weights = weight_files(model_dir)
    shard_paths = [path for path in weights if path.suffix == ".safetensors"]
    total_weight_bytes = sum(path.stat().st_size for path in shard_paths)
    if total_weight_bytes != EXPECTED_WEIGHT_BYTES:
        raise ValueError(
            "model weight size does not match the pinned revision: "
            f"expected={EXPECTED_WEIGHT_BYTES}, observed={total_weight_bytes}"
        )
    for path in weights:
        files[path.name] = file_metadata(path)
    return files


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError(f"prepared package is missing: {name}") from exc


def runtime_packages() -> dict[str, str]:
    observed = {name: package_version(name) for name in EXPECTED_PACKAGES}
    normalized = dict(observed)
    normalized["torch"] = observed["torch"].split("+")[0]
    normalized["torchvision"] = observed["torchvision"].split("+")[0]
    if normalized != EXPECTED_PACKAGES:
        raise ValueError(
            f"prepared package versions do not match: "
            f"expected={EXPECTED_PACKAGES!r}, observed={observed!r}"
        )
    return observed


def build_record(model_dir: Path) -> dict[str, Any]:
    packages = runtime_packages()
    return {
        "schema_version": 1,
        "status": "complete",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_dir": str(model_dir.resolve()),
        "container_image": os.environ.get(
            "CONTAINER_IMAGE",
            "pytorch/pytorch@sha256:"
            "c8268a92a69bd500f8be0e665b2630ee006dadaf7bfbc24249141b15ff622755",
        ),
        "python": platform.python_version(),
        "packages": packages,
        "files": inspect_files(model_dir),
    }


def write_record(record_path: Path, record: dict[str, Any]) -> None:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = record_path.with_name(f".{record_path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(record_path)


def verify_record(model_dir: Path, record_path: Path) -> dict[str, Any]:
    if not record_path.is_file():
        raise ValueError(
            f"preparation record is missing: {record_path}; run the prepare script first"
        )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    packages = runtime_packages()
    expected = {
        "schema_version": 1,
        "status": "complete",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_dir": str(model_dir.resolve()),
        "container_image": os.environ.get(
            "CONTAINER_IMAGE",
            "pytorch/pytorch@sha256:"
            "c8268a92a69bd500f8be0e665b2630ee006dadaf7bfbc24249141b15ff622755",
        ),
        "python": platform.python_version(),
        "packages": packages,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(
                f"preparation record mismatch for {key}: "
                f"expected={value!r}, observed={record.get(key)!r}"
            )

    observed_files = inspect_files(model_dir)
    if record.get("files") != observed_files:
        raise ValueError("prepared model files no longer match the preparation record")
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_dir = args.model_dir.resolve()
    record_path = args.record.resolve()
    if args.write:
        record = build_record(model_dir)
        write_record(record_path, record)
        print(f"[OK] wrote Gemma 4 preparation record: {record_path}")
    else:
        verify_record(model_dir, record_path)
        print(f"[OK] verified Gemma 4 preparation: {model_dir}")


if __name__ == "__main__":
    main()
