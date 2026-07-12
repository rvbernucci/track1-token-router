#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1280
HEIGHT = 720
DURATION = 76
FPS = 15
FONT = Path("/System/Library/Fonts/Menlo.ttc")


SCENES = (
    (0, 8, "PROOFROUTE", "ACCURACY FIRST. TOKENS LAST.", ("BOOTING TOKEN ECONOMY...", "AMD ACT II // TRACK 1", "SYSTEM STATUS: READY")),
    (8, 18, "THE PROBLEM", "EVERY QUERY PAYS THE FULL PRICE.", ("SIMPLE TASK? EXPENSIVE MODEL.", "HARD TASK? EXPENSIVE MODEL.", "SAME COST. NO JUDGMENT.", "TOKENS DISAPPEAR AT SCALE.")),
    (18, 29, "THE IDEA", "TURN COMPUTE INTO A DECISION.", ("PROVE WHAT CAN BE PROVED.", "USE LOCAL INTELLIGENCE WHERE IT WINS.", "BUY REMOTE INTELLIGENCE ONLY WHEN NEEDED.", "NEVER TRADE ACCURACY FOR A CHEAP GUESS.")),
    (29, 42, "ONE ROUTER", "EIGHT WORLDS. ONE ECONOMY.", ("FACTUAL QA       MATH REASONING", "SENTIMENT        SUMMARIZATION", "NER              CODE DEBUGGING", "LOGIC PUZZLES    CODE GENERATION", "UNSEEN TASK -> BEST SUFFICIENT ENGINE")),
    (42, 53, "TRUST, THEN ROUTE", "LOCAL ANSWERS MUST PROVE THEMSELVES.", ("UNIQUE PROOF -> ZERO FIREWORKS TOKENS", "AMBIGUOUS RESULT -> REFUSE", "NO PROOF -> ALLOWED FIREWORKS MODEL", "2/2 CORRECT RECOVERED // 5/5 ERRORS REJECTED")),
    (53, 64, "LEARN THE FRONTIER", "GEMMA FINDS WHERE LOCAL CAN WIN.", ("FUNCTIONGEMMA 270M -> INTENT + 5 SIGNALS", "GEMMA 4 E2B -> 2,183 / 4,400 CORRECT", "WILSON + NASH -> PROTECTED LOCAL COHORT", "95.95% PRECISION // 8.41% COVERAGE")),
    (64, 76, "THE OUTCOME", "MORE ANSWERS PER TOKEN. ACCURACY PROTECTED.", ("2.67 GB PUBLIC LINUX/AMD64 IMAGE", "4 GB // 2 VCPU // 2 SECOND RESOURCE GATE", "712 TESTS // ZERO EMBEDDED SECRETS", "OFFICIAL CONTROL: 84.2% // 4,198 TOKENS")),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the retro CLI ProofRoute presentation video.")
    parser.add_argument("--output", type=Path, default=Path("submission/final/proofroute-retro-cli.mp4"))
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    font = FONT if FONT.exists() else Path("/System/Library/Fonts/SFNSMono.ttf")

    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", _audio_source(),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame_index in range(DURATION * FPS):
            process.stdin.write(_render_frame(frame_index / FPS, font).tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise SystemExit("ffmpeg failed while encoding the presentation")
    print(output)
    return 0


def _render_frame(time_s: float, font_path: Path) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), (4, 8, 6))
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 64):
        draw.line((x, 0, x, HEIGHT), fill=(9, 28, 19), width=1)
    for y in range(0, HEIGHT, 64):
        draw.line((0, y, WIDTH, y), fill=(9, 28, 19), width=1)
    draw.rounded_rectangle((34, 30, 1246, 690), radius=8, fill=(6, 15, 10), outline=(241, 90, 36), width=2)
    draw.line((58, 82, 1222, 82), fill=(49, 87, 66), width=2)
    small = ImageFont.truetype(str(font_path), 17)
    tiny = ImageFont.truetype(str(font_path), 14)
    draw.text((58, 48), "PROOFROUTE // ROUTER.OS 3.8.2", font=small, fill=(255, 120, 64))
    draw.text((934, 48), "AMD ACT II   [ ONLINE ]", font=small, fill=(141, 255, 179))
    scene = next(item for item in SCENES if item[0] <= time_s < item[1])
    start, end, title, subtitle, lines = scene
    elapsed = time_s - start
    title_font = ImageFont.truetype(str(font_path), 50)
    subtitle_font = ImageFont.truetype(str(font_path), 22)
    body_font = ImageFont.truetype(str(font_path), 23)
    draw.text((62, 115), title, font=title_font, fill=(244, 241, 223), stroke_width=1, stroke_fill=(30, 38, 31))
    draw.text((64, 184), subtitle, font=subtitle_font, fill=(255, 106, 43))
    y = 264
    for index, line in enumerate(lines):
        reveal_start = 1.0 + index * 0.68
        if elapsed < reveal_start:
            break
        visible = min(len(line), int((elapsed - reveal_start) * 42))
        rendered = line[:visible]
        prefix = "> " if start not in {0, 64} else ""
        color = (159, 255, 195) if index == len(lines) - 1 else (197, 216, 202)
        draw.text((82, y), prefix + rendered, font=body_font, fill=color)
        y += 55
    draw.rectangle((72, 632, 72 + int(1080 * time_s / DURATION), 637), fill=(255, 90, 32))
    draw.text((830, 646), "ESC TO ABORT // ENTER TO ROUTE", font=tiny, fill=(100, 138, 115))
    if time_s % 1 < 0.55:
        draw.rectangle((82, 580, 94, 600), fill=(159, 255, 195))
    for y_scan in range(0, HEIGHT, 4):
        draw.line((0, y_scan, WIDTH, y_scan), fill=(0, 0, 0), width=1)
    fade = min(1.0, time_s / 0.8, (DURATION - time_s) / 1.0)
    if fade < 1:
        image = Image.blend(Image.new("RGB", image.size, "black"), image, max(0.0, fade))
    return image


def _audio_source() -> str:
    # Low-volume square-like chiptune bed with a changing harmonic pulse.
    expression = (
        "0.025*sin(2*PI*t*(110+55*between(mod(t,8),2,4)+110*between(mod(t,8),6,8)))"
        "+0.012*sin(2*PI*t*220)*between(mod(t,1),0,0.12)"
    )
    return f"aevalsrc='{expression}':s=48000:d={DURATION},highpass=f=70,lowpass=f=1800,afade=t=in:d=1,afade=t=out:st={DURATION-2}:d=2"


if __name__ == "__main__":
    raise SystemExit(main())
