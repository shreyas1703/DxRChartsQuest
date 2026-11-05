#!/usr/bin/env bash
# Runs the real DxR port code (Parser → Mark.Infer → scales → marks → axes → legend) outside Unity
# against a small functional UnityEngine shim, dumps the geometry, and renders preview PNGs.
# Needs: mono (mcs + mono), python3 + matplotlib.   macOS: brew install mono ; pip3 install matplotlib
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PKG="$ROOT/UnityPackage/com.vlm.dxrcharts"
OUT="${1:-$HERE/out}"
mkdir -p "$OUT/build"
mcs -target:library -nowarn:67,169,649,414,660,661,618 -out:"$OUT/build/HUnity.dll" "$HERE/HeadlessUnity.cs"
mcs -target:library -nowarn:649,414,168,219 -r:"$OUT/build/HUnity.dll" -d:ENABLE_LEGACY_INPUT_MANAGER \
    -out:"$OUT/build/DxRCharts.dll" $(find "$PKG/Runtime" -name '*.cs')
mcs -nowarn:649 -r:"$OUT/build/HUnity.dll" -r:"$OUT/build/DxRCharts.dll" -out:"$OUT/build/harness.exe" "$HERE/Harness.cs"
MONO_PATH="$OUT/build" mono "$OUT/build/harness.exe" "$PKG/Charts~" "$PKG/Runtime/Resources" "$OUT/dump"
python3 "$ROOT/tests/verify_dumps.py" "$OUT/dump"                                       # every mark vs ground truth
mcs -r:"$OUT/build/HUnity.dll" -r:"$OUT/build/DxRCharts.dll" -out:"$OUT/build/room.exe" "$HERE/RoomDump.cs"
MONO_PATH="$OUT/build" mono "$OUT/build/room.exe" "$OUT/room.json"
python3 "$ROOT/tests/render_preview.py" "$OUT/dump" "$OUT/preview"                          # Dark backdrop
python3 "$ROOT/tests/render_preview.py" "$OUT/dump" "$OUT/preview_room" --room "$OUT/room.json"  # Grid room backdrop
echo "Previews: $OUT/preview and $OUT/preview_room"
