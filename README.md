# Open Music by Hong 🎵

一个基于 PySide6 和 pygame 的本地音乐播放器，支持多歌单管理、在线歌词、均衡器等功能。

## 功能特性

- 本地音乐扫描与播放
- 多歌单管理
- 在线歌词同步
- 均衡器调节
- 专辑封面显示
- 播放队列管理
- 快捷键支持

## 快速开始

### 方式一：直接运行源码

`ash
# 1. 安装 Python 3.8+
# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python OpenMusic.py
`

### 方式二：打包为 EXE

双击运行 uild.bat，会自动安装依赖并打包。

或手动执行：
`ash
pip install pyinstaller
pyinstaller --onedir --windowed --name "OpenMusic" --add-data "Open Music.png;." OpenMusic.py
`

## 项目结构

`
OpenMusic-GitHub/
├── OpenMusic.py          # 主程序源码
├── Open Music.png        # 程序图标
├── build.bat             # 一键打包脚本
├── requirements.txt      # Python 依赖
├── 功能说明书.html         # 功能说明文档
├── dist/OpenMusic/       # 音乐文件夹（自行放入歌曲）
└── README.md
`

## 技术栈

- **UI**: PySide6 (Qt6)
- **音频**: pygame / SDL2_mixer
- **歌词**: 在线 API
- **打包**: PyInstaller

## License

MIT
