> 当前GUI采用Adobe React Spectrum。界面环境与启动方式请以 [桌面版说明](SPECTRUM_DESKTOP.md) 为准；下文保留模型硬件与GPU环境参考。

# LVFace 选型与目标台式机适配

核对日期：2026-10-16。本文使用 RTX 5070 Ti 16GB、i7-13700F、32GB RAM、Windows 11 作为参考配置；这些是硬件选型案例，不代表已在该设备验收。

## 官方数据与工程建议分开

[官方仓库](https://github.com/bytedance/LVFace)发布 Glint360K 训练的 T/S/B/L，提供 ONNX 和 PyTorch 权重。[官方模型目录](https://huggingface.co/bytedance-research/LVFace/tree/main)。WebFace42M 的 B 在核对时仍标为 come soon，不能用其论文最好结果代表已发布权重。

官方没有提供“某型号显卡必须多少显存”的逐卡推理表。下面是 **batch=1、已对齐 112×112 人脸、单识别模型**的保守选型建议，不是最低显存、实测峰值或训练配置。FP32 ONNX 为第一阶段基线；文件大小不等于运行显存。

| 版本 | 官方 IJB-C TAR@FAR=1e-4 | 建议优先尝试的独显档位（工程估计） | 5070 Ti 16GB 上的用途 |
| --- | ---: | --- | --- |
| T | 96.67% | 4GB+，如 RTX 3050 6GB | 快速基线、CPU 也可测试但不承诺速度 |
| S | 97.31% | 6GB+，如 RTX 3060 12GB / 4060 8GB | 吞吐量对照 |
| B | 97.70% | 8GB+，如 RTX 4060/4070 及以上 | **推荐主模型**，单脸推理起步 |
| L | 97.66% | 12–16GB+，如 RTX 4070 Ti Super / 5070 Ti | 可尝试；是否值得取决于实际照片收益 |

这些档位不是排他列表，显卡速度、驱动与执行后端同样重要；较小显存也可能运行较大模型。预计目标机可尝试四个版本的单脸推理，但尚未在目标机验证。不要因为 B 的名字推断它与通用 ViT-B 参数完全相同，官方定义使用自己的宽度和深度。

B 并非全部指标都赢 L：官方 IJB-C FAR=1e-5 为 B 97.00%、L 97.02%；FAR=1e-6 为 B 90.06%、L 89.51%。这不是你的旅行相册归档准确率。

## 推荐运行策略

- 先 B，再 S，再决定是否测试 L。初版实际使用 batch=1，不宣称支持批张量输入。
- 高分辨率原图用于人脸检测；识别输入仍是对齐后的 112×112 人脸。不要随意降低模型要求的 112×112 输入尺寸。
- SAM3、YOLO 未来按任务阶段加载/卸载；初版不同时常驻。16GB 不等于可以任意叠加这些模型。
- 先 FP32 建立正确性基线。FP16 需要转换并复核相似度、阈值和归档质量，不是改一个配置就一定减半显存。
- 当前项目支持 CPU / CUDA 显式选择，并检查 CUDA provider 是否成功启用。provider 启用不等于每个算子都跑 GPU，精确算子分配需要 ORT profile。
- GPU 加速可用性、峰值显存、速度、真实照片精度均需目标机实测。

## Windows 安装起步方案

不要复制官方示例的旧 NumPy 1.23 / cu124 环境到这台新显卡，也不要修改全局 base。下面是待目标机验证的独立环境方案，不是已验证的锁定环境：

```powershell
conda create -n memivo-album python=3.12 -y
conda activate memivo-album
python -m pip install -r requirements-album.txt
python -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install "onnxruntime-gpu>=1.21,<1.27"
python -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0)); print((torch.ones(4,device='cuda')+1).cpu())"
python -c "import torch, onnxruntime as ort; ort.preload_dlls(); print(ort.__version__,ort.get_available_providers())"
python main.py
```

Torch 在本阶段用于提供/验证 CUDA DLL 环境，不是执行 LVFace 所必需的推理后端。CPU 环境只需 `pip install onnxruntime`，不需要 Torch GPU。CPU 和 GPU ORT 包不要同时安装。ORT GPU 1.27 起默认 CUDA 13 的包与 CUDA 12 包分开，因此这里限制版本区间；后续升级需重新核对 [ORT CUDA 兼容表](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)。仅有 CUDA Toolkit 不代表已有匹配的 cuDNN。

InsightFace 在部分 Windows/Python 组合下安装时会编译扩展，需要 Visual Studio Build Tools 的 C++ 桌面开发组件。不要从未知来源安装 wheel。安装完成后记录 `python -m pip freeze > environment.lock.txt`，再以真实推理验证，不能只凭导入成功判断兼容。

## 准备权重与测量

1. 从官方模型目录选择 LVFace-B_Glint360K 的 ONNX 文件，保留配套 external data 文件（若有）。GUI 选择实际文件名，不依赖示例文件名。
2. 从 [InsightFace 官方模型库](https://github.com/deepinsight/insightface/tree/master/model_zoo)准备 SCRFD `det_10g.onnx`。LVFace 负责身份特征，SCRFD 负责检测与五点对齐。功能中心提供官方入口；人脸权重下载后放入模型目录，选择并扫描。
3. 使用界面添加每位朋友的一张或多张单人参考照。匹配阈值 0.55、候选差距 0.08 仅为未校准起始值，不是官方推荐值。
4. 先用小批照片检查检测框、身份结果与 provider，再扩大范围。用 `nvidia-smi -l 1`观察 GPU 进程和显存；采样可能遗漏短峰值。
5. 识别模型微基准（不是完整相册耗时，也不衡量准确率）：

```powershell
python album_cli.py benchmark --model "D:/Models/LVFace-B_Glint360K.onnx" --face "D:/Photos/aligned-face.png" --device cuda --repeats 50 --output "benchmark-B.json"
```

传入已经对齐的人脸。工具输出模型 SHA256、ORT 版本、provider、加载时间、batch=1 的 session.run 中位数/P95。报告会说明不含检测、预处理与磁盘 I/O。不能用它替代端到端测试。

## 授权

LVFace 官方代码为 MIT，但官方 README 对下载模型另列非商业研究限制；InsightFace 官方模型也有独立限制。权重公开可下载不等于自由商用。此处不把代码许可证延伸到权重。
