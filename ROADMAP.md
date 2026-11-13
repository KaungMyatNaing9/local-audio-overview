# Roadmap

0.1.0 is a local command: ingest a source, write a two-host script, check a
few kinds of unsupported facts, and render an English MP3 with Kokoro. The
items below are not started.

## A generated conversation that stays honest

The fake backend either reads the source in order or speaks a script you
supply. The OpenAI-compatible client is implemented and unit-tested, and it
was not run against a live model while building 0.1.0. The next quality pass
is to run real local models, keep the prompts that survive the grounding
check, and record the failures (bad JSON, invented numbers, endless repair)
instead of guessing.

A later grounding check can use a small entailment model for paraphrases.
The lexical check should stay, because it is deterministic and it does not
invent a verdict of its own.

## Web UI

A single page: drop a file or paste a URL, pick length, tone, and two voices,
then play the MP3 with the transcript beside it. The chapter JSON is already
the shape a player needs. No accounts.

## More voices and languages

The Kokoro voice file already has British English and several other languages.
kokoro-onnx 0.6.1 phonemizes `en-us` and `en-gb` only, so 0.1.0 refuses the
other voices rather than guessing phonemes. A later release can add a G2P
that those voices were trained with, and tests that do not treat English
pitch as a stand-in for every language.

Other engines, including Piper, fit behind `synthesize(text, voice)`. Each
engine's license has to be compatible with how you ship it. Piper's current
Python package is GPL-3.0, so it stays optional if it is added.

## Interrupt and ask

Pause after a section, take a typed question, and answer from the source
only, then resume. The grounding check should run on that answer too. This
is the interactive mode people expect from a hosted notebook, and it needs
a live model plus a way to stop the audio.

## Sources that 0.1.0 refuses

- OCR for scanned PDFs
- Slides and spreadsheets
- A page that is mostly navigation, where trafilatura returns nothing useful

## Playback

- Stream turns while later ones are still synthesizing
- Batch a folder of documents
- Write an RSS item for the episode

None of these are required to make one MP3, which is why they are not in 0.1.0.
