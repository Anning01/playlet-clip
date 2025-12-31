"""
视频处理服务测试

测试 FFmpeg 视频处理功能:
1. 视频信息获取
2. 音频提取
3. 视频裁剪
4. 模糊效果 + 字幕
5. 视频拼接

运行方式:
    uv run pytest tests/test_04_video.py -v -s

    # 只测试特定功能
    uv run pytest tests/test_04_video.py -v -s -k "trim"
    uv run pytest tests/test_04_video.py -v -s -k "concat"

注意:
    - 需要安装 FFmpeg
    - 需要放置测试视频到 data/input/test.mp4
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from playlet_clip.core.config import VideoSettings
from playlet_clip.utils.ffmpeg import FFmpegProcessor


class TestFFmpegBasic:
    """FFmpeg 基础测试"""

    @pytest.fixture
    def video_settings(self) -> VideoSettings:
        """视频处理配置"""
        return VideoSettings(
            blur_height=185,
            blur_y=1413,
            subtitle_margin=65,
            blur_sigma=20,
            video_codec="libx264",
            audio_codec="aac",
            preset="fast",
        )

    @pytest.fixture
    def ffmpeg(self, video_settings: VideoSettings) -> FFmpegProcessor:
        """创建 FFmpeg 处理器"""
        return FFmpegProcessor(video_settings)

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_ffmpeg_available(self, ffmpeg: FFmpegProcessor):
        """测试 FFmpeg 是否可用"""
        assert ffmpeg.ffmpeg_path is not None
        print(f"✓ FFmpeg 可用: {ffmpeg.ffmpeg_path}")

    def test_ffprobe_available(self, ffmpeg: FFmpegProcessor):
        """测试 FFprobe 是否可用"""
        assert ffmpeg.ffprobe_path is not None
        print(f"✓ FFprobe 可用: {ffmpeg.ffprobe_path}")


class TestVideoInfo:
    """视频信息测试"""

    @pytest.fixture
    def ffmpeg(self) -> FFmpegProcessor:
        return FFmpegProcessor(VideoSettings())

    @pytest.mark.asyncio
    async def test_get_duration(self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None):
        """测试获取视频时长"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在，请放置 data/input/test.mp4")

        duration = await ffmpeg.get_duration(sample_video_path)

        assert duration > 0
        print(f"✓ 视频时长: {duration:.2f} 秒")

    @pytest.mark.asyncio
    async def test_get_video_info(self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None):
        """测试获取视频详细信息"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        # 使用 ffprobe 获取详细信息
        import subprocess
        import json

        cmd = [
            ffmpeg.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(sample_video_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)

        print(f"✓ 视频信息:")
        print(f"  - 格式: {info['format']['format_name']}")
        print(f"  - 时长: {float(info['format']['duration']):.2f}s")

        for stream in info["streams"]:
            if stream["codec_type"] == "video":
                print(f"  - 视频: {stream['width']}x{stream['height']} @ {stream['codec_name']}")
            elif stream["codec_type"] == "audio":
                print(f"  - 音频: {stream['sample_rate']}Hz @ {stream['codec_name']}")


class TestAudioExtraction:
    """音频提取测试"""

    @pytest.fixture
    def ffmpeg(self) -> FFmpegProcessor:
        return FFmpegProcessor(VideoSettings())

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_extract_audio(
        self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None, temp_dir: Path
    ):
        """测试音频提取"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        output_path = temp_dir / "extracted_audio.wav"

        print(f"\n从视频提取音频...")
        await ffmpeg.extract_audio(sample_video_path, output_path)

        assert output_path.exists()
        file_size = output_path.stat().st_size / 1024 / 1024  # MB
        print(f"✓ 音频提取成功:")
        print(f"  - 输出: {output_path}")
        print(f"  - 大小: {file_size:.2f} MB")


class TestVideoTrimming:
    """视频裁剪测试"""

    @pytest.fixture
    def ffmpeg(self) -> FFmpegProcessor:
        return FFmpegProcessor(VideoSettings())

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_trim_video(
        self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None, temp_dir: Path
    ):
        """测试视频裁剪"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        output_path = temp_dir / "trimmed.mp4"
        start_time = 0.0
        duration = 5.0

        print(f"\n裁剪视频: {start_time}s - {start_time + duration}s")
        await ffmpeg.trim(sample_video_path, start_time, duration, output_path)

        assert output_path.exists()

        # 验证输出时长
        actual_duration = await ffmpeg.get_duration(output_path)
        print(f"✓ 裁剪成功:")
        print(f"  - 目标时长: {duration}s")
        print(f"  - 实际时长: {actual_duration:.2f}s")

        # 允许 0.5 秒误差
        assert abs(actual_duration - duration) < 0.5

    @pytest.mark.asyncio
    async def test_trim_multiple_segments(
        self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None, temp_dir: Path
    ):
        """测试多段裁剪"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        video_duration = await ffmpeg.get_duration(sample_video_path)
        segments = [
            (0.0, 2.0),
            (3.0, 2.0),
            (6.0, 2.0),
        ]

        # 过滤掉超出视频长度的片段
        valid_segments = [(s, d) for s, d in segments if s + d <= video_duration]

        if not valid_segments:
            pytest.skip("视频太短，无法测试多段裁剪")

        print(f"\n裁剪多个片段:")
        trimmed_paths = []

        for i, (start, dur) in enumerate(valid_segments):
            output_path = temp_dir / f"segment_{i}.mp4"
            await ffmpeg.trim(sample_video_path, start, dur, output_path)
            trimmed_paths.append(output_path)
            print(f"  ✓ 片段 {i + 1}: {start}s - {start + dur}s")

        assert len(trimmed_paths) == len(valid_segments)
        print(f"✓ 成功裁剪 {len(trimmed_paths)} 个片段")


class TestVideoBlurAndSubtitle:
    """模糊效果和字幕测试"""

    @pytest.fixture
    def ffmpeg(self) -> FFmpegProcessor:
        return FFmpegProcessor(
            VideoSettings(
                blur_height=100,
                blur_y=500,
                blur_sigma=20,
            )
        )

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_srt(self, temp_dir: Path) -> Path:
        """创建示例字幕文件"""
        srt_path = temp_dir / "test.srt"
        srt_content = """1
00:00:00,000 --> 00:00:02,000
这是第一句字幕

2
00:00:02,000 --> 00:00:04,000
这是第二句字幕

3
00:00:04,000 --> 00:00:06,000
这是第三句字幕
"""
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        return srt_path

    @pytest.mark.asyncio
    async def test_add_blur_effect(
        self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None, temp_dir: Path
    ):
        """测试添加模糊效果"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        # 先裁剪一小段
        trimmed = temp_dir / "trimmed.mp4"
        await ffmpeg.trim(sample_video_path, 0, 3, trimmed)

        output_path = temp_dir / "blurred.mp4"

        print(f"\n添加模糊效果...")
        await ffmpeg.add_blur(trimmed, output_path)

        assert output_path.exists()
        print(f"✓ 模糊效果添加成功: {output_path}")

    @pytest.mark.asyncio
    async def test_add_subtitle(
        self,
        ffmpeg: FFmpegProcessor,
        sample_video_path: Path | None,
        temp_dir: Path,
        sample_srt: Path,
    ):
        """测试添加字幕"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        # 先裁剪一小段
        trimmed = temp_dir / "trimmed.mp4"
        await ffmpeg.trim(sample_video_path, 0, 6, trimmed)

        output_path = temp_dir / "subtitled.mp4"

        print(f"\n添加字幕...")
        await ffmpeg.add_subtitle(trimmed, sample_srt, output_path)

        assert output_path.exists()
        print(f"✓ 字幕添加成功: {output_path}")

    @pytest.mark.asyncio
    async def test_add_narration_with_blur_and_subtitle(
        self,
        ffmpeg: FFmpegProcessor,
        sample_video_path: Path | None,
        temp_dir: Path,
        sample_srt: Path,
    ):
        """测试完整流程：模糊 + 字幕 + 音频"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        # 先裁剪一小段
        trimmed = temp_dir / "trimmed.mp4"
        await ffmpeg.trim(sample_video_path, 0, 6, trimmed)

        output_path = temp_dir / "final.mp4"

        print(f"\n添加模糊和字幕...")

        # 先添加模糊
        blurred = temp_dir / "blurred.mp4"
        await ffmpeg.add_blur(trimmed, blurred)

        # 再添加字幕
        await ffmpeg.add_subtitle(blurred, sample_srt, output_path)

        assert output_path.exists()
        print(f"✓ 完整处理成功: {output_path}")


class TestVideoConcat:
    """视频拼接测试"""

    @pytest.fixture
    def ffmpeg(self) -> FFmpegProcessor:
        return FFmpegProcessor(VideoSettings())

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_concat_videos(
        self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None, temp_dir: Path
    ):
        """测试视频拼接"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        video_duration = await ffmpeg.get_duration(sample_video_path)
        if video_duration < 6:
            pytest.skip("测试视频太短")

        # 裁剪多个片段
        segments = []
        for i, (start, dur) in enumerate([(0, 2), (2, 2), (4, 2)]):
            if start + dur <= video_duration:
                seg_path = temp_dir / f"seg_{i}.mp4"
                await ffmpeg.trim(sample_video_path, start, dur, seg_path)
                segments.append(seg_path)

        if len(segments) < 2:
            pytest.skip("无法创建足够的片段")

        output_path = temp_dir / "concatenated.mp4"

        print(f"\n拼接 {len(segments)} 个视频片段...")
        await ffmpeg.concat(segments, output_path)

        assert output_path.exists()

        # 验证输出时长
        total_duration = await ffmpeg.get_duration(output_path)
        expected_duration = sum(2.0 for _ in segments)

        print(f"✓ 拼接成功:")
        print(f"  - 片段数: {len(segments)}")
        print(f"  - 期望时长: {expected_duration}s")
        print(f"  - 实际时长: {total_duration:.2f}s")

        # 拼接后时长应该接近各片段之和
        assert abs(total_duration - expected_duration) < 1.0

    @pytest.mark.asyncio
    async def test_concat_smooth_playback(
        self, ffmpeg: FFmpegProcessor, sample_video_path: Path | None, temp_dir: Path
    ):
        """测试拼接后播放流畅性（re-encode 模式）"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        video_duration = await ffmpeg.get_duration(sample_video_path)

        # 裁剪片段
        segments = []
        for i in range(3):
            start = i * 2
            if start + 2 <= video_duration:
                seg_path = temp_dir / f"seg_{i}.mp4"
                await ffmpeg.trim(sample_video_path, start, 2, seg_path)
                segments.append(seg_path)

        if len(segments) < 2:
            pytest.skip("视频太短")

        output_path = temp_dir / "smooth.mp4"

        print(f"\n测试流畅拼接 (re-encode 模式)...")
        await ffmpeg.concat(segments, output_path)

        assert output_path.exists()

        # 检查输出文件的 codec
        import subprocess
        import json

        cmd = [
            ffmpeg.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)

        video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio_stream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)

        print(f"✓ 拼接完成 (使用 re-encode):")
        print(f"  - 视频编码: {video_stream['codec_name']}")
        if audio_stream:
            print(f"  - 音频编码: {audio_stream['codec_name']}")


# 独立测试函数
def run_video_test():
    """独立运行视频处理测试"""
    print("=" * 50)
    print("视频处理服务测试")
    print("=" * 50)

    from playlet_clip.utils.ffmpeg import FFmpegProcessor
    from playlet_clip.core.config import VideoSettings

    # 创建处理器
    ffmpeg = FFmpegProcessor(VideoSettings())
    print(f"✓ FFmpeg: {ffmpeg.ffmpeg_path}")
    print(f"✓ FFprobe: {ffmpeg.ffprobe_path}")

    # 检查测试视频
    test_video = Path("data/input/test.mp4")
    if not test_video.exists():
        print("\n⚠ 测试视频不存在")
        print("  请放置视频文件到 data/input/test.mp4")
        return

    # 获取时长
    duration = asyncio.run(ffmpeg.get_duration(test_video))
    print(f"\n测试视频: {test_video}")
    print(f"  - 时长: {duration:.2f}s")

    # 裁剪测试
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "trimmed.mp4"
        print(f"\n裁剪视频 (0-3s)...")
        asyncio.run(ffmpeg.trim(test_video, 0, 3, output))
        print(f"✓ 裁剪成功: {output}")

        # 拼接测试
        seg1 = Path(tmpdir) / "seg1.mp4"
        seg2 = Path(tmpdir) / "seg2.mp4"
        asyncio.run(ffmpeg.trim(test_video, 0, 2, seg1))
        asyncio.run(ffmpeg.trim(test_video, 2, 2, seg2))

        concat_output = Path(tmpdir) / "concat.mp4"
        print(f"\n拼接视频...")
        asyncio.run(ffmpeg.concat([seg1, seg2], concat_output))
        print(f"✓ 拼接成功: {concat_output}")


if __name__ == "__main__":
    run_video_test()
