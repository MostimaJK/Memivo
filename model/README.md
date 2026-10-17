# Memivo 模型库

将官方权重放进对应子文件夹，在设置点击“扫描模型”。程序启动与打开设置时也会扫描；某个用途只有一个候选且没有有效的已保存选择时自动选中，有多个候选时使用下拉框选择。扫描不会把所有模型载入内存。

| 子目录 | 文件 | 用途 |
| --- | --- | --- |
| `face/detector/` | SCRFD `.onnx`（如 `det_10g.onnx`） | 人脸位置与五点对齐 |
| `face/recognition/` | LVFace 或 ArcFace `.onnx` | 人物身份特征 |
| `sam3/` | `sam3.pt` | 提示分割、抠图 |
| `yolo/detect/` | YOLO `.pt` | 检测、计数与检测训练 |
| `yolo/segment/` | YOLO `*-seg.pt` | 实例分割训练，也可用于框计数 |

支持子文件夹与中文路径。仅按用途目录与扩展名发现候选；加载时由引擎验证具体架构。不要把人脸关键点、年龄性别 ONNX 当作识别模型。InsightFace 包解压后请分别移动检测和识别文件。LVFace 请选择 ONNX，当前人脸模块不直接接收 `.pt`。

功能中心提供官方目录：YOLO11/YOLO26 检测与分割各有 n/s/m/l/x，可由程序显式下载、核对发布文件大小与 SHA-256。LVFace T/S/B/L、WebFace42M B、InsightFace 模型包和 SAM3 提供官方入口；SAM3 需自行申请访问。没有在后台下载任何模型。

源码使用项目根 `model/`；EXE 使用 `Memivo.exe` 旁的 `model/`，请将整个发布目录放在可写位置。高级用户可在源码启动时使用 `MEMIVO_MODEL_ROOT` 指定目录。模型不随引擎卸载删除，不随发布包分发。

目录来源核对：2026-10-17。条款以官方为准：[YOLO11](https://docs.ultralytics.com/models/yolo11/)、[YOLO26](https://docs.ultralytics.com/models/yolo26/)、[LVFace](https://github.com/bytedance/LVFace)、[InsightFace](https://github.com/deepinsight/insightface/tree/master/model_zoo)、[SAM3](https://huggingface.co/facebook/sam3)。

## InsightFace 下载与解压指引

第一次推荐 buffalo_l.zip，仅需要 det_10g.onnx（放 face/detector）与 w600k_r50.onnx（放 face/recognition）。完整包通常包含 5 个 ONNX；另外三个为 106 点二维关键点、68 点三维关键点、年龄／性别估计，当前流程不需要。若已使用 LVFace，只需取检测文件。各规格文件名、官方 ZIP 链接、目录示例和备用入口请看 [详细指南](../docs/INSIGHTFACE_MODELS.md)。功能中心也会随所选规格展示对应文件。
