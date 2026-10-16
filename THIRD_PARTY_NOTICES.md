# Third-party information

Memivo original code and documentation are licensed under GPL-3.0-only; see LICENSE and NOTICE. This document does not relicense upstream code, fonts, or weights.

- Frontend package versions are recorded in `frontend/package-lock.json`; upstream package licenses apply. The Windows release builder collects package LICENSE/NOTICE files under `THIRD-PARTY/`.
- Bundled Google Sans and renamed Source Han Sans UI subsets retain notices and license text under `frontend/src/assets/fonts/` and `frontend/public/licenses/`.
- Python UI and optional inference environments are external dependencies. Their upstream licenses apply separately; no Python or AI runtime is bundled in the preview ZIP.
- The official model catalog records origin links, variant names, and download metadata. YOLO downloads point to the upstream release and are verified by size and SHA-256. LVFace, InsightFace, and SAM3 link to their official model pages. Users obtain weights under those terms; no model weights are redistributed here.
- No claim is made that a code repository license covers every pretrained weight or training dataset. Refer to the official model pages for the chosen model and use.


## GPL and commercial deployment

GPL-3.0-only permits commercial use under its terms. Distributed covered works must meet the applicable source, notice and licensing obligations. The Windows ZIP includes corresponding project source, including the frontend and C# launcher, and rebuild instructions.

Upstream rights must be reviewed separately: Ultralytics and its CLIP fork use AGPL-3.0 terms (Ultralytics also offers Enterprise licensing). GPLv3 section 13 permits combination with AGPLv3: GPL continues to cover the GPL portion, while AGPLv3 section 13 network interaction requirements apply to the combination. Do not replace an upstream AGPL license with GPL.

InsightFace and LVFace distinguish MIT code from noncommercial-research model terms in their official READMEs; SAM3 has its own license. External installation or subprocess execution is not an automatic license exemption. Memivo's license does not relicense upstream code, weights or fonts, or establish proprietary commercial distribution rights for the entire application.
