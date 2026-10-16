# Memivo：GPL 與第三方授權

採用日期：2026-10-17。Memivo 自有程式與文件採 **GPL-3.0-only**，完整條款見 [LICENSE](../LICENSE)，範圍見 [NOTICE](../NOTICE)。先前討論的非商業授權方案未採用。

## 使用、修改與散布

GPL 允許個人及商業使用、修改、複製、收費與再散布。散布受 GPL 規範的修改版或組合作品時，須履行適用的同授權、對應原始碼及聲明義務。提供原始碼的對象與方式依 GPL 第 6 節辦理，並不一概要求上傳到公開 GitHub。程式不提供擔保。

私人使用或內部修改，通常不必向公眾發布原始碼。GPL 本身不因只提供網路服務就要求公開原始碼；但 GPLv3 第 13 節允許與 AGPLv3 組合，GPL 部分繼續適用 GPL，AGPLv3 第 13 節的網路互動要求適用於組合作品。第三方 AGPL 條款不能改成 GPL；本專案的 Ultralytics／CLIP fork 需按相關條款處理。

GPL **不禁止他人商用**。已依 GPL 授出的版本，不能靠在 README 加上「禁止商用」撤回接收者已獲授的權利。另行提供商業授權前，必須確認自有程式、外部貢獻及上游元件的授權權限。

## 原始碼與重建

Windows ZIP 內附對應專案原始碼 ZIP，包含 Python、React／TypeScript、C# 啟動器、測試、相依版本與建構腳本。解壓至獨立資料夾後，按照 [README](../README.md) 安裝建構相依，再執行 `python scripts/build_release.py`。外部相依與模型仍須按各自條款取得；不包含模型權重。

## 現有依賴與模型要分開看

| 元件 | 官方說明與目前影響 |
| --- | --- |
| Ultralytics YOLO 與所選官方權重 | [官方授權頁](https://www.ultralytics.com/license)提供 AGPL-3.0 與 Enterprise 路徑。不能自行給第三方 AGPL 程式加上禁止商用限制；若要把相關程式／模型嵌入閉源商業產品，需依實際整合範圍確認 AGPL 義務或取得相應商業授權。不是「所有商業使用都必須付費」。 |
| InsightFace 程式與預訓練權重 | [官方 README](https://github.com/deepinsight/insightface)將 MIT 程式與僅供非商業研究的官方預訓練模型分開；手動下載或自動下載不改變權重條款。商用應取得相應權利或換用具備所需授權的模型。 |
| LVFace 程式與預訓練權重 | [官方 README](https://github.com/bytedance/LVFace)表示程式為 MIT，另將下載模型描述為非商業研究用途。即使模型頁面顯示 MIT 標籤，也不能忽略此權重說明；正式商用前應向權利人確認具體權重的授權。 |
| SAM3 | 使用獨立的 [SAM License](https://huggingface.co/facebook/sam3/blob/main/LICENSE)。存取申請通過不等於不受限制，應核對用途、散布、聲明與其他條件。 |
| React／Spectrum／字型等 | 保留各自套件與字型的原始授權；自有程式的限制不能取代第三方的條款。檔案來源與聲明見 [第三方資訊](../THIRD_PARTY_NOTICES.md)。 |

**引擎另行下載、透過子程序呼叫或不把權重打進 EXE，均不是自動免除授權義務的保證。** 是否屬於組合作品、能否採不相容條款，需要看實際程式與整合方式，不能只憑一個技術形式判斷。此處不宣稱目前整套 Memivo 已具備閉源商業發行權。


## 官方資料

- [GNU GPL v3 全文](https://www.gnu.org/licenses/gpl-3.0.html)，尤其第 6、10、13 節。
- [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html)。
- [第三方資訊](../THIRD_PARTY_NOTICES.md)。
