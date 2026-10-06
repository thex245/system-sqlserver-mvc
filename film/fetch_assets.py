"""Download every third-party asset the build needs into build/cache.

Nothing here is committed: fonts (OFL/Apache), the Kokoro TTS model, three.js
example characters, a face detector, and public-domain archival photographs
(historic test images from the DeOldify and "Bringing Old Photos Back to Life"
repositories).
"""
import concurrent.futures as cf
import subprocess
import sys

from config import FONTS, MESHES, MODELS, PHOTOS

GF = "https://raw.githubusercontent.com/google/fonts/main"
FONT_FILES = {
    "VT323-Regular.ttf": f"{GF}/ofl/vt323/VT323-Regular.ttf",
    "SpecialElite-Regular.ttf": f"{GF}/apache/specialelite/SpecialElite-Regular.ttf",
    "CourierPrime-Regular.ttf": f"{GF}/ofl/courierprime/CourierPrime-Regular.ttf",
    "CourierPrime-Bold.ttf": f"{GF}/ofl/courierprime/CourierPrime-Bold.ttf",
    "UnifrakturMaguntia-Book.ttf": f"{GF}/ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf",
    "IBMPlexSansCondensed-Bold.ttf": f"{GF}/ofl/ibmplexsanscondensed/IBMPlexSansCondensed-Bold.ttf",
    "IBMPlexSansCondensed-Medium.ttf": f"{GF}/ofl/ibmplexsanscondensed/IBMPlexSansCondensed-Medium.ttf",
    "IBMPlexSansCondensed-Regular.ttf": f"{GF}/ofl/ibmplexsanscondensed/IBMPlexSansCondensed-Regular.ttf",
    "IBMPlexMono-Regular.ttf": f"{GF}/ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
    "IBMPlexMono-Bold.ttf": f"{GF}/ofl/ibmplexmono/IBMPlexMono-Bold.ttf",
}

KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILES = {
    "kokoro-v1.0.onnx": f"{KOKORO}/kokoro-v1.0.onnx",
    "voices-v1.0.bin": f"{KOKORO}/voices-v1.0.bin",
    "face_detection_yunet_2023mar.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
}

THREE = "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf"
MESH_FILES = {n: f"{THREE}/{n}" for n in ("Xbot.glb", "Michelle.glb", "Soldier.glb")}

# DeOldify removed its historic test photos in 2019; this is the last commit that had them.
DEOLDIFY = ("https://media.githubusercontent.com/media/jantic/DeOldify/"
            "e505432e8033f8c82ba7a850e0cf2f8713e6ed2e/test_images")
DEOLDIFY_PHOTOS = """
1860Girls.jpg 1875Olds.jpg 1908FamilyPhoto.jpg 1920sFamilyPhoto.jpg 1940PAFamily.jpg
Mid1800sSisters.jpg Unidentified1855.jpg PostCivilWarAncestors.jpg
GreatGrandparentsIrelandEarly1900s.jpg FamilyWithDog.jpg ServantsBessboroughHouse1908Ireland.jpg
SchoolKidsConnemaraIreland1901.jpg AustriaHungaryWomen1890s.jpg DutchBabyCoupleEllis.jpg
1890sMedStudents.jpg 1890BostonHospital.jpg poverty.jpg dustbowl_people.jpg HalloweenEarly1900s.jpg
AppalachianLoggers1901.jpg CottonMillWorkers1913.jpg 1888Slum.jpg HomeIreland1924.jpg
ww1_trench.jpg ArmisticeDay1918.jpg WWIHospital.jpg soldier_kids.jpg civil_war_3.jpg Yorktown1862.jpg
kids_pit.jpg 1850SchoolForGirls.jpg Deadwood1860s.jpg OregonTrail1870s.jpg 1870Girl.jpg
IrishLate1800s.jpg FinnishPeasant1867.jpg VictorianLivingRoom.jpg 1897BlindmansBluff.jpg
MementoMori1865.jpg 1946Wedding.jpg 40sCouple.jpg Depression.jpg ManPile.jpg WWIIPeeps.jpg
airmen1943.jpg NorwegianBride1920s.jpg GreatAunt1920.jpg 20sWoman.jpg 1925Girl.jpg
BoxedBedEarly1900s.jpg FarmWomen1895.jpg
""".split()
BOPB = "https://raw.githubusercontent.com/microsoft/Bringing-Old-Photos-Back-to-Life/master/test_images"
BOPB_PHOTOS = {
    "scratch_boy.png": f"{BOPB}/old_w_scratch/b.png",
    "scratch_girl.png": f"{BOPB}/old_w_scratch/c.png",
    "scratch_couple.png": f"{BOPB}/old_w_scratch/d.png",
    "autochrome_garden.png": f"{BOPB}/old/b.png",
    "autochrome_umbrella.png": f"{BOPB}/old/e.png",
    "autochrome_crown.png": f"{BOPB}/old/g.png",
}


def jobs():
    for name, url in FONT_FILES.items():
        yield FONTS / name, url
    for name, url in MODEL_FILES.items():
        yield MODELS / name, url
    for name, url in MESH_FILES.items():
        yield MESHES / name, url
    for name in DEOLDIFY_PHOTOS:
        yield PHOTOS / name, f"{DEOLDIFY}/{name}"
    for name, url in BOPB_PHOTOS.items():
        yield PHOTOS / name, url


def fetch(dest, url):
    if dest.exists() and dest.stat().st_size > 2048:
        return f"cached {dest.name}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    subprocess.run(["curl", "-sSfL", "--retry", "4", "-o", str(tmp), url], check=True)
    if tmp.stat().st_size < 2048 and tmp.read_bytes().startswith(b"version https://git-lfs"):
        raise RuntimeError(f"{url} returned an LFS pointer")
    tmp.rename(dest)
    return f"fetched {dest.name}"


def main():
    failed = 0
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fetch, d, u): d for d, u in jobs()}
        for f in cf.as_completed(futs):
            try:
                print(f.result())
            except Exception as e:  # keep going, report at the end
                failed += 1
                print(f"FAILED {futs[f].name}: {e}", file=sys.stderr)
    if failed:
        sys.exit(f"{failed} downloads failed")


if __name__ == "__main__":
    main()
