"""PlatformIO post-script: guard upload actions before any are executed."""
import hashlib
import json
import os
from pathlib import Path
import sys

Import("env")
from SCons.Script import COMMAND_LINE_TARGETS

project = Path(env.subst("$PROJECT_DIR")).resolve()
root = next((p for p in [project, *project.parents] if (p / "tools/board_safety.py").is_file()), None)
require_root = root is not None
if not require_root:
    raise RuntimeError("Cannot locate project board guard.")
sys.path.insert(0, str(root / "tools"))
from board_safety import PROFILES, SafetyError, require, load_manifest

name = env["PIOENV"]
selected = [key for key, p in PROFILES.items() if name in p["environments"]]
require(len(selected) == 1, "No approved physical board profile for this environment.")
profile = selected[0]
require(env.GetProjectOption("upload_protocol") == "custom", "Only the guarded custom uploader is supported.")
require(not set(COMMAND_LINE_TARGETS) & {"erase", "uploadfs", "uploadfsota", "program", "bootloader"},
        "Erase, filesystem, OTA and standalone bootloader uploads are disabled by board safety.")
require(env.BoardConfig().get("build.mcu") == ("esp32s3" if profile == "es3c28p-s3" else "esp32"), "Build processor/profile mismatch.")
require(env.BoardConfig().get("upload.flash_size") == ("16MB" if profile == "es3c28p-s3" else "4MB"), "Build flash/profile mismatch.")
require(Path(env.subst("$PROJECT_SRC_DIR")).resolve() ==
        (root / "src" if profile == "es3c28p-s3" else root / "tools/board_diagnostics/cyd_identifier/src"), "Unapproved source directory.")
manifest = Path(env.subst("$BUILD_DIR")) / "board-upload.json"
binary_target = str(Path(env.subst("$BUILD_DIR")) / "firmware.bin")
build_inputs = [project / "platformio.ini", root / "tools/pio_board_guard.py", root / "tools/board_safety.py"]
if profile == "es3c28p-s3":
    build_inputs.append(root / "partitions.csv")
# Regenerate both the binary action and its manifest after safety/build settings
# change, including when the compiler/linker can reuse their cached outputs.
env.Depends(binary_target, [env.File(str(p)) for p in build_inputs])
# Always recreate
# the upload binary from the selected ELF, then stamp it. Compilation stays cached.
env.AlwaysBuild(binary_target)


def record_build(source, target, env):
    directory = Path(env.subst("$BUILD_DIR")).resolve()
    pairs = [("application", 0x10000, directory / "firmware.bin")]
    if profile == "es3c28p-s3":
        pairs += [("bootloader", 0, directory / "bootloader.bin"),
                  ("partitions", 0x8000, directory / "partitions.bin"),
                  ("ota_boot", 0xe000, Path(env.PioPlatform().get_package_dir("framework-arduinoespressif32")) / "tools/partitions/boot_app0.bin")]
    images = []
    for role, offset, path in pairs:
        data = path.read_bytes()
        images.append({"role": role, "offset": offset, "path": os.path.relpath(path, directory),
                       "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    payload = {"schema": 1, "profile": profile, "environment": name, "images": images,
               "inputs": [{"path": os.path.relpath(p, directory), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in build_inputs]}
    manifest.write_text(json.dumps(payload, indent=2)+"\n", encoding="utf-8")
    load_manifest(manifest, profile)
    print("Recorded board-bound firmware manifest:", profile)


env.AddPostAction(binary_target, record_build)
# The custom protocol skips PlatformIO's automatic port detection. Missing ports
# are rejected by argparse/the guard before serial is opened.
env.Replace(UPLOADCMD='"$PYTHONEXE" "' + str(root / "tools/board_safety.py") +
            '" upload --profile ' + profile + ' --port "$UPLOAD_PORT" --manifest "' + str(manifest) + '"')
