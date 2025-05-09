# Playlet-Clip 短剧自动化剪辑工具

## 项目简介

Playlet-Clip 是一个基于AI的短剧自动化剪辑工具，能够根据原始视频和字幕文件，自动生成带有解说的短视频。该工具利用ChatGPT生成解说文案，使用Edge TTS将文字转换为语音，并通过FFmpeg进行视频剪辑和合成，实现全自动化的短剧二次创作。

## 功能特点

- **AI解说生成**：利用ChatGPT根据字幕内容和指定风格自动生成解说文案
- **文字转语音**：使用Edge TTS将解说文案转换为自然流畅的语音
- **视频智能剪辑**：自动截取视频片段，添加解说音频和字幕
- **模糊字幕区域**：自动为字幕区域添加模糊效果，提升视觉体验
- **支持多种风格**：可配置多种解说风格，如讽刺风格等
- **分布式处理**：支持服务器-客户端模式，实现多机协同处理任务

## 系统要求

- Python 3.6+
- FFmpeg（用于视频处理）
- 网络连接（用于AI接口调用）

## 安装步骤

1. 克隆仓库到本地

```bash
git clone https://github.com/yourusername/playlet-clip.git
cd playlet-clip
```

2. 安装依赖

```bash
# 安装服务端依赖
pip install -r requirements.txt

# 如果只需要客户端功能
pip install -r client_requirements.txt
```

3. 配置参数

编辑 `conf.py` 文件，设置以下参数：

```python
# ChatGPT API key 支持本地和各类国内代理商
api_key = "your_api_key"
# ChatGPT API 请求路由
base_url = "your_base_url"
# 模型
model = "gpt-4o"
# 声音
voice = "zh-CN-YunxiNeural"
# 语速
rate = "+30%"
# 音量
volume = "+100%"
# 蒙版高度
blur_height = 185
# 蒙版位置
blur_y = 1413
# 字幕位置
MarginV = 65
# 粒子特效目录（可选）
lz_path = None
```

## 使用方法

### 单机模式

1. 编辑 `conf.py` 文件，设置视频和字幕路径：

```python
# 单个视频路径
video_path = "path/to/your/video.mp4"
# 单个srt路径
srt_path = "path/to/your/subtitle.srt"
```

2. 运行主程序：

```bash
python main.py
```

### 服务器-客户端模式

1. 启动服务器：

```bash
python server.py
```

2. 创建任务：

```bash
python create_task.py --directory "path/to/videos" --blur_height 185 --blur_y 1413 --MarginV 65
```

3. 启动客户端处理任务：

```bash
python manage_tasks.py --server "http://server_ip:8000"
```

## 自定义风格

在 `conf.py` 文件中，可以自定义解说风格：

```python
style_list = [
    "讽刺风格：通过讽刺和夸张的手法来评论剧中的不合理或过于狗血的情节，让观众在笑声中进行思考。",
    # 添加更多风格...
]
```

## API接口

服务器提供以下API接口：

- `POST /tasks/`：创建新任务
- `GET /tasks/next`：获取下一个待处理任务
- `POST /tasks/{task_id}/update`：更新任务状态
- `GET /config`：获取服务器配置

## 工作流程

1. 解析字幕文件和视频文件
2. 使用ChatGPT生成解说文案
3. 使用Edge TTS将解说转换为语音
4. 截取视频片段并添加解说
5. 合成最终视频

## 常见问题

**Q: 如何调整字幕位置和模糊效果？**

A: 在 `conf.py` 或创建任务时设置 `blur_height`、`blur_y` 和 `MarginV` 参数。

**Q: 支持哪些语音？**

A: 支持Edge TTS提供的所有语音，默认使用 `zh-CN-YunxiNeural`。

## 许可证

[MIT License](LICENSE)

## 作者

- anning (anningforchina@gmail.com)
