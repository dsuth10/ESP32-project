"""Child-process Whisper so a native CUDA abort cannot kill the companion GUI."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe a WAV file with faster-whisper.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--compute-type", required=True)
    parser.add_argument("--wav", required=True)
    args = parser.parse_args(argv)

    import faster_whisper

    model = faster_whisper.WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
    )
    segments, _ = model.transcribe(
        args.wav,
        beam_size=3,
        language="en",
        task="transcribe",
        temperature=0.0,
    )
    text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
