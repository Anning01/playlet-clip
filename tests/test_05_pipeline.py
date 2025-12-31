"""
完整 Pipeline 测试

测试完整的视频处理流程:
1. ASR 字幕提取
2. LLM 解说生成
3. TTS 语音合成
4. 视频剪辑合成

运行方式:
    uv run pytest tests/test_05_pipeline.py -v -s

注意:
    - 需要配置 OPENAI_API_KEY
    - 需要放置测试视频到 data/input/test.mp4
    - 完整测试需要所有服务可用
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from playlet_clip.core.config import (
    ASRSettings,
    LLMSettings,
    PathSettings,
    Settings,
    TTSSettings,
    VideoSettings,
)
from playlet_clip.core.pipeline import PlayletPipeline
from playlet_clip.models.task import TaskStatus


class TestPipelineCreation:
    """Pipeline 创建测试"""

    @pytest.fixture
    def settings(self) -> Settings:
        """测试配置"""
        api_key = os.environ.get("OPENAI_API_KEY", "test-key")

        return Settings(
            llm=LLMSettings(api_key=api_key),
            asr=ASRSettings(device="cpu"),
            tts=TTSSettings(backend="edge_tts"),
            video=VideoSettings(),
            paths=PathSettings(),
            debug=True,
        )

    def test_pipeline_creation(self, settings: Settings):
        """测试 Pipeline 创建"""
        pipeline = PlayletPipeline(settings)

        assert pipeline is not None
        assert pipeline.asr_service is not None
        assert pipeline.tts_service is not None
        assert pipeline.llm_service is not None
        assert pipeline.ffmpeg is not None

        print(f"✓ Pipeline 创建成功")
        print(f"  - ASR: {pipeline.asr_service.config.device}")
        print(f"  - TTS: {pipeline.tts_service.config.backend}")
        print(f"  - LLM: {pipeline.llm_service.config.model}")


class TestPipelineSteps:
    """Pipeline 各步骤测试"""

    @pytest.fixture
    def pipeline(self) -> PlayletPipeline:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            pytest.skip("OPENAI_API_KEY 未配置")

        settings = Settings(
            llm=LLMSettings(api_key=api_key),
            asr=ASRSettings(device="cpu"),
            tts=TTSSettings(backend="edge_tts"),
            video=VideoSettings(),
        )
        return PlayletPipeline(settings)

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_step1_asr(self, pipeline: PlayletPipeline, sample_video_path: Path | None):
        """Step 1: ASR 字幕提取"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        print("\n=== Step 1: ASR 字幕提取 ===")

        subtitles = await pipeline.asr_service.transcribe(sample_video_path)

        assert len(subtitles) > 0
        print(f"✓ 提取 {len(subtitles)} 条字幕:")
        for s in subtitles[:3]:
            print(f"  [{s.start_time:.1f}s] {s.text}")

    @pytest.mark.asyncio
    async def test_step2_llm(self, pipeline: PlayletPipeline):
        """Step 2: LLM 解说生成"""
        from playlet_clip.models.subtitle import SubtitleSegment

        print("\n=== Step 2: LLM 解说生成 ===")

        # 模拟字幕
        subtitles = [
            SubtitleSegment(index=1, start_time=0.0, end_time=5.0, text="女主角走进办公室"),
            SubtitleSegment(index=2, start_time=5.0, end_time=10.0, text="男主角说你终于来了"),
        ]

        narrations = await pipeline.llm_service.generate_narration(
            subtitles=subtitles,
            video_duration=10.0,
            style_name="讽刺风格",
            style_description="通过讽刺和夸张的手法来评论剧情",
        )

        assert len(narrations) > 0
        print(f"✓ 生成 {len(narrations)} 条解说:")
        for n in narrations:
            print(f"  [{n.start_time:.1f}s - {n.end_time:.1f}s] {n.text}")

    @pytest.mark.asyncio
    async def test_step3_tts(self, pipeline: PlayletPipeline, temp_dir: Path):
        """Step 3: TTS 语音合成"""
        print("\n=== Step 3: TTS 语音合成 ===")

        text = "这是一段测试解说，用于验证语音合成功能。"
        output_path = temp_dir / "narration"

        result = await pipeline.tts_service.synthesize(
            text=text,
            output_path=output_path,
            generate_subtitle=True,
        )

        assert result.audio_path.exists()
        print(f"✓ 语音合成成功:")
        print(f"  - 音频: {result.audio_path}")
        print(f"  - 时长: {result.duration:.2f}s")

    @pytest.mark.asyncio
    async def test_step4_video(
        self, pipeline: PlayletPipeline, sample_video_path: Path | None, temp_dir: Path
    ):
        """Step 4: 视频处理"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        print("\n=== Step 4: 视频处理 ===")

        # 裁剪
        trimmed = temp_dir / "trimmed.mp4"
        await pipeline.ffmpeg.trim(sample_video_path, 0, 5, trimmed)
        print(f"✓ 视频裁剪成功: {trimmed}")

        # 模糊
        blurred = temp_dir / "blurred.mp4"
        await pipeline.ffmpeg.add_blur(trimmed, blurred)
        print(f"✓ 模糊效果添加成功: {blurred}")


class TestFullPipeline:
    """完整 Pipeline 测试"""

    @pytest.fixture
    def temp_output_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_full_pipeline_with_video(
        self, sample_video_path: Path | None, temp_output_dir: Path
    ):
        """测试完整处理流程"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            pytest.skip("OPENAI_API_KEY 未配置")

        print("\n" + "=" * 50)
        print("完整 Pipeline 测试")
        print("=" * 50)

        settings = Settings(
            llm=LLMSettings(api_key=api_key),
            asr=ASRSettings(device="cpu"),
            tts=TTSSettings(backend="edge_tts"),
            video=VideoSettings(),
            paths=PathSettings(
                output_dir=temp_output_dir,
                temp_dir=temp_output_dir / "temp",
            ),
        )

        pipeline = PlayletPipeline(settings)
        output_path = temp_output_dir / "final_output.mp4"

        progress_log = []

        def on_progress(progress: float, message: str):
            progress_log.append((progress, message))
            print(f"  [{progress:5.1f}%] {message}")

        print(f"\n处理视频: {sample_video_path}")
        print(f"输出路径: {output_path}\n")

        result = await pipeline.process(
            video_path=sample_video_path,
            output_path=output_path,
            style_name="讽刺风格",
            progress_callback=on_progress,
        )

        print(f"\n处理结果:")
        print(f"  - 状态: {result.status}")

        if result.status == TaskStatus.COMPLETED:
            print(f"  - 输出: {result.output_path}")
            print(f"  - 时长: {result.duration:.2f}s")
            print(f"  - 片段数: {result.segments_count}")
            assert result.output_path.exists()
        else:
            print(f"  - 错误: {result.error_message}")
            pytest.fail(f"处理失败: {result.error_message}")

    @pytest.mark.asyncio
    async def test_pipeline_with_srt_file(
        self, sample_video_path: Path | None, temp_output_dir: Path
    ):
        """测试使用外部 SRT 文件"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            pytest.skip("OPENAI_API_KEY 未配置")

        # 创建测试 SRT 文件
        srt_path = temp_output_dir / "test.srt"
        srt_content = """1
00:00:00,000 --> 00:00:05,000
这是手动提供的第一句字幕

2
00:00:05,000 --> 00:00:10,000
这是手动提供的第二句字幕
"""
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        print("\n" + "=" * 50)
        print("使用外部 SRT 文件测试")
        print("=" * 50)

        settings = Settings(
            llm=LLMSettings(api_key=api_key),
            tts=TTSSettings(backend="edge_tts"),
            video=VideoSettings(),
            paths=PathSettings(
                output_dir=temp_output_dir,
                temp_dir=temp_output_dir / "temp",
            ),
        )

        pipeline = PlayletPipeline(settings)
        output_path = temp_output_dir / "output_with_srt.mp4"

        def on_progress(progress: float, message: str):
            print(f"  [{progress:5.1f}%] {message}")

        result = await pipeline.process(
            video_path=sample_video_path,
            output_path=output_path,
            style_name="讽刺风格",
            srt_path=srt_path,  # 使用外部 SRT
            progress_callback=on_progress,
        )

        print(f"\n处理结果: {result.status}")
        if result.status == TaskStatus.COMPLETED:
            print(f"  ✓ 成功: {result.output_path}")
        else:
            print(f"  ✗ 失败: {result.error_message}")


class TestPipelineErrorHandling:
    """Pipeline 错误处理测试"""

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_missing_video(self, temp_dir: Path):
        """测试视频不存在的情况"""
        settings = Settings(
            llm=LLMSettings(api_key="test"),
            tts=TTSSettings(backend="edge_tts"),
        )
        pipeline = PlayletPipeline(settings)

        result = await pipeline.process(
            video_path=Path("/nonexistent/video.mp4"),
            output_path=temp_dir / "output.mp4",
            style_name="讽刺风格",
        )

        assert result.status == TaskStatus.FAILED
        print(f"✓ 正确处理不存在的视频: {result.error_message}")

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, sample_video_path: Path | None, temp_dir: Path):
        """测试无效 API Key 的情况"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        settings = Settings(
            llm=LLMSettings(api_key="invalid-key"),
            asr=ASRSettings(device="cpu"),
            tts=TTSSettings(backend="edge_tts"),
        )
        pipeline = PlayletPipeline(settings)

        result = await pipeline.process(
            video_path=sample_video_path,
            output_path=temp_dir / "output.mp4",
            style_name="讽刺风格",
        )

        # 应该在 LLM 步骤失败
        assert result.status == TaskStatus.FAILED
        print(f"✓ 正确处理无效 API Key: {result.error_message}")


# 独立测试函数
def run_pipeline_test():
    """独立运行 Pipeline 测试"""
    print("=" * 50)
    print("Pipeline 完整测试")
    print("=" * 50)

    # 检查配置
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("✗ OPENAI_API_KEY 未配置")
        return

    # 检查测试视频
    test_video = Path("data/input/test.mp4")
    if not test_video.exists():
        print("✗ 测试视频不存在: data/input/test.mp4")
        return

    print(f"✓ API Key 已配置")
    print(f"✓ 测试视频: {test_video}")

    # 创建 Pipeline
    from playlet_clip.core.config import Settings

    settings = Settings(
        llm=LLMSettings(api_key=api_key),
        asr=ASRSettings(device="cpu"),
        tts=TTSSettings(backend="edge_tts"),
    )

    pipeline = PlayletPipeline(settings)
    print(f"✓ Pipeline 创建成功")

    # 运行完整测试
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "output.mp4"

        def on_progress(progress: float, message: str):
            print(f"  [{progress:5.1f}%] {message}")

        print(f"\n开始处理...")

        result = asyncio.run(
            pipeline.process(
                video_path=test_video,
                output_path=output_path,
                style_name="讽刺风格",
                progress_callback=on_progress,
            )
        )

        print(f"\n处理结果: {result.status}")
        if result.status == TaskStatus.COMPLETED:
            print(f"  ✓ 输出: {result.output_path}")
            print(f"  ✓ 时长: {result.duration:.2f}s")
        else:
            print(f"  ✗ 错误: {result.error_message}")


if __name__ == "__main__":
    run_pipeline_test()
