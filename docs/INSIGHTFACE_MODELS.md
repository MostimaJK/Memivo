# InsightFace：下載哪一包、使用哪些檔案？

Memivo 的人物整理流程需要 **一個人臉偵測模型 + 一個身份特徵模型**。InsightFace 是工具庫及模型集合；不需要把整包的每個模型都載入。

## 第一次使用

1. 先選 **buffalo_l.zip**，作為一般照片整理的起點。[官方 ZIP](https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_l.zip) · [官方發布頁 Assets](https://github.com/deepinsight/insightface/releases/tag/model-zoo) · [官方模型說明](https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md)。不要下載 GitHub 自動產生的 Source code 壓縮包。
2. 解壓縮，找出 `det_10g.onnx` 及 `w600k_r50.onnx`。部分型號有一層同名子目錄，請進入目錄找檔案。
3. 依下圖放入 Memivo 模型庫。原始碼版是專案根目錄的 `model/`，EXE 版是 `Memivo.exe` 旁的 `model/`；自訂模型路徑以介面顯示為準。

```text
Memivo/
  model/
    face/
      detector/
        det_10g.onnx       # 找出人臉及對齊用的五點
      recognition/
        w600k_r50.onnx     # 提取身份特徵，用於匹配參考照
```

4. 在功能中心按「掃描模型」，再於設定確認 SCRFD 偵測與 LVFace／ArcFace 識別兩個選項。只有唯一候選且沒有有效設定時才會自動選取；多個候選需要自己選擇。
5. 安裝「人物識別引擎」；權重檔案與執行環境是兩件事。儲存設定、登記人物參考照，再執行整理並檢閱不確定結果。

如果已經使用 LVFace，僅取 `det_10g.onnx` 作為偵測器，識別部分保留 LVFace，不必同時再載入本包的 ArcFace。更換識別模型後需重新評估匹配閾值與參考照片效果。

## 壓縮包中的其他檔案

已核對官方 `model-zoo` 發布資產的 ZIP 檔案目錄（2026-10-17）。`buffalo_l` 完整包是 **5 個 ONNX**，不是固定 4 個；`buffalo_sc` 則只有 2 個。

| buffalo_l 檔案 | 用途 | Memivo 目前是否需要 |
| --- | --- | --- |
| `det_10g.onnx` | SCRFD 人臉位置與五點關鍵點 | 需要，放入 `model/face/detector/` |
| `w600k_r50.onnx` | 身份特徵，與參考照進行匹配 | 需要，放入 `model/face/recognition/`；可由 LVFace 替代 |
| `2d106det.onnx` | 106 點二維人臉關鍵點 | 不需要；不要當成偵測器或身份模型 |
| `1k3d68.onnx` | 68 點三維人臉關鍵點 | 不需要 |
| `genderage.onnx` | 年齡／性別估計 | 不需要 |

若看到 4 個檔案，先檢查實際包名、內層目錄與檔名；不要按排序猜測。當前流程只要求正確的偵測與識別檔案，缺少未使用的輔助模型不會阻止整理。SCRFD 已提供對齊所需五點，不必另外載入 106 點模型。保留下載原包及其授權檔供日後查閱；只將使用的 ONNX 放進角色目錄。

## 其他型號如何選？

| 官方包與下載 | 偵測檔案 | 識別檔案 | 對專案的參考價值 |
| --- | --- | --- | --- |
| [buffalo_l.zip](https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_l.zip) | `det_10g.onnx` | `w600k_r50.onnx` | 常規起點，較大的偵測器 |
| [buffalo_m.zip](https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_m.zip) | `det_2.5g.onnx` | `w600k_r50.onnx` | 較小偵測器，與 l 使用相同識別模型 |
| [buffalo_s.zip](https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_s.zip) | `det_500m.onnx` | `w600k_mbf.onnx` | 較輕量的偵測及識別組合 |
| [buffalo_sc.zip](https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_sc.zip) | `det_500m.onnx` | `w600k_mbf.onnx` | s 的精簡包，不包含三個輔助模型 |
| [antelopev2.zip](https://github.com/deepinsight/insightface/releases/download/model-zoo/antelopev2.zip) | `scrfd_10g_bnkps.onnx` | `glintr100.onnx` | 更大的 ResNet100 識別模型，需評估速度及實際匹配效果 |

這是 Memivo 當前 ONNX 接入流程的模型選擇，不是 InsightFace 所有新模型包的相容性承諾。每個型號的正確兩個檔案放置位置相同；檔名不同不要任意改成其他模型名稱。掃描按角色目錄與副檔名發現候選，不會自動辨識錯放的關鍵點／屬性模型。

## 下載入口、變動與條款

- 程式提供官方 ZIP 手動下載連結，沒有鏡像權重，也沒有為這些 ZIP 啟用程式內校驗下載；YOLO 的校驗下載是另一條流程。
- 直鏈可能被官方移動、更新或受地區網路限制；失效時先到 [官方發布頁](https://github.com/deepinsight/insightface/releases/tag/model-zoo) 的 Assets 尋找同名檔案，再查看 [官方模型說明](https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md) 的下載入口。沒有自動追隨未知鏡像。
- 官方工具庫程式碼與預訓練權重的授權不同。官方模型說明將其預訓練模型限制為非商業研究；Memivo 的 GPL 不會改變權重條款。商業用途請自行取得適當授權，並以下載當時官方條款為準。
