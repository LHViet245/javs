#!/bin/bash
TARGET_DIR="tests/movie"
mkdir -p "$TARGET_DIR"

# 1. Normal case
touch "$TARGET_DIR/UZU-036.mp4"

# 2. Prefixes and suffixes
touch "$TARGET_DIR/[Thz.la] UZU-018 HD.mp4"

# 3. Subfolder, subtitle suffix (-C), and subtitle file
mkdir -p "$TARGET_DIR/Subbed/SDDE-764"
touch "$TARGET_DIR/Subbed/SDDE-764/SDDE-764-C.mp4"
touch "$TARGET_DIR/Subbed/SDDE-764/SDDE-764-C.srt"

# 4. Mixed Japanese text, resolution, random text
touch "$TARGET_DIR/Random Text 123 SDDE-567 最高のビデオ フルHD.mkv"

# 5. Deeply nested
mkdir -p "$TARGET_DIR/Deeply/Nested/Folder"
touch "$TARGET_DIR/Deeply/Nested/Folder/SRMC-050.avi"

# 6. Split files (cd1, cd2)
touch "$TARGET_DIR/START-539 cd1.mp4"
touch "$TARGET_DIR/START-539 cd2.mp4"

# 7. Uncensored tag
touch "$TARGET_DIR/RCTD-717_uncensored.mp4"

# 8. Directory has the ID, file has a generic name (e.g. video.mp4, 1.mp4)
mkdir -p "$TARGET_DIR/SGKI-079"
touch "$TARGET_DIR/SGKI-079/video.mp4"

# 9. Parentheses, resolution tags
touch "$TARGET_DIR/RCT-972 (1080p).mkv"

# 10. Split files with A/B suffix
mkdir -p "$TARGET_DIR/DVMM-377"
touch "$TARGET_DIR/DVMM-377/DVMM-377A.mp4"
touch "$TARGET_DIR/DVMM-377/DVMM-377B.mp4"

echo "Dummy files created in $TARGET_DIR"
