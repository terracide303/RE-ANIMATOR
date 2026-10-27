#!/bin/sh
# Builds RE-ANIMATOR.app (Apple Silicon) and the release zip.
#
#   ./build.sh            -> dist/RE-ANIMATOR.app and dist/RE-ANIMATOR-<version>-arm64.zip
#
# Needs: macOS on Apple Silicon, python3 from python.org (with Tk), Homebrew's libusb (brew install libusb).
# Everything else (PyInstaller, Pillow) goes into a private virtual environment in .build/.
set -eu
cd "$(dirname "$0")"
ROOT=$(pwd)
SRC="$ROOT/reanimator"
B="$ROOT/.build"
VERSION=$(sed -n "s/^VERSION = '\(.*\)'/\1/p" "$SRC/reanimator_app.py" | tr ' ' '-')
LIBUSB=$(ls /opt/homebrew/lib/libusb-1.0.0.dylib 2>/dev/null || true)
BRIDGE="$SRC/vendor/MK1 Revive.app/Contents/MacOS/mk1-bridge"
[ -n "$LIBUSB" ] || { echo "libusb not found: brew install libusb"; exit 1; }
[ -f "$BRIDGE" ] || { echo "bridge not found: $BRIDGE"; exit 1; }

mkdir -p "$B"
[ -x "$B/venv/bin/python" ] || python3 -m venv "$B/venv"
"$B/venv/bin/pip" install -q --upgrade pip pyinstaller pillow

# app icon from the cover
rm -rf "$B/RE-ANIMATOR.iconset"; mkdir -p "$B/RE-ANIMATOR.iconset"
for s in 16 32 128 256 512; do
    sips -z $s $s "$ROOT/design/reanimator-cover.png" --out "$B/RE-ANIMATOR.iconset/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    sips -z $d $d "$ROOT/design/reanimator-cover.png" --out "$B/RE-ANIMATOR.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$B/RE-ANIMATOR.iconset" -o "$B/RE-ANIMATOR.icns"

# licences that travel with the app
rm -rf "$B/licenses"; mkdir -p "$B/licenses"
cp "$ROOT/docs/licenses/"*.md "$B/licenses/"
cp "$(dirname "$(readlink -f "$LIBUSB")")/../COPYING" "$B/licenses/libusb-COPYING-LGPL-2.1.txt"

rm -rf "$B/work" "$ROOT/dist/RE-ANIMATOR.app"
"$B/venv/bin/python" -m PyInstaller --noconfirm --windowed --name RE-ANIMATOR \
    --icon "$B/RE-ANIMATOR.icns" --osx-bundle-identifier com.reanimator.mk1 --target-arch arm64 \
    --workpath "$B/work" --distpath "$ROOT/dist" --specpath "$B" \
    --add-data "$SRC/assets:assets" --add-data "$B/licenses:licenses" \
    --add-binary "$LIBUSB:." --paths "$SRC" \
    --hidden-import bridge --hidden-import mk1usb --hidden-import patch_maschine3_macos \
    "$SRC/reanimator_app.py"

# The bridge goes in after packaging (PyInstaller would re-sign it): OUR build from bridge/ (MK1 Revive by andy83,
# changed, see bridge/ORIGIN.md); andy83's released binary in reanimator/vendor/ only if ours cannot be built.
APP="$ROOT/dist/RE-ANIMATOR.app"
mkdir -p "$APP/Contents/Resources/vendor"
if "$ROOT/bridge/build.sh"; then
    cp "$ROOT/bridge/build/mk1-bridge" "$APP/Contents/Resources/vendor/mk1-bridge"
    [ -f "$ROOT/bridge/build/reanimator.anim" ] && cp "$ROOT/bridge/build/reanimator.anim" "$APP/Contents/Resources/vendor/"
else
    echo "our bridge did not build: using andy83's released binary"
    cp "$BRIDGE" "$APP/Contents/Resources/vendor/mk1-bridge"
fi
codesign -f -s - "$APP"
codesign --verify --deep --strict "$APP"

ZIP="$ROOT/dist/RE-ANIMATOR-$VERSION-arm64.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
echo "built: $APP"
echo "zip:   $ZIP"
