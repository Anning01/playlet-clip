"""Gradio application main entry."""

import asyncio
from pathlib import Path
from typing import Generator

import gradio as gr
from loguru import logger

from playlet_clip.core.config import Settings, get_settings
from playlet_clip.core.pipeline import PlayletPipeline
from playlet_clip.models.task import TaskProgress, TaskStatus
from playlet_clip.services.tts import TTSService


def _format_error(title: str, detail: str | None) -> str:
    """Format error message as HTML for display."""
    import html

    title_escaped = html.escape(str(title)) if title else "未知错误"
    detail_escaped = html.escape(str(detail)) if detail else ""

    return f"""
    <div class="error-box">
        <h4 style="margin: 0 0 8px 0; color: #dc2626;">❌ {title_escaped}</h4>
        <pre style="margin: 0; color: #7f1d1d;">{detail_escaped}</pre>
    </div>
    """


def create_app(settings: Settings | None = None) -> gr.Blocks:
    """
    Create the Gradio application.

    Args:
        settings: Application settings (optional, loads default if not provided)

    Returns:
        Gradio Blocks application
    """
    if settings is None:
        settings = get_settings()

    # Initialize pipeline
    pipeline = PlayletPipeline(settings)

    # Get available styles
    style_choices = [s.name for s in settings.styles]

    # Get available voices
    voice_choices = TTSService.PRESET_VOICES

    # Custom CSS
    css = """
    .progress-container {
        margin: 10px 0;
    }
    .video-container video {
        max-height: 45vh !important;
        width: 100%;
        object-fit: contain;
    }
    .error-box {
        background-color: #fee2e2;
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 12px;
        margin-top: 10px;
    }
    .error-box pre {
        white-space: pre-wrap;
        word-wrap: break-word;
        font-size: 12px;
        max-height: 300px;
        overflow-y: auto;
    }
    """

    with gr.Blocks(
        title="Playlet-Clip - AI短剧自动剪辑",
        theme=gr.themes.Soft(),
        css=css,
    ) as app:
        # Header
        gr.Markdown(
            """
            # 🎬 Playlet-Clip
            ### AI驱动的短剧自动化剪辑工具

            上传视频 → ASR提取字幕 → AI生成解说 → TTS合成语音 → 自动剪辑成片
            """
        )

        with gr.Tabs():
            # Tab 1: Video Processing
            with gr.Tab("视频处理", id="process"):
                with gr.Row():
                    # Left column: Input
                    with gr.Column(scale=1):
                        video_input = gr.Video(
                            label="上传视频",
                            sources=["upload"],
                            elem_classes=["video-container"],
                        )

                        style_dropdown = gr.Dropdown(
                            choices=style_choices,
                            value=style_choices[0] if style_choices else None,
                            label="解说风格",
                        )

                        with gr.Accordion("高级设置", open=False):
                            voice_dropdown = gr.Dropdown(
                                choices=voice_choices,
                                value=settings.tts.default_voice,
                                label="解说音色",
                            )

                            blur_height = gr.Slider(
                                minimum=0,
                                maximum=500,
                                value=settings.video.blur_height,
                                step=5,
                                label="字幕模糊区域高度 (像素)",
                            )

                            blur_y = gr.Slider(
                                minimum=0,
                                maximum=2000,
                                value=settings.video.blur_y,
                                step=10,
                                label="字幕模糊区域位置 (像素)",
                            )

                            subtitle_margin = gr.Slider(
                                minimum=0,
                                maximum=200,
                                value=settings.video.subtitle_margin,
                                step=5,
                                label="字幕边距 (像素)",
                            )

                        # Optional existing subtitles
                        with gr.Accordion("使用已有字幕 (可选)", open=False):
                            srt_input = gr.File(
                                label="上传SRT字幕文件",
                                file_types=[".srt"],
                            )
                            gr.Markdown("*如果上传字幕文件，将跳过ASR语音识别步骤*")

                        process_btn = gr.Button("🚀 开始处理", variant="primary", size="lg")

                    # Right column: Output
                    with gr.Column(scale=1):
                        # Progress display
                        progress_text = gr.Textbox(
                            label="处理状态",
                            value="等待开始...",
                            interactive=False,
                        )
                        progress_bar = gr.Slider(
                            minimum=0,
                            maximum=100,
                            value=0,
                            label="进度",
                            interactive=False,
                        )

                        # Output video
                        output_video = gr.Video(
                            label="处理结果",
                            elem_classes=["video-container"],
                        )

                        # Download button
                        download_file = gr.File(
                            label="下载视频",
                            visible=False,
                        )

                        # Error display
                        error_output = gr.HTML(
                            label="错误信息",
                            visible=False,
                            elem_classes=["error-box"],
                        )

            # Tab 2: Settings
            with gr.Tab("设置", id="settings"):
                gr.Markdown("### API 配置")

                with gr.Row():
                    api_key_input = gr.Textbox(
                        label="OpenAI API Key",
                        value=settings.llm.api_key[:10] + "..." if settings.llm.api_key else "",
                        type="password",
                        placeholder="sk-...",
                    )

                    base_url_input = gr.Textbox(
                        label="API Base URL",
                        value=settings.llm.base_url,
                        placeholder="https://api.openai.com/v1",
                    )

                model_input = gr.Textbox(
                    label="模型名称",
                    value=settings.llm.model,
                    placeholder="gpt-4o",
                )

                save_settings_btn = gr.Button("保存设置", variant="secondary")
                settings_status = gr.Textbox(
                    label="状态",
                    value="",
                    interactive=False,
                )

                gr.Markdown("---")
                gr.Markdown("### 解说风格管理")

                styles_display = gr.Dataframe(
                    headers=["名称", "描述"],
                    value=[[s.name, s.description] for s in settings.styles],
                    label="当前风格列表",
                )

            # Tab 3: Voice Management
            with gr.Tab("音色管理", id="voices"):
                gr.Markdown("### 可用音色")

                voices_display = gr.Dataframe(
                    headers=["音色名称"],
                    value=[[v] for v in voice_choices],
                    label="预设音色",
                )

                gr.Markdown("---")
                gr.Markdown("### 音色克隆 (实验性)")

                with gr.Row():
                    clone_audio = gr.Audio(
                        label="上传参考音频",
                        type="filepath",
                    )
                    clone_text = gr.Textbox(
                        label="参考音频文本",
                        placeholder="请输入参考音频中说的话...",
                    )

                clone_name = gr.Textbox(
                    label="新音色名称",
                    placeholder="我的自定义音色",
                )

                clone_btn = gr.Button("克隆音色", variant="secondary")
                clone_status = gr.Textbox(
                    label="克隆状态",
                    value="",
                    interactive=False,
                )

            # Tab 4: About
            with gr.Tab("关于", id="about"):
                gr.Markdown(
                    """
                    ## Playlet-Clip v2.0

                    AI驱动的短剧自动化剪辑工具

                    ### 功能特点
                    - 🎤 **ASR语音识别**: 使用FunASR自动提取视频字幕
                    - 🤖 **AI解说生成**: 使用ChatGPT根据字幕生成解说文案
                    - 🔊 **TTS语音合成**: 使用CosyVoice合成自然的解说语音
                    - 🎬 **自动视频剪辑**: 智能剪辑合成最终视频

                    ### 技术栈
                    - Python 3.10+
                    - FunASR (语音识别)
                    - CosyVoice (语音合成)
                    - OpenAI API (解说生成)
                    - FFmpeg (视频处理)
                    - Gradio (Web界面)

                    ### 作者
                    - anning (anningforchina@gmail.com)

                    ### 开源协议
                    MIT License
                    """
                )

        # Event handlers
        async def process_video(
            video_path: str,
            style: str,
            voice: str,
            blur_h: int,
            blur_y_val: int,
            margin: int,
            srt_file: str | None,
        ) -> Generator:
            """Process video with progress updates."""
            if not video_path:
                error_html = _format_error("输入错误", "请上传视频文件")
                yield (
                    "请先上传视频",
                    0,
                    None,
                    gr.update(visible=False),
                    gr.update(visible=True, value=error_html),
                )
                return

            # Update settings with UI values
            settings.video.blur_height = blur_h
            settings.video.blur_y = blur_y_val
            settings.video.subtitle_margin = margin
            settings.tts.default_voice = voice

            video_file = Path(video_path)
            srt_path = Path(srt_file) if srt_file else None

            progress_updates = []

            def progress_callback(progress: TaskProgress):
                progress_updates.append(progress)

            try:
                # Start processing in background
                if srt_path and srt_path.exists():
                    # Use existing subtitles
                    task = pipeline.process_with_existing_subtitles(
                        video_path=video_file,
                        srt_path=srt_path,
                        style=style,
                        progress_callback=progress_callback,
                    )
                else:
                    # Full pipeline with ASR
                    task = pipeline.process(
                        video_path=video_file,
                        style=style,
                        progress_callback=progress_callback,
                    )

                # Create task
                loop = asyncio.get_event_loop()
                future = asyncio.ensure_future(task)

                # Poll for progress updates
                while not future.done():
                    await asyncio.sleep(0.5)

                    if progress_updates:
                        latest = progress_updates[-1]
                        status_text = f"[{latest.status.value}] {latest.message}"
                        yield (
                            status_text,
                            latest.progress,
                            None,
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )

                # Get result
                result = await future

                if result.success:
                    yield (
                        f"✅ 处理完成! 耗时: {result.duration:.1f}秒, 片段数: {result.segments_count}",
                        100,
                        str(result.output_path),
                        gr.update(visible=True, value=str(result.output_path)),
                        gr.update(visible=False),
                    )
                else:
                    error_html = _format_error("处理失败", result.error_message)
                    yield (
                        f"❌ 处理失败",
                        0,
                        None,
                        gr.update(visible=False),
                        gr.update(visible=True, value=error_html),
                    )

            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                error_html = _format_error(str(e), error_detail)
                logger.exception(f"Processing error: {e}")
                yield (
                    "❌ 处理出错",
                    0,
                    None,
                    gr.update(visible=False),
                    gr.update(visible=True, value=error_html),
                )

        def save_api_settings(api_key: str, base_url: str, model: str) -> str:
            """Save API settings."""
            try:
                if api_key and not api_key.endswith("..."):
                    settings.llm.api_key = api_key
                if base_url:
                    settings.llm.base_url = base_url
                if model:
                    settings.llm.model = model

                # Save to config file
                config_path = settings.paths.config_dir / "config.yaml"
                settings.to_yaml(config_path)

                return f"✅ 设置已保存到 {config_path}"
            except Exception as e:
                return f"❌ 保存失败: {e}"

        # Connect events
        process_btn.click(
            fn=process_video,
            inputs=[
                video_input,
                style_dropdown,
                voice_dropdown,
                blur_height,
                blur_y,
                subtitle_margin,
                srt_input,
            ],
            outputs=[
                progress_text,
                progress_bar,
                output_video,
                download_file,
                error_output,
            ],
        )

        save_settings_btn.click(
            fn=save_api_settings,
            inputs=[api_key_input, base_url_input, model_input],
            outputs=[settings_status],
        )

    return app


def launch_app(
    settings: Settings | None = None,
    share: bool = False,
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
) -> None:
    """
    Launch the Gradio application.

    Args:
        settings: Application settings
        share: Enable Gradio share link
        server_name: Server host
        server_port: Server port
    """
    if settings is None:
        settings = get_settings()

    app = create_app(settings)

    logger.info(f"Launching Gradio app on {server_name}:{server_port}")

    app.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        show_error=True,
    )
