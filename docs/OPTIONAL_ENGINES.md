# Memivo 可选引擎

重启 `start_memivo.bat`，进入“功能中心”。首次进入自动读取系统、Python、磁盘空间、NVIDIA 显卡、驱动及驱动支持的 CUDA 上限；检测本身不安装依赖。

## 安装与使用

- **视觉 AI 引擎**：YOLO 与 SAM3 共用 PyTorch/Ultralytics 环境。可选自动、CPU、满足候选条件时的 NVIDIA CUDA 12.8。
- **人物识别引擎**：ONNX Runtime/InsightFace，支持自动、CPU、NVIDIA CUDA 12.8；5070 Ti 等满足检测条件时自动推荐 NVIDIA。
- 自动安装首版面向 Windows/Linux x64、主程序 Python 3.10–3.12。其他组合提示不支持，不猜测安装命令。
- 点击安装才联网下载，使用官方 PyPI、PyTorch 源与 Ultralytics 官方 CLIP 仓库的固定提交。引擎安装不会安装驱动、系统 Python、完整 CUDA Toolkit 或模型权重。官方权重在同页独立下载或访问官方入口。
- 环境放在应用状态目录的 `runtimes/vision`、`runtimes/face`，各有所有权和状态标记。模型、数据集与训练结果应存放在这些环境目录之外。
- 安装使用已核对的 PyTorch 2.9.1/torchvision 0.24.1 配对；CPU 与 cu128 分开选择。这是维护中的固定方案，不代表自动追随最新版本。
- 视觉使用已验收的 Ultralytics 8.4.178，另安装 timm 与 SAM3 所需的 CLIP 分词器（固定提交 `7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40`，无需系统 Git）。安装后检查 Torch、Torchvision NMS、Ultralytics、SAM3 接口、timm 与实际分词；GPU 方案额外执行 GPU 张量运算。人脸环境检查核心导入，并执行 ONNX 卷积；GPU 方案加载环境内的 NVIDIA 运行库，检查计算结果和 CUDA 节点执行记录，失败时不会报告 GPU 就绪。检查成功且 `pip check` 通过后才标记就绪。
- 模型库见项目或 EXE 同级的 `model/README.md`：按用途放入权重，启动/设置扫描，单个候选自动选择、多个候选下拉选择；保留外部文件入口。YOLO11/YOLO26 检测与分割各有 n/s/m/l/x，点击下载才联网，验证发布文件大小与 SHA-256，不覆盖同名文件。LVFace、InsightFace、SAM3 提供官方规格/入口；SAM3 访问申请由用户自行处理。
- 模型权重仍在设置中选择；执行设备仍遵循已保存设置，不因安装方案改变而覆盖用户设置。环境检查不等于具体模型加载或精度验证。

受管理环境就绪后，检测、分割、人脸整理由对应环境的独立 Python 子进程运行，通过临时 JSON 和数值掩码文件传递结果。未安装受管理环境时继续兼容原先显式配置的 Python 主环境。

## 进度、失败与卸载

安装进度按五个阶段显示，不冒充下载字节百分比；诊断日志只保留最近 80 行。停止会终止安装/模型子进程树。未完成环境保留为需要修复，可重试或清理。默认不缓存安装包，重试可能重新下载。

卸载前提示共享影响，只删除带正确标记且位于固定管理根目录中的环境；不会卸载外部 Python 环境。YOLO 与 SAM3 共用视觉引擎，不能单独删除它们共用的 Torch。照片、外置权重、项目和审核记录不随引擎删除。

部分 Windows 环境的 InsightFace 安装需要预先准备 C++ 构建工具；缺少工具、网络失败、依赖冲突、GPU 运算失败均保留错误状态与日志，不承诺所有电脑零配置安装。

## 验证边界

本机已完成 NVIDIA 实际探测、前端交互与构建、多语言覆盖、环境管理及数据集测试。另在隔离验收目录真实安装 CPU 视觉引擎（约 984 MiB），通过 Torch/NMS/SAM3 接口检查与 pip check，并执行合成数据上的检测训练、分割训练、评估、恢复与再次检测。CUDA 引擎安装、GPU 实模型、人脸引擎仍需目标机测试。标注和训练入口已提供，见 [完整流程](LEARNING_WORKFLOW.md)。

安装方案参考：[PyTorch 官方版本配对](https://pytorch.org/get-started/previous-versions/#v291)、[Ultralytics 安装说明](https://docs.ultralytics.com/quickstart/)。方案更新需重新检查支持系统、Python、驱动和真实运行测试。

## RTX 5070 Ti：从 CPU 切换到 GPU

1. 更新主程序。源码版执行 `git pull --ff-only`，再运行 `start_memivo.bat`；EXE 版须下载新的 Windows ZIP 并完整解压，不能只替换一个 EXE。
2. 功能中心点“重新检测”，确认显示 RTX 5070 Ti。需要驱动支持 CUDA 12.8 或以上；这里是驱动能力，不要求手动安装完整 CUDA Toolkit。
3. 若人物识别引擎已经装成 CPU，先卸载该引擎，再选择“自动选择”或“NVIDIA · CUDA 12.8”并安装。模型权重保持原位置。
4. 等安装验证完成，确认引擎显示 NVIDIA。若失败，查看诊断日志；不要将失败状态视为 GPU 已启用。
5. 在设置中将执行设备改为 NVIDIA CUDA，保存。设备设置是项目设置，不会因安装引擎自动更改。
6. 先用少量照片执行人物识别。任务报告 `report.json` 中的 `providers` 应包含 `CUDAExecutionProvider`。更换设备后缓存仍可复用，缓存命中不表示本次实际调用 GPU；验证时应使用新照片或新项目。

GPU 人脸环境采用 ONNX Runtime GPU 1.23.2、CUDA 12.8 运行库与 cuDNN 9.10.2.21，依赖放在独立环境，不修改系统 CUDA；无需额外安装 PyTorch。GPU 安装仍需联网下载数 GB 依赖，缺少 Microsoft C++ 构建工具时 InsightFace 0.7.3 可能安装失败。不同引擎的依赖不会相互借用。

此版本通过安装配方、GPU 失败状态及任务设备传递测试；本机不具备目标 GPU，RTX 5070 Ti 实际推理仍需目标机验证。安装时执行的 CUDA 卷积检查不能代替完整模型的实际测试。

参考：[ONNX Runtime CUDA 依赖与 DLL 加载](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)、[NVIDIA cuDNN 支持矩阵](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.10.1/reference/support-matrix.html)。

## CPU 引擎误配 CUDA 与诊断日志

如果日志显示 `torch-2.9.1+cpu`、`Invalid CUDA device=0`、`torch.cuda.is_available(): False`，当前解释器装的是 CPU 版 PyTorch，却被要求使用 CUDA。更换主程序或修改设置不会将已有 CPU 引擎自动升级为 GPU 版。

解决办法：先停止任务，在功能中心卸载视觉 AI 引擎，选择 NVIDIA CUDA 12.8 并重新安装，等待 GPU 计算验证成功。模型权重保留。若只想先验证工作流程，可在设置中改为 CPU 后重试。人物引擎也需按其独立方案选择；两套环境不互相替代。

新版会在受管理引擎启动推理前检查已安装方案与任务设备，不匹配时直接说明。功能中心也会显示配置不匹配警告。

诊断日志支持“复制日志”和“全选日志”，文本框只读但可以框选及 Ctrl+C；复制不修改原日志。桌面宿主开启文字选择，画布仍保留专用拖拽行为。若系统限制剪贴板，按钮会全选并提示手动复制。

子进程完整输出保存在应用数据目录的 `runtimes/logs/`，并保留最近失败记录。Windows EXE 默认是 `%LOCALAPPDATA%/Memivo/data/runtimes/logs/`；源码默认是 `.segmentflow/runtimes/logs/`。界面显示的路径为准，可以点击“打开日志文件夹”。这些日志保存在本机，不自动上传；其中可能包含本机路径，分享前可自行检查。

检测与分割工作台会直接显示失败原因、日志复制入口以及配置入口；底部失败状态为红色。新结果未生成时保留上一次成功结果，并明确提示本次失败。当前的复制按钮复制界面中的诊断摘要和最近输出，完整原始输出请取日志文件。

本机复用了已安装的 CPU 引擎，以官方 YOLO26n 权重实际检测，并复现 CPU/CUDA 误配异常，验证提前拦截、日志落盘与错误详情；这不代表在 RTX 5070 Ti 上完成了真实推理测试。
