"""Final master: picture + mix -> MP4.

  output/TAPE_BC_do_you_still_love_me.mp4   1920x1080 @ 60 fps (4:3 picture, pillarboxed), H.264
  build/video/master_hq.mp4                 same picture at high quality (not committed)

The picture is built at 720x540 (the detail a VHS tape actually carries) and
upscaled with Lanczos to 1440x1080, centred in a 1920x1080 frame.
"""
import subprocess
import sys

import soundfile as sf

from config import AUDIO, BUILD, FPS, OUTPUT

PIC = BUILD / "video" / "picture.mkv"
MIX = AUDIO / "mix.wav"
OUT = OUTPUT / "TAPE_BC_do_you_still_love_me.mp4"
HQ = BUILD / "video" / "master_hq.mp4"
VF = "scale=1440:1080:flags=lanczos,pad=1920:1080:240:0:black,setsar=1"
META = ["-metadata", "title=DO YOU STILL LOVE ME? (TAPE B.C.)", "-metadata", "comment=Analog horror short. "
        "Made programmatically: Blender, Kokoro TTS, numpy/OpenCV, ffmpeg."]


def run(cmd):
    print(" ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def main(budget_mb=95.0):
    dur = sf.info(str(MIX)).duration
    audio_kbps = 160
    total_kbit = budget_mb * 8 * 1024
    video_kbps = int(total_kbit / dur - audio_kbps - 40)
    common = ["-i", str(PIC), "-i", str(MIX), "-map", "0:v", "-map", "1:a", "-vf", VF, "-c:v", "libx264",
              "-preset", "slow", "-tune", "grain", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    log = BUILD / "video" / "x264pass"
    run(["ffmpeg", "-y", "-loglevel", "error"] + common + ["-b:v", f"{video_kbps}k", "-pass", "1",
        "-passlogfile", str(log), "-an", "-f", "mp4", "/dev/null"])
    run(["ffmpeg", "-y", "-loglevel", "error"] + common + ["-b:v", f"{video_kbps}k", "-pass", "2",
        "-passlogfile", str(log), "-c:a", "aac", "-b:a", f"{audio_kbps}k", "-movflags", "+faststart"] + META +
        ["-shortest", str(OUT)])
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB  (video {video_kbps} kb/s)")
    if "--hq" in sys.argv:
        run(["ffmpeg", "-y", "-loglevel", "error"] + common + ["-crf", "16", "-c:a", "aac", "-b:a", "256k",
            "-movflags", "+faststart"] + META + ["-shortest", str(HQ)])
        print("wrote", HQ, f"{HQ.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
