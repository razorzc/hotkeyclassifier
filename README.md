# PowerLineCV — 图像数据集构建工具

面向计算机视觉数据集构建的桌面应用，用于巡检图像的快速筛选、分类、裁剪与标注。

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
