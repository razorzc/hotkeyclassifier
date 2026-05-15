# PowerLineCV — 电力巡检图像数据集构建工具

面向计算机视觉数据集构建的桌面应用，用于电力巡检图像的快速筛选、缺陷分类、裁剪与标注。

## 功能

- **高速浏览** — 方向键切换图片，支持 10 万级大图
- **键盘分类** — 一键分类并复制到目标目录，自动生成 `labels.csv`
- **固定尺寸裁剪** — 224×224 / 384×384 / 640×640，拖动定位，回车保存
- **进度恢复** — 自动保存 `.sort_progress.json`，再次打开同一文件夹时恢复到上次位置
- **撤销** — Ctrl+Z 撤销上一步分类/裁剪
- **拖拽分类** — 右侧面板支持拖放图片完成分类
- **模糊检测** — OpenCV Laplacian 方差检测模糊图
- **预加载** — 前后 5 张异步缓存，大图切换不卡顿
- **深色主题** — 全界面深色主题，长时间使用不伤眼

## 快捷键

| 按键 | 功能 |
|------|------|
| ← → | 上一张/下一张 |
| Home / End | 第一张/最后一张 |
| Q/W/E/R | 输电线分类（断股/损伤/异物/正常） |
| A/S/D/F | 塔杆分类（变形/锈蚀/异物/正常） |
| T | 待定 |
| 1/2/3 | 选择裁剪框尺寸 |
| Enter | 独立保存裁剪 |
| Ctrl+Z | 撤销 |
| 0 | 适应窗口 |
| Space+拖动 | 平移 |

## 运行

### 源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 便携版

下载 [Releases](../../releases) 中的 `PowerLineCV.exe`，双击运行，无需安装 Python。

## 工作流

1. Ctrl+O 打开图片文件夹
2. 设置 → 路径 → 指定分类输出目录
3. 方向键浏览，按分类键打标签
4. 可选：按 1/2/3 框选缺陷区域，分类时自动保存裁剪

## 技术栈

Python 3.12 / PySide6 / OpenCV / Pillow / numpy

## 项目结构

```
sort/
├── main.py              # 入口
├── config/              # 配置文件
│   ├── config.json      # 快捷键、分类、路径等设置
│   └── dark_theme.qss   # 深色主题
├── core/                # 核心逻辑
│   ├── image_manager.py   # 图片索引与加载
│   ├── file_mover.py      # 文件移动与冲突处理
│   ├── label_manager.py   # CSV 标注管理
│   ├── undo_manager.py    # 撤销栈
│   ├── crop_manager.py    # 裁剪保存
│   ├── preload_manager.py # 异步预加载
│   ├── blur_detector.py   # 模糊检测
│   ├── progress_manager.py# 进度持久化
│   └── settings.py        # 配置读写
├── widgets/             # UI 组件
│   ├── image_viewer.py    # 图片查看器
│   ├── crop_overlay.py    # 裁剪框
│   ├── drag_zone.py       # 拖拽分类区
│   └── info_overlay.py    # 信息浮层
├── ui/                  # 界面
│   ├── main_window.py     # 主窗口
│   └── settings_dialog.py # 设置对话框
└── utils/
    └── logger.py
```
