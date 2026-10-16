# Memivo 可选引擎

重启 `start_memivo.bat`，进入“功能中心”。首次进入自动读取系统、Python、磁盘空间、NVIDIA 显卡、驱动及驱动支持的 CUDA 上限；检测本身不安装依赖。

## 安装与使用

- **视觉 AI 引擎**：YOLO 与 SAM3 共用 PyTorch/Ultralytics 环境。可选自动、CPU、满足候选条件时的 NVIDIA CUDA 12.8。
- **人物识别引擎**：ONNX Runtime/InsightFace，首版自动安装提供 CPU 方案。
- 自动安装首版面向 Windows/Linux x64、主程序 Python 3.10–3.12。其他组合提示不支持，不猜测安装命令。
- 点击安装才联网下载，使用官方 PyPI、PyTorch 源与 Ultralytics 官方 CLIP 仓库的固定提交。引擎安装不会安装驱动、系统 Python、完整 CUDA Toolkit 或模型权重。官方权重在同页独立下载或访问官方入口。
- 环境放在应用状态目录的 `runtimes/vision`、`runtimes/face`，各有所有权和状态标记。模型、数据集与训练结果应存放在这些环境目录之外。
- 安装使用已核对的 PyTorch 2.9.1/torchvision 0.24.1 配对；CPU 与 cu128 分开选择。这是维护中的固定方案，不代表自动追随最新版本。
- 视觉使用已验收的 Ultralytics 8.4.178，另安装 timm 与 SAM3 所需的 CLIP 分词器（固定提交 `7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40`，无需系统 Git）。安装后检查 Torch、Torchvision NMS、Ultralytics、SAM3 接口、timm 与实际分词；GPU 方案额外执行 GPU 张量运算。人脸环境检查核心导入与 CPU provider。检查成功且 `pip check` 通过后才标记就绪。
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
