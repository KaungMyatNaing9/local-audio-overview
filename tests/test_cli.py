import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from audio_overview.cli import main
from audio_overview.errors import AudioOverviewError
from audio_overview.run import build_engine
from audio_overview.settings import Settings
from audio_overview.speech.voices import download_models, list_voice_names
from tests.conftest import SAMPLE


def test_help_and_version() -> None:
    assert main(["--help"]) == 0
    assert main(["--version"]) == 0


def test_missing_source_is_a_clean_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(tmp_path / "missing.md"), "-o", str(tmp_path / "episode.mp3"), "--tts", "tone"])
    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_cli_fake_tone_writes_the_episode(tmp_path: Path) -> None:
    output = tmp_path / "episode.mp3"
    code = main(
        [
            str(SAMPLE),
            "-o",
            str(output),
            "--backend",
            "fake",
            "--tts",
            "tone",
            "--length",
            "short",
            "--quiet",
        ]
    )
    assert code == 0
    assert output.stat().st_size > 1000
    transcript = (tmp_path / "episode.transcript.md").read_text(encoding="utf-8")
    assert "Maya" in transcript
    assert "Leo" in transcript
    chapters = json.loads((tmp_path / "episode.chapters.json").read_text(encoding="utf-8"))
    assert chapters["chapters"][0]["start_ms"] == 0
    grounding = json.loads((tmp_path / "episode.grounding.json").read_text(encoding="utf-8"))
    assert grounding["flag_count"] == 0
    assert grounding["method"] == "lexical"
    script = (tmp_path / "episode.script.jsonl").read_text(encoding="utf-8")
    assert '"speaker": "Maya"' in script
    assert '"speaker": "Leo"' in script


def test_strict_replay_stops_before_audio(tmp_path: Path) -> None:
    replay = tmp_path / "bad.jsonl"
    replay.write_text(
        '{"speaker": "Maya", "text": "The secret code is 987654.", "section": "Opening"}\n'
        '{"speaker": "Leo", "text": "I heard that.", "section": "Opening"}\n',
        encoding="utf-8",
    )
    output = tmp_path / "episode.mp3"
    code = main(
        [
            str(SAMPLE),
            "-o",
            str(output),
            "--backend",
            "fake",
            "--tts",
            "tone",
            "--replay",
            str(replay),
            "--strict",
            "--quiet",
        ]
    )
    assert code == 2
    assert not output.exists()
    grounding = json.loads((tmp_path / "episode.grounding.json").read_text(encoding="utf-8"))
    assert grounding["flag_count"] == 1
    assert grounding["flags"][0]["kind"] == "number"


def test_module_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "audio_overview", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "two-host" in completed.stdout


def test_download_models_uses_the_injected_fetch(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(url: str, dest: Path) -> None:
        calls.append(url)
        dest.write_bytes(b"x" * 64)

    model, voices = download_models(tmp_path, "int8", fetch=fetch, min_bytes=32)
    assert model.name == "kokoro-v1.0.int8.onnx"
    assert voices.name == "voices-v1.0.bin"
    assert len(calls) == 2
    download_models(tmp_path, "int8", fetch=fetch, min_bytes=32)
    assert len(calls) == 2


def test_list_voices_reads_a_npz(tmp_path: Path) -> None:
    path = tmp_path / "voices.bin"
    with path.open("wb") as handle:
        np.savez(handle, af_heart=np.zeros(2), am_michael=np.zeros(2), jf_alpha=np.zeros(2))
    names = list_voice_names(path)
    assert names == ["af_heart", "am_michael", "jf_alpha"]


def test_missing_kokoro_files_explain_how_to_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIO_OVERVIEW_KOKORO_MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setenv("AUDIO_OVERVIEW_KOKORO_VOICES", str(tmp_path / "missing.bin"))
    settings = Settings(tts="kokoro")
    settings.validate()
    with pytest.raises(AudioOverviewError, match="download-models"):
        build_engine(settings)


def test_env_selects_the_openai_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIO_OVERVIEW_BACKEND", "openai")
    monkeypatch.setenv("AUDIO_OVERVIEW_BASE_URL", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("AUDIO_OVERVIEW_MODEL", "local-model")
    monkeypatch.setenv("AUDIO_OVERVIEW_API_KEY", "abc")
    notes = Path("samples/paper-boat-workshop.md")
    # Build settings the way the CLI does, without speaking.
    from audio_overview.settings import apply_env

    settings = Settings(backend=os.environ["AUDIO_OVERVIEW_BACKEND"])
    apply_env(settings)
    assert settings.backend == "openai"
    assert settings.model == "local-model"
    assert settings.api_key == "abc"
    assert notes.name.endswith(".md")
