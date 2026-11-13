# Local Audio Overview

One command turns a PDF, web page, markdown file, text file, or local git
repository into a two-host MP3. Speech runs on your machine. There is no
account and no daily cap.

Version 0.1.0 speaks English only. The default speech engine is
[Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) through
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx). Without a language
model, the `fake` backend can still read the source aloud, or speak a script
you already wrote.

This repository is MIT licensed. The owner is Kaung (GitHub
[KaungMyatNaing9](https://github.com/KaungMyatNaing9)).

## What 0.1.0 does

- `audio-overview <source> -o episode.mp3`
- Length: `short`, `medium`, or `long` (a target for the language model; the
  fake read-through uses it as a sentence cap)
- Tone: `conversational`, `explanatory`, `skeptical`, or `enthusiastic`
- Host names and Kokoro voice ids
- Backends:
  - `fake` reads sentences from the source, or speaks a JSONL file you pass
    with `--replay`. No API key.
  - `ollama` talks to a local Ollama server's OpenAI-compatible API
  - `openai` talks to any OpenAI-compatible `/v1/chat/completions` endpoint
- Ingestion:
  - PDF text extraction with `pypdf` (no OCR)
  - URL article extraction with `trafilatura` (navigation is dropped)
  - UTF-8 markdown and plain text
  - A local directory: README, a file tree, manifest files, and short excerpts
    of key source files. Dependency folders are skipped.
- Long sources are split on paragraph boundaries, with a small overlap.
  Sources over 14,000 characters are outlined chunk by chunk, then merged.
- The script is JSON lines of `speaker`, `text`, and `section`.
- A lexical grounding check flags numbers, quotations, and proper names that
  do not appear in the source. With a real model, one repair pass rewrites
  flagged lines. `--strict` refuses to render audio if any flag remains.
- Turns are stitched with short pauses (longer when the section changes) into
  one MP3 or WAV, plus a transcript, chapter JSON, and chapter markers inside
  the MP3.

## What it does not do

- It does not OCR scanned PDFs.
- It does not prove that a paraphrase is true to the source. A line with no
  number, quotation, or proper name is not flagged. A name that is only the
  first word of a sentence is not flagged either.
- Repo episodes are grounded on the summary, not on files that were not opened.
- Speech is English (`en-us`, `en-gb`). The voice file contains other
  languages; this release does not phonemize them.
- There is no web UI. See [ROADMAP.md](ROADMAP.md).

## Install

Tested on Python 3.12. `pydub` still imports the standard-library `audioop`
module, which Python 3.13 removes, so stay on 3.10, 3.11, or 3.12.

System packages:

```bash
sudo apt install ffmpeg espeak-ng
```

`ffmpeg` writes the MP3 and embeds chapters. `espeak-ng` is what the Kokoro
phonemizer uses.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[kokoro,dev]"
audio-overview download-models
```

`download-models` saves `kokoro-v1.0.onnx` (about 311 MB) and `voices-v1.0.bin`
(about 27 MB) under `~/.cache/audio-overview/`. `--variant int8` downloads the
smaller int8 model instead. Override the location with
`AUDIO_OVERVIEW_MODEL_DIR`, or point at the files directly:

```bash
export AUDIO_OVERVIEW_KOKORO_MODEL=/path/to/kokoro-v1.0.onnx
export AUDIO_OVERVIEW_KOKORO_VOICES=/path/to/voices-v1.0.bin
```

The weights are Apache-2.0 and are not vendored in this repo. The first run
needs a network connection for that download only.

## Listen to the sample

`samples/paper-boat-workshop.md` is an original short piece written for this
repo. It is fiction. `samples/paper-boat-workshop.script.jsonl` is a
hand-written two-host script. Every number, quotation, and proper name in that
script is in the essay; the test suite checks that.

A rendered episode is already in `samples/demo/`:

- `episode.mp3` (1 minute 44 seconds, Kokoro voices `af_heart` and `am_michael`)
- `episode.transcript.md`
- `episode.chapters.json`
- `episode.grounding.json` (0 flags)

Regenerate it:

```bash
audio-overview samples/paper-boat-workshop.md \
  -o samples/demo/episode.mp3 \
  --backend fake \
  --replay samples/paper-boat-workshop.script.jsonl
```

A read-through, with no replay file, speaks sentences from the source in order.
It does not paraphrase:

```bash
audio-overview samples/paper-boat-workshop.md -o readthrough.mp3 --backend fake
```

`--tts tone` skips Kokoro and writes sine waves, one pitch per voice. The tests
use it. It is not for listening.

## Use your own source

```bash
audio-overview notes.md -o episode.mp3 --backend fake
audio-overview paper.pdf -o episode.mp3 --length medium --backend ollama --model llama3.2
audio-overview https://example.com/story -o episode.mp3 \
  --backend openai --base-url http://127.0.0.1:8080/v1 --model local-model
audio-overview ./my-repo -o episode.mp3 --host-a Mina --host-b Jules \
  --voice-a af_bella --voice-b am_fenrir
```

Useful flags:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--length` | `short` | `short`, `medium`, `long` |
| `--tone` | `conversational` | style hint for the model; the fake backend only changes one intro line |
| `--host-a`, `--host-b` | Maya, Leo | spoken names; they do not have to appear in the source |
| `--voice-a`, `--voice-b` | `af_heart`, `am_michael` | Kokoro voice ids (`audio-overview list-voices`) |
| `--backend` | `fake`, or `AUDIO_OVERVIEW_BACKEND` | `fake`, `ollama`, `openai` |
| `--model` | see below | model name |
| `--base-url` | Ollama's local port, or `AUDIO_OVERVIEW_BASE_URL` | OpenAI-compatible `/v1` root |
| `--replay` | none | JSONL script; forces the fake backend and skips repair |
| `--strict` | off | exit 2 instead of writing audio when grounding flags remain |
| `--no-repair` | repair is on for real models | skip the rewrite pass |
| `--tts` | `kokoro` | `kokoro` or `tone` |
| `--speech-rate` | `1.0` | Kokoro speed, 0.5 to 2.0 |

Sidecars next to `episode.mp3`:

- `episode.transcript.md`
- `episode.chapters.json`
- `episode.script.jsonl`
- `episode.grounding.json`

Exit codes: `0` wrote the audio, `1` a usage or runtime error, `2` `--strict`
and the script is still ungrounded.

## Language model

Ollama and any other OpenAI-compatible server share one client. Temperature is
fixed at 0.3. The pipeline asks for an outline, then JSON lines. If the
grounding check flags a line, it asks once for a full rewrite.

```bash
export AUDIO_OVERVIEW_BACKEND=ollama          # default base URL http://127.0.0.1:11434/v1
export AUDIO_OVERVIEW_MODEL=llama3.2          # ollama's default name if unset
export AUDIO_OVERVIEW_BASE_URL=http://127.0.0.1:8080/v1
export AUDIO_OVERVIEW_MODEL=local-model
export AUDIO_OVERVIEW_API_KEY=...             # sent as Bearer; omit it for Ollama
export AUDIO_OVERVIEW_TIMEOUT=180             # seconds
```

Prefer the environment variable for the API key. `--api-key` works and will
show up in the process list.

The client is covered by a unit test that checks the request body without
opening a socket. A live Ollama trial on this VM is described with the
hardware notes below. It is not the sample episode.

## Why Kokoro

Kokoro-82M is published under Apache-2.0 (the model card says `license:
apache-2.0`; kokoro-onnx's package metadata also says the model is Apache
2.0). The `kokoro-onnx` runtime is MIT. It runs on CPU through ONNX Runtime,
with no PyTorch install. One voice file holds many speakers, so the two hosts
do not need two separate downloads.

`af_heart` and `am_michael` are the defaults. In the project's own voice table,
`af_heart` is graded A and `am_michael` is graded C+. Those grades describe
their training data. They are not a listening score from this repo.

Piper is a reasonable engine and is not wired up. The current `piper-tts`
package is GPL-3.0-or-later, which is a poor fit next to this MIT project, and
some Piper voices are non-commercial. Another engine is a class with
`synthesize(text, voice) -> float32 mono samples`. `ToneEngine` is the test
double.

## Grounding

`episode.grounding.json` records the method. The check looks for:

- numbers, including `1,200` vs `1200`, `$12`, and `12%` vs `12 percent`
- double-quoted strings of at least 8 characters, and longer single-quoted strings
- a multi-word capitalized name, a capitalized word in the middle of a sentence,
  or an acronym

Host names are allowed even when the document never mentions them. Reactions
such as "Go on" are not facts and are not flagged.

## Tests

```bash
pip install -e ".[kokoro,dev]"
pytest
ruff check src tests
```

52 tests, all passing on this machine. They cover markdown, plain text, PDF
(including a blank page), HTML article extraction, URL ingest with a fake
fetcher, a local repo (README and a function signature in, `node_modules` out),
chunk size and overlap, script schema, the grounding cases above, the fake
read-through, the repair pass with a scripted reply sequence, the OpenAI
request shape, stitching and MP3 chapters, the CLI, and an end-to-end run with
the fake script plus the tone engine. One test synthesizes two Kokoro lines
when the weights are already downloaded, and skips otherwise. Tests do not use
the network.

## Speed on the machine that built 0.1.0

These numbers are from one VM on 13 November 2026. They are not a general
benchmark.

- CPU: 4 vCPU, Intel Xeon, no GPU
- Guest `free` reported 15 GiB of RAM
- Python 3.12.3, ffmpeg 6.1.1, espeak-ng 1.51, kokoro-onnx 0.6.1
- Model: full `kokoro-v1.0.onnx` (311 MB) and `voices-v1.0.bin` (27 MB)
- Command: the sample replay in `samples/demo/episode.mp3`
- Spoken script: 288 words, 12 turns
- Wall clock for the whole command, including model load and MP3 encoding: 15.7 seconds
- Audio duration (`ffprobe`): 104.0 seconds
- Wall clock divided by audio duration: 0.15
- `volumedetect` on the committed MP3: mean -25.3 dB, max -5.4 dB
- Pitch estimate by autocorrelation on the committed MP3, 1–7 s (`af_heart`)
  and 10–16 s (`am_michael`): about 214 Hz and about 122 Hz

The two hosts are different signals, and the file is not silent. That is the
whole quality claim for the sample. Nobody scored it against NotebookLM.

### A live model, same VM

Ollama 0.40.16 was installed for this trial. systemd was not running, so the
server was started with `ollama serve`. It reported CPU only. These runs used
the sample essay, `--length short`, and Kokoro. They are one-offs.

- `qwen2.5:0.5b` did not emit dialogue JSONL. One captured reply was another
  outline, and it added "a single, unmarked skiff on the table", which is not
  in the essay. The CLI exited 1. About 10 seconds.
- `llama3.2:1b` was tried twice. Both runs exited 1 because the outline was
  not valid JSON. About 27 seconds and about 8 seconds.
- `qwen2.5:1.5b` exited 0 in 77.7 seconds, including speech. The MP3 is 93.4
  seconds (mean volume -24.7 dB, max -5.0 dB). The script is 11 lines. One
  repair pass still left a flag: the line "They've been doing this for 25
  years" — the essay says the workshop opened in 1998, not that it has been
  open for 25 years. The same script has Maya ask "what do you teach, Mina?"
  The lexical check does not flag that, because the name Mina is in the essay.
  That is the gap described above, observed here rather than imagined.

The committed sample under `samples/demo/` is the hand-written replay, not
this model output. The 1.5B file was not kept as the demo.

## License

[MIT](LICENSE). Copyright 2026 Kaung Myat Naing.

Kokoro's weights and the kokoro-onnx runtime keep their own licenses. Read
those before you redistribute the model files. This repo does not include them.
