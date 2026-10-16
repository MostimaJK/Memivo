# Memivo v0.3.1 Preview

Memivo — Organize memories, together.

从共同的旅程，整理出属于每个人的回忆。

## Included

- Spectrum 2 desktop workspace with 简体中文 / 繁體中文 / English.
- Local photo library, people albums, SAM3 cutouts, and YOLO object counting.
- Box/polygon annotation, reviewed datasets, scene-group splits, and fixed YOLO dataset versions.
- Detection/segmentation training, checkpoint resume, independent test evaluation, and model export/application.
- Optional engine installation and a local model library with official variants and verified YOLO downloads.
- Windows EXE launcher with external dependencies and a prebuilt frontend.

## Download

Use `Memivo-0.3.1-preview-windows-x64.zip` from this release. Extract the whole ZIP and run `Memivo.exe`. Requires external Python 3.12 x64 and WebView2 on Windows 10/11. First launch downloads UI dependencies. AI engines and weights are installed separately; Node.js is not needed by the EXE package.

## Validation

49 tests pass; one symlink test is skipped because Windows permissions do not allow creating symlinks. TypeScript/build, localization, CPU training/evaluation/resume, official YOLO11n/YOLO26n download and CPU inference, and EXE self-check have been exercised. Synthetic training data verifies the workflow only. GPU and real SAM3/face-model validation remain device-dependent work.

This is a prerelease with external dependencies, not a standalone or offline installer. Original Memivo code and documentation use GPL-3.0-only. LICENSE, NOTICE and corresponding project source with rebuild instructions are included in the Windows ZIP. Upstream notices and model terms apply separately.
