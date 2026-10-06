"""Final masters: picture + mix -> MP4, both 4:3 (the format of the tape).

  output/TAPE_BC_do_you_still_love_me_1080p60.mp4   1440x1080 @ 60 fps, high quality H.264
  output/TAPE_BC_do_you_still_love_me_preview.mp4   compact viewing copy, two-pass sized to a budget

The picture is built at 720x540 (the detail a VHS tape actually carries) and
upscaled with Lanczos for the 1080p master.
"""
import subprocess
import sys

import soundfile as sf

from config import AUDIO, BUILD, FPS, OUTPUT

PIC = BUILD / "video" / "picture.mkv"
MIX = AUDIO / "mix.wav"
MASTER = OUTPUT / "TAPE_BC_do_you_still_love_me_1080p60.mp4"
PREVIEW = OUTPUT / "TAPE_BC_do_you_still_love_me_preview.mp4"
META = ["-metadata", "title=DO YOU STILL LOVE ME? (TAPE B.C.)", "-metadata", "comment=Analog horror short. "
        "Made programmatically: Blender, Kokoro TTS, numpy/OpenCV, ffmpeg."]


def run(cmd):
    print(" ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def master(crf=18):
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(PIC), "-i", str(MIX), "-map", "0:v", "-map", "1:a",
         "-vf", "scale=1440:1080:flags=lanczos,setsar=1", "-c:v", "libx264", "-preset", "slow", "-tune", "grain",
         "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "256k",
         "-movflags", "+faststart"] + META + ["-shortest", str(MASTER)])
    print("wrote", MASTER, f"{MASTER.stat().st_size / 1e6:.1f} MB")


def preview(budget_mb=49.0, size=(720, 540), fps=FPS, audio_kbps=96, denoise="hqdn3d=1.2:1.2:4:4"):
    """Two-pass encode that lands under `budget_mb` (MB = 10^6 bytes)."""
    dur = sf.info(str(MIX)).duration
    video_kbps = int(budget_mb * 8000 / dur - audio_kbps - 12)
    vf = f"{denoise + ',' if denoise else ''}scale={size[0]}:{size[1]}:flags=lanczos,setsar=1"
    common = ["-i", str(PIC), "-i", str(MIX), "-map", "0:v", "-map", "1:a", "-vf", vf, "-c:v", "libx264",
              "-preset", "veryslow", "-tune", "grain", "-pix_fmt", "yuv420p", "-r", str(fps), "-b:v", f"{video_kbps}k",
              "-maxrate", f"{int(video_kbps * 1.8)}k", "-bufsize", f"{int(video_kbps * 4)}k"]
    log = BUILD / "video" / "x264pass"
    run(["ffmpeg", "-y", "-loglevel", "error"] + common + ["-pass", "1", "-passlogfile", str(log), "-an", "-f", "mp4",
        "/dev/null"])
    run(["ffmpeg", "-y", "-loglevel", "error"] + common + ["-pass", "2", "-passlogfile", str(log), "-c:a", "aac",
        "-b:a", f"{audio_kbps}k", "-movflags", "+faststart"] + META + ["-shortest", str(PREVIEW)])
    mb = PREVIEW.stat().st_size / 1e6
    print("wrote", PREVIEW, f"{mb:.1f} MB  (video {video_kbps} kb/s)")
    assert mb < 49.9, "preview over budget"


if __name__ == "__main__":
    if "--preview-only" not in sys.argv:
        master()
    preview()
