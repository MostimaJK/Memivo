# Memivo v0.3.3 Preview

Memivo — Organize memories, together.

## NVIDIA driver detection fix

- Recognize both `CUDA Version` and the newer `CUDA UMD Version` header emitted by NVIDIA-SMI 617.42.
- Fix RTX 5070 Ti / compute capability 12.0 / CUDA UMD 13.4 being incorrectly classified as CPU-only.
- Display the detected driver CUDA limit and parsing diagnostics in Feature center; failed NVIDIA-SMI commands do not approve a GPU profile.
- Regression tests cover legacy and UMD headers, optional spaces, old driver capability, missing versions and failed queries. The reported RTX 5070 Ti case now recommends cu128; target GPU inference remains unverified locally.

## GPU face recognition

- Add Auto / CPU / NVIDIA CUDA 12.8 installation profiles for the face recognition engine.
- Install ONNX Runtime GPU and matching CUDA/cuDNN libraries in the managed environment; no separate PyTorch or full system CUDA Toolkit required for face recognition.
- Validate an actual ONNX convolution and CUDA node placement before marking the GPU engine ready. Installation or validation failure remains visible in diagnostics.
- Allow managed face recognition tasks to run on NVIDIA CUDA; reject an incompatible CPU-only engine with a clear upgrade instruction.
- Keep independent profile selection for the vision and face engines, with Simplified Chinese, Traditional Chinese and English guidance.

## Update and use

Download `Memivo-0.3.3-preview-windows-x64.zip` and extract the entire folder. Requires external Python 3.10–3.12 (3.12 x64 recommended), WebView2 and Windows 10/11. AI engines and weights are installed separately.

In Feature center, detect hardware, uninstall an existing CPU face engine if necessary, select Auto or NVIDIA CUDA 12.8, and install. Wait for verification to succeed. Then select NVIDIA CUDA as the execution device in Settings and save. Model weights and photo data are retained when uninstalling an engine. See docs/OPTIONAL_ENGINES.md for the full workflow.

## Validation limits

54 tests pass; one Windows symlink-permission test is skipped. Automated runtime lifecycle, installation recipe, failure handling, task device forwarding and application regression tests are exercised. ONNX execution checking is tested on CPU; RTX 5070 Ti installation and real face-model inference require testing on the target computer. A passed installation check does not replace a real-model test. InsightFace 0.7.3 may require Microsoft C++ Build Tools on Windows.

This is a prerelease with external dependencies, not a standalone or offline installer. Original Memivo code and documentation use GPL-3.0-only. LICENSE, NOTICE and corresponding project source with rebuild instructions are included. Upstream notices and model terms apply separately.
