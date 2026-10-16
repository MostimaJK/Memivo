# Memivo · Adobe React Spectrum 工作台

## 一键启动

Windows 双击根目录 **start_memivo.bat**，也可执行 `python main.py`。新版仓库只保留一个一键启动 BAT。

首次启动需要联网安装界面依赖并构建前端；需要已安装 Python（建议3.12）和 Node.js LTS（建议22/24）。后续源码未变时跳过构建，不要求联网。启动失败会保留控制台错误。

```powershell
.\start_memivo.bat --check    # 只读检查，不安装、不打开窗口
.\start_memivo.bat            # 独立桌面窗口
.\start_memivo.bat --browser  # 开发用浏览器预览
.\start_memivo.bat --rebuild  # 强制重新构建前端
```

启动器优先使用 `MEMIVO_PYTHON` 指定的环境，或已登记的 `memivo-album` Conda 环境；否则在项目中创建 `.venv-spectrum`。仅自动安装 `requirements-spectrum.txt`，不会自动安装模型引擎、CUDA 或下载权重。该环境可以先浏览照片、管理参考照、打开历史项目。

需要让原有模型环境运行桌面壳时，设置环境变量，例如 PowerShell：

```powershell
$env:MEMIVO_PYTHON = 'D:/YourEnv/python.exe'
.\start_memivo.bat
```

首次会向所选环境安装缺少的界面依赖；请使用项目专属环境。启动器不会修改全局 Python 环境，除非用户通过变量显式指定它。

## 架构

- **React 19 + TypeScript + Adobe React Spectrum 2**：正式组件库 `@react-spectrum/s2`，不是无样式 React Aria 拼接或仿制皮肤。依赖版本由 `frontend/package-lock.json` 锁定。
- **pywebview + 系统 WebView2**：Windows 原生独立窗口，不捆绑完整 Chromium。需要 Microsoft WebView2 Runtime 和可用 .NET 环境；安装器说明见 [pywebview](https://pywebview.flowrl.com/guide/installation.html)。
- **本地 Python API**：仅监听127.0.0.1随机端口，每次启动生成会话令牌。无云端服务，不上传照片。静态资源打包在本机。
- **独立工作线程**：扫描、识别、分割、导出不阻塞界面；同一时间一个模型任务。已安装的受管理 AI 引擎通过独立 Python 子进程运行，支持取消；未安装受管理引擎时兼容显式配置的主环境。
- **原有 Python 核心复用**：`album/` 的特征缓存、身份匹配和导出继续使用；SAM3 通过 `sam_backend.py` 接入。此仓库以新版桌面入口为维护对象。

## 操作流程

1. **照片图库 → 导入照片**：选择目录，递归读取支持的图片。原图不移动。每页最多48张，缩略图按需加载，内存缓存最多160张。这里采用分页，不宣称完整列表虚拟化。
2. **人物相册 → 登记朋友**：姓名可复用以补充参考照。每张参考照应只有一张清晰人脸，推理时会验证。没有权重也可先登记，但不代表已经验证样本质量。
3. **右上角设置**：选择 SCRFD ONNX、LVFace/ArcFace ONNX，选择CPU或CUDA。SAM3模型可单独配置。当前默认CPU，避免把未验证的GPU后端默认为可用。
4. **开始整理**：显示真实阶段与处理张数。低分或候选接近时进入待审核；失败会显示错误，保留输入以便重试。
5. **照片详情**：点击人脸序号，查看候选相似度，确认身份或“不归档”；支持撤销。未识别、无人脸、识别失败分别展示。
6. **导出人物相册**：复制原图到各人物目录；合照可同时归给多人；自动匹配结果也会参与导出，请先检查。内容哈希防止静默覆盖，导出前核对原图是否变化。
7. **分割工作台**：选择照片，使用正点、负点、框选或文字模式。几何标记与文本模式分开；SAM3结果叠加显示，可调透明度并导出透明PNG。当前合并所有返回掩码导出，尚无逐实例独立编辑/导出。

当前无“通用自然语言聊天”功能；SAM3文字输入是视觉概念提示。人物身份不由SAM3文本姓名识别完成。

## 项目保存与旧数据

应用会话位置 `.segmentflow/session.json`；每次导入新目录建立独立项目，记录其 `project.json`、`library.json`、特征缓存及识别报告。历史项目可通过侧栏“打开已有项目”选择 project.json。

旧相册版的 project.json/report.json 可以打开；旧格式没有的SAM3配置使用默认值。未开始识别的导入照片也会通过library.json恢复。任务记录目前仅保存本次进程会话，不是永久审计日志。

原始照片、人物参考照、模型权重不随Git提交。应用工作目录和构建产物已加入.gitignore。

## 模型依赖与硬件

界面轻量环境未安装AI引擎。可在当前所选Python环境另行安装：

```powershell
python -m pip install opencv-python insightface onnxruntime
# CPU/GPU ORT只安装一种；GPU环境依照硬件文档配置。
# SAM3另外需要匹配的Torch、Ultralytics和本地权重。
```

安装Windows InsightFace可能需要C++ Build Tools；不承诺所有版本可以免编译安装。参见 [LVFace硬件说明](LVFACE_HARDWARE.md)。笔记本3060 6GB先测T/S，台式机5070Ti 16GB先测B，均需真实推理验证。

SAM3在几何与文本模式之间切换时释放另一种predictor引用，避免有意常驻两份SAM；仍没有对SAM3与人脸后端做完整GPU显存调度。人物任务结束后后端局部引用释放，原生运行库可能仍保留缓存。不要将其称为已实现的显存优化成果。

## 开发与验证

```powershell
cd frontend
npm ci
npm run build
cd ..
python -m unittest discover -s tests -v
```

当前验证：TypeScript检查和生产构建；11项核心/API测试；真实浏览器导入仓库DEMO图片、搜索/详情、正负点与撤销、缺模型错误恢复、模型设置弹窗及主题；通过BAT启动Windows WebView2独立窗口。

模型测试使用显式假后端验证业务，不证明真实识别精度。本机还没有安装ORT/InsightFace/Ultralytics与权重，真实模型端到端推理、CUDA兼容性和精度未验证。浏览器截图中的仓库DEMO图含旧程序画面，是输入图片，不是新版本推理结果。

人体ReID、主动学习策略、YOLO训练仍是后续算法阶段。本次完成界面与应用架构重构，没有把这些算法标成已完成。


## Spectrum 2 视觉修订

使用 Adobe 官方 S2 的 Provider、Button、ActionButton、SearchField、Picker、TextField、NumberField、Dialog、SegmentedControl、CardView、AssetCard、Slider 与进度组件；图标也来自 S2。旧 v3 包已经移除。主工作区、导航和标记画布属于应用布局，不宣称是官方现成页面模板。

页面采用中性底色、24px 圆角白色主面板、胶囊搜索和按钮、紧凑导航。CardView 使用 waterfall 布局与原始图片尺寸；中文字体明确回退 Microsoft YaHei UI，避免无 Adobe 字体时回退宋体。构建接入官方文档推荐的 unplugin-parcel-macros 和 lightningcss。


## Language 与字体

设置顶部的 Language 提供简体中文（zh-CN）、繁體中文（zh-TW）、English（en-US）。选择后点击保存设置生效。菜单、弹窗、标准任务消息与 Spectrum 内建控件跟随语言；文件路径、照片名、朋友姓名和未识别的模型底层诊断保留原文。语言偏好独立保存在 .segmentflow/preferences.json，不随项目切换。首次启动默认简体中文。

English 使用官方开放版 Google Sans；简体推荐思源黑体 SC，繁体推荐思源黑体 TC。中文界面随应用提供基于对应地区字体制作的字形子集，修改版内部名为 Memivo Han SC/TC；不包含的姓名或文件名字符回退到本机对应地区字体。所有字体在本地加载，不依赖在线字体服务。三份 WOFF2 合计约 391 KB。原始许可证与来源在 frontend/src/assets/fonts/，构建同时附带 public/licenses 下的字体声明。

验证本地化：node scripts/check_i18n.cjs；覆盖词条完整性、语言参数、带占位符的消息和用户数据不改写。字体开发工具 scripts/build_ui_fonts.py 仅维护时使用，普通用户启动不需要 fonttools/brotli。


## Memivo 名称与旧版本兼容

正式产品名统一为 Memivo（Memory + Visual 的音节融合），英文说明为 Intelligent Photo Organization。三种语言的窗口与网页标题均保留英文品牌名。中文子集字体内部名同步为 Memivo Han SC / TC；原字体作者与许可声明保留。

唯一的一键启动 BAT 是 `start_memivo.bat`。`MEMIVO_PYTHON` 优先于旧的 `SEGMENTFLOW_PYTHON`；自动发现支持 `memivo-album` 与原有 `segmentflow-album` Conda 环境。历史数据目录 `.segmentflow/`、构建指纹位置以及浏览器偏好键继续复用，避免清理入口时丢失已有照片、审核结果与语言偏好。API 使用 X-Memivo-Token，同时接受旧的 X-SegmentFlow-Token。


## 应用图标

页眉和浏览器标签使用 frontend/public/memivo.svg，Windows 窗口与任务栏使用同一标志生成的 memivo.ico（16 至 256 像素多尺寸）。启动时设置 Memivo.Desktop 应用标识，独立于 Python 的任务栏分组。图标已随项目提供，普通启动不需要额外生成；维护图标可运行 scripts/build_app_icon.py（依赖 Pillow）。


## 启动位置

Windows 启动时按鼠标所在屏幕的工作区居中（避开任务栏），在显示前完成定位。窗口默认尺寸随该屏幕 DPI 缩放，空间不足时缩小尺寸与最小尺寸，并保留边缘间距。每次启动重新计算，不恢复旧的偏移位置；适用于切换笔记本与外接显示器。多显示器混合缩放的完整组合仍需目标设备实测。
