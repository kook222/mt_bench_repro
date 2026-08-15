from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Gemma4RuntimeContractTest(unittest.TestCase):
    EXPECTED_WEIGHT_BYTES = 23_919_549_408
    REQUIRED_MODEL_FILES = (
        "chat_template.jinja",
        "config.json",
        "generation_config.json",
        "processor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
    )

    @staticmethod
    def fake_runtime_metadata(root: Path) -> None:
        for name, version in (
            ("torch", "2.5.1"),
            ("torchvision", "0.20.1"),
            ("transformers", "5.15.0"),
            ("openai", "2.54.0"),
            ("Pillow", "11.0.0"),
        ):
            metadata = root / f"{name}-{version}.dist-info" / "METADATA"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(
                f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
                encoding="utf-8",
            )

    def create_model_metadata(self, model: Path) -> None:
        model.mkdir()
        for name in self.REQUIRED_MODEL_FILES:
            if name == "config.json":
                content = json.dumps(
                    {
                        "architectures": ["Gemma4UnifiedForConditionalGeneration"],
                        "model_type": "gemma4_unified",
                        "dtype": "bfloat16",
                    }
                )
            else:
                content = f"{name}\n"
            (model / name).write_text(content, encoding="utf-8")

    def test_download_and_install_are_prepare_only(self) -> None:
        prepare = (ROOT / "scripts/run/a100/prepare_gemma4_12b_a100.sh").read_text()
        judge = (ROOT / "scripts/run/a100/run_judge_gemma4_12b_a100.sh").read_text()
        self.assertIn('bin/hf" download', prepare)
        self.assertIn("pip install", prepare)
        self.assertNotIn("hf download", judge)
        self.assertNotIn("pip install", judge)
        self.assertNotIn("vllm serve", judge)
        self.assertIn('TRANSFORMERS_CLI" serve', judge)
        self.assertIn("--reasoning auto", judge)
        self.assertIn("HF_HUB_OFFLINE=1", judge)
        self.assertIn("TRANSFORMERS_OFFLINE=1", judge)

    def test_shared_paths_match_existing_a100_layout(self) -> None:
        common = (ROOT / "scripts/run/a100/gemma4_12b_common.sh").read_text()
        judge = (ROOT / "scripts/run/a100/run_judge_gemma4_12b_a100.sh").read_text()
        self.assertIn('$WORKSPACE_PARENT/models', common)
        self.assertIn('$RUN_ROOT/runtime/gemma4_12b', common)
        self.assertIn('$RUN_ROOT/reproduction/$lang/judgments/gemma4/judge_12B', judge)
        self.assertIn('$RUN_ROOT/aggregates/gemma4_12b/$lang', judge)
        self.assertIn('$PROJECT_DIR/data/$lang/answers', judge)

    def test_generic_runner_uses_pinned_runtime_contract(self) -> None:
        common = (ROOT / "scripts/run/a100/gemma4_12b_common.sh").read_text()
        prepare = (ROOT / "scripts/run/a100/prepare_gemma4_12b_a100.sh").read_text()
        judge = (ROOT / "scripts/run/a100/run_judge_gemma4_12b_a100.sh").read_text()
        self.assertIn('^hf_[A-Za-z0-9]+$', prepare)
        self.assertIn("prepare_record.json", common)
        self.assertIn("GEMMA4_PREPARE_RECORD", prepare)
        self.assertNotIn("sleep 5", judge)
        self.assertNotIn("tail -", judge)
        self.assertIn("scripts/tools/wait_for_http.py", judge)

    def test_missing_preparation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/tools/verify_gemma4_preparation.py"),
                    "--model-dir",
                    str(root / "model"),
                    "--record",
                    str(root / "prepare.json"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preparation record is missing", result.stderr)

    def test_preparation_record_detects_changed_model_metadata(self) -> None:
        verifier = ROOT / "scripts/tools/verify_gemma4_preparation.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model"
            self.create_model_metadata(model)
            with (model / "model.safetensors").open("wb") as stream:
                stream.truncate(self.EXPECTED_WEIGHT_BYTES)
            record = root / "prepare.json"
            site_packages = root / "site-packages"
            self.fake_runtime_metadata(site_packages)
            subprocess_env = dict(os.environ, PYTHONPATH=str(site_packages))

            subprocess.run(
                [
                    sys.executable,
                    str(verifier),
                    "--model-dir",
                    str(model),
                    "--record",
                    str(record),
                    "--write",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=subprocess_env,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(verifier),
                    "--model-dir",
                    str(model),
                    "--record",
                    str(record),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=subprocess_env,
            )

            (model / "tokenizer_config.json").write_text("changed\n", encoding="utf-8")
            changed = subprocess.run(
                [
                    sys.executable,
                    str(verifier),
                    "--model-dir",
                    str(model),
                    "--record",
                    str(record),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=subprocess_env,
            )
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("no longer match", changed.stderr)

    def test_preparation_accepts_complete_sharded_weights(self) -> None:
        verifier = ROOT / "scripts/tools/verify_gemma4_preparation.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model"
            self.create_model_metadata(model)
            shard_names = [
                "model-00001-of-00002.safetensors",
                "model-00002-of-00002.safetensors",
            ]
            shard_sizes = [12_000_000_000, self.EXPECTED_WEIGHT_BYTES - 12_000_000_000]
            for name, size in zip(shard_names, shard_sizes):
                with (model / name).open("wb") as stream:
                    stream.truncate(size)
            (model / "model.safetensors.index.json").write_text(
                json.dumps(
                    {
                        "weight_map": {
                            "model.embed_tokens.weight": shard_names[0],
                            "model.layers.0.weight": shard_names[1],
                        }
                    }
                ),
                encoding="utf-8",
            )
            record = root / "prepare.json"
            site_packages = root / "site-packages"
            self.fake_runtime_metadata(site_packages)
            result = subprocess.run(
                [
                    sys.executable,
                    str(verifier),
                    "--model-dir",
                    str(model),
                    "--record",
                    str(record),
                    "--write",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=dict(os.environ, PYTHONPATH=str(site_packages)),
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
