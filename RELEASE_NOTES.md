# Memivo v0.3.5 Preview

## Engine mismatch and diagnostic fixes

- Reject CUDA jobs before spawning when the managed engine is CPU-only, including detection, segmentation, training and face jobs. Show mismatched device settings in Feature center.
- Preserve subprocess traceback details and exit codes instead of only reporting a generic engine failure. Write full output under the application data directory's runtimes/logs and retain the latest failure across restarts.
- Display failure details directly in detection and segmentation workspaces, with engine-configuration and log-folder actions. Failed tasks use a red footer indicator.
- Add Copy log and Select all actions with selectable read-only text. Enable text selection in the native desktop host; image dragging remains separate. Clipboard fallback selects the text and prompts Ctrl+C.

## Fixing torch +cpu / Invalid CUDA device errors

An existing CPU engine does not become GPU-enabled after updating the app. Uninstall the visual AI engine in Feature center, select NVIDIA CUDA 12.8, and install. Wait for GPU verification, then select NVIDIA CUDA in Settings. Model weights are retained. Alternatively choose CPU in Settings to test the workflow with the current CPU engine.

## Validation

57 tests pass, one Windows symlink-permission test is skipped. A real official YOLO26n model was run through the managed-worker path on the existing CPU environment; it returned four objects on a local photo. The CPU/CUDA exception was reproduced with a deliberately mismatched test record to verify complete error capture. Target RTX 5070 Ti inference remains to be tested. Build, localization and diagnostic copy interaction are checked separately.

Extract the complete Memivo-0.3.5-preview-windows-x64.zip, or update source and run start_memivo.bat. Requires external Python 3.10–3.12 and WebView2. GPL-3.0-only applies to original code; corresponding source, LICENSE and NOTICE are included. Third-party terms apply separately.
