# DO YOU STILL LOVE ME? — TAPE B.C.

An analog horror short film, made entirely in code.

> *"This material was produced for the instruction of personnel involved in the identification,
> containment, and interaction with organisms classified as PASIÓN."*

A restricted government training tape about **Pasión** — organisms that imitate, adapt, and
attach themselves to people. Ten slides, cave walls 40,000 years old, family photographs with
one face always missing, a containment cell in 1986, an incident in 1997, and a final instruction
the narrator cannot finish in its own voice.

**▶ The film** (≈6 min, English, 4:3 at 60 fps):

| File | Resolution | Size |
|---|---|---|
| [`output/TAPE_BC_do_you_still_love_me_1080p60.mp4`](output/TAPE_BC_do_you_still_love_me_1080p60.mp4) | 1440×1080 | 95 MB |
| [`output/TAPE_BC_do_you_still_love_me_preview.mp4`](output/TAPE_BC_do_you_still_love_me_preview.mp4) | 720×540 (native) | 49 MB |
| [`output/TAPE_BC_do_you_still_love_me_mobile.mp4`](output/TAPE_BC_do_you_still_love_me_mobile.mp4) | 640×480 | 30 MB |

**Script:** [`script/SCRIPT_EN.md`](script/SCRIPT_EN.md)

## How it was made

Nothing was filmed, drawn by hand, or recorded. Every frame and every sound comes out of the
scripts in [`film/`](film/).

| Layer | How |
|---|---|
| Narrator | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) neural TTS, re-synthesized through the WORLD vocoder with the pitch pinned to a single note — clear words, no human intonation. In slide 10 the same voice gets its natural pitch back. |
| 3D footage & photographs | Blender 5.2 (Cycles, CPU) driven by Python: the CCTV of specimen P-04, the Incident 12 security camera, the night forest flash photo, the corridors, the hallway. The specimen is a stretched, faceless mannequin rig whose grin is a ray-cast, shape-keyed mesh on its blank face. Characters are three.js example models; poses use a small joint-aiming / two-bone IK system ([`film/blender/rig.py`](film/blender/rig.py)). |
| Cave paintings & manuscript | Procedural: fractal rock relief with torch lighting, warped ochre / charcoal / kaolin pigments, a gold-ground illumination with a scratched-out face ([`film/paintings.py`](film/paintings.py)). |
| Archival photographs | Public-domain historic photos (1838–1950s) from the test sets of DeOldify and *Bringing Old Photos Back to Life*; faces found with OpenCV YuNet and redacted. |
| The tape | A YIQ composite-video simulation: limited luma bandwidth with edge ringing, smeared and delayed chroma, line jitter, head-switching noise, tracking errors, dropouts, static ([`film/vhs.py`](film/vhs.py)). |
| Sound | Fully synthesized: tape hiss, mains hum, drone, fluorescent room tone, VCR mechanics, projector clicks, teletype, glitches; per-line voice treatments; a VHS linear-track master ([`film/sound.py`](film/sound.py)). |
| Edit | [`film/edit.py`](film/edit.py) — one timeline drives both picture and sound; cuts follow the measured length of each spoken line. |

Voice intelligibility was checked objectively with an offline Whisper model on the final mix.

## Rebuild

```sh
./build.sh
```

Requires Python 3.13, ffmpeg and network access for the first run (≈2 GB of models and assets
are downloaded into `build/`, which is not committed). Rendering takes a few hours on 4 CPU cores.

## Credits & licenses

- Fonts: IBM Plex (OFL), VT323 (OFL), Courier Prime (OFL), Special Elite (Apache 2.0), UnifrakturMaguntia (OFL) — via google/fonts.
- TTS: Kokoro-82M (Apache 2.0) through kokoro-onnx.
- Character models: three.js examples (Xbot, Soldier).
- Historic photographs: public-domain images distributed with jantic/DeOldify and microsoft/Bringing-Old-Photos-Back-to-Life.
- Everything else (code, sound, procedural imagery): this repository.

---

### Resumo (PT-BR)

Curta de *analog horror* “Você ainda me ama?” (FITA B.C.), localizado em inglês e produzido
100% por código: narração TTS robotizada por vocoder, cenas 3D em Blender, pinturas rupestres
procedurais, fotos históricas de domínio público com rostos censurados, simulação de VHS e trilha
sonora sintetizada. O vídeo final está em `output/`; o roteiro em inglês, em `script/SCRIPT_EN.md`.
