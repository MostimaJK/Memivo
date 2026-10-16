# Memivo v0.3.4 Preview

## Image workspaces

- Share a fit-to-canvas image viewer between segmentation and detection, with cursor-centered wheel zoom, drag pan and Reset view / 0 shortcut. Space or middle-drag allows panning while annotating.
- Keep prompts and detection boxes aligned to original image coordinates, preserve the camera when comparing result views, and keep detection labels readable at fit scale.
- Add Original / Overlay / Binary mask / Transparent cutout segmentation views and Original / Results detection views. Show detection boxes, confidence labels and class counts together.
- Save combined and per-instance binary masks alongside transparent cutouts, crops and overlays in separate result folders. Surface segmentation success, object count, the results path and a desktop Open folder action.
- Export either transparent PNGs or original-size binary masks, and show the exact saved path. Display asynchronous task errors clearly; failed or cancelled runs preserve the last successful result.
- Load full-resolution, EXIF-corrected images in the workspaces. See docs/IMAGE_WORKSPACES.md for controls and storage locations.

## Update

Extract the complete `Memivo-0.3.4-preview-windows-x64.zip`, or update source and run start_memivo.bat. Existing AI engines and model weights can be reused; this update does not require reinstalling GPU engines. External Python 3.10–3.12 (3.12 x64 recommended) and WebView2 are required for the Windows package.

## Validation

54 tests pass; one Windows symlink-permission test is skipped. Tests include binary-mask pixels, combined/per-instance export, original dimensions, EXIF-correct full-resolution serving and previous-result preservation. Frontend build and localization checks pass. Browser interaction tests use synthetic photos and explicit model doubles; real SAM3/YOLO accuracy and target GPU inference are not established by these checks.

Original Memivo code and documentation use GPL-3.0-only. The Windows package includes corresponding project source, LICENSE and NOTICE. Third-party model and library terms apply separately.
