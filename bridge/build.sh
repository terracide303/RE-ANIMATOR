#!/bin/sh
# Builds RE-ANIMATOR's MK1 bridge (our version of mk1-bridge from MK1 Revive by andy83, see ORIGIN.md).
#   ./bridge/build.sh   ->  bridge/build/mk1-bridge   (arm64, macOS 12+; only the command line tools are needed)
set -eu
cd "$(dirname "$0")"
mkdir -p build
clang -std=gnu17 -O2 -arch arm64 -mmacosx-version-min=12.0 \
    -include IOKit/IOCFPlugIn.h -Wno-deprecated-declarations \
    -Imk1-ipc -Imk1-usb \
    -o build/mk1-bridge \
    mk1-bridge/main.c mk1-bridge/mk1_server.c mk1-usb/mk1_device.c mk1-ipc/mk1_ipc.c \
    -framework CoreFoundation -framework IOKit -framework CoreMIDI
codesign -f -s - build/mk1-bridge 2>/dev/null
echo "built: $(pwd)/build/mk1-bridge"
