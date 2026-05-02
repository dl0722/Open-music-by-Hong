# 🎵 Open Music by Hong

> 一个基于 PySide6 + pygame 的本地音乐播放器 — **颜值在线，功能齐全**

[![Portfolio](https://img.shields.io/badge/Portfolio-dl0722.github.io-ff69b4?style=flat-square)](https://dl0722.github.io)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt6-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## ✨ 功能一览

| 功能 | 说明 |
|------|------|
| 🎶 **本地音乐播放** | 支持 mp3 / flac / wav / ogg 等多种格式 |
| 📂 **多歌单管理** | 自定义歌单，随心分类 |
| 📝 **在线歌词同步** | 自动匹配歌词，卡拉 OK 体验 |
| 🎛️ **均衡器** | 10 段均衡器，调出你的专属音效 |
| 🖼️ **专辑封面** | 自动显示内嵌封面图 |
| 📋 **播放队列** | 拖拽排序，想听啥就听啥 |
| ⌨️ **快捷键** | 全局热键，摸鱼必备 |

---

## 🚀 快速上手

### 方式一：直接运行源码

```bash
# 1. 安装 Python 3.8+
# 2. 安装依赖
pip install -r requirements.txt

# 3. 开听！
python OpenMusic.py
```

### 方式二：打包成 EXE

双击 `build.bat` 一键打包，或者手动：

```bash
pip install pyinstaller
pyinstaller --onedir --windowed --name "OpenMusic" --add-data "Open Music.png;." OpenMusic.py
```

---

## 📁 项目结构

```
Open Music/
├── 🐍 OpenMusic.py          # 主程序源码
├── 🖼️ Open Music.png        # 程序图标
├── 🛠️ build.bat             # 一键打包脚本
├── 📦 requirements.txt      # Python 依赖
├── 📖 功能说明书.html         # 功能说明文档
└── 📂 dist/OpenMusic/       # 放你的音乐文件夹
```

---

## 🧰 技术栈

| 技术 | 用途 |
|------|------|
| **PySide6 (Qt6)** | 图形界面框架 |
| **pygame / SDL2_mixer** | 音频解码与播放 |
| **在线歌词 API** | 歌词同步 |
| **PyInstaller** | 打包为 EXE |
| **NumPy / Pillow** | 音频数据处理 / 封面渲染 |

---

## 📸 截图

> TODO: 添加截图

---

## 🎨 关于作者

**Hong** — 数字艺术家 & 业余开发者

- 🌐 作品集: [dl0722.github.io](https://dl0722.github.io)
- 🎵 收听歌单: 就在这个播放器里 😄

---

## 📄 License

MIT License — 随意使用，欢迎 Star ⭐
