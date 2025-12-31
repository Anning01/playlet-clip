"""
视频剪辑流程测试

测试完整的视频剪辑逻辑:
1. 解说片段: 裁剪视频 + TTS音频替换 + 字幕
2. 视频片段: 直接裁剪保留原音频
3. 拼接所有片段

运行方式:
    uv run pytest tests/test_06_editing.py -v -s

    # 只测试特定功能
    uv run pytest tests/test_06_editing.py -v -s -k "narration"
    uv run pytest tests/test_06_editing.py -v -s -k "full"
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from playlet_clip.core.config import TTSSettings, VideoSettings
from playlet_clip.models.segment import NarrationSegment
from playlet_clip.services.tts import TTSService
from playlet_clip.services.video import VideoService


class TestSegmentParsing:
    """测试 LLM 返回的片段解析"""

    def test_parse_narration_segment(self):
        """测试解说片段解析"""
        data = {
            "type": "解说",
            "content": "这个女人刚回家，就掉进死亡陷阱",
            "time": "00:00:00,000 --> 00:00:03,000"
        }

        segment = NarrationSegment.from_llm_response(data)

        assert segment.type == "解说"
        assert segment.content == "这个女人刚回家，就掉进死亡陷阱"
        assert segment.start_time == 0.0
        assert segment.end_time == 3.0
        assert segment.is_narration is True
        print(f"✓ 解说片段: [{segment.start_time}s - {segment.end_time}s] {segment.content}")

    def test_parse_video_segment(self):
        """测试视频片段解析"""
        data = {
            "type": "video",
            "time": "00:00:03,000 --> 00:00:11,089"
        }

        segment = NarrationSegment.from_llm_response(data)

        assert segment.type == "video"
        assert segment.content is None
        assert segment.start_time == 3.0
        assert abs(segment.end_time - 11.089) < 0.001
        assert segment.is_narration is False
        print(f"✓ 视频片段: [{segment.start_time}s - {segment.end_time}s]")

    def test_parse_full_response(self):
        """测试完整的 LLM 响应解析"""
        llm_response = [
            {
                "type": "解说",
                "content": "这个女人刚回家，就掉进死亡陷阱",
                "time": "00:00:00,000 --> 00:00:03,000"
            },
            {
                "type": "video",
                "time": "00:00:03,000 --> 00:00:11,089"
            },
            {
                "type": "解说",
                "content": "大哥的愤怒，藏着不为人知的秘密",
                "time": "00:01:00,360 --> 00:01:03,360"
            },
            {
                "type": "video",
                "time": "00:01:03,360 --> 00:01:15,140"
            },
        ]

        segments = [NarrationSegment.from_llm_response(d) for d in llm_response]

        assert len(segments) == 4
        assert segments[0].is_narration is True
        assert segments[1].is_narration is False
        assert segments[2].is_narration is True
        assert segments[3].is_narration is False

        print(f"✓ 解析 {len(segments)} 个片段:")
        for i, seg in enumerate(segments):
            seg_type = "解说" if seg.is_narration else "视频"
            print(f"  [{i+1}] {seg_type}: {seg.start_time:.2f}s - {seg.end_time:.2f}s")


class TestGapFilling:
    """测试间隔填充逻辑"""

    @pytest.fixture
    def llm_service(self):
        from playlet_clip.core.config import LLMSettings
        from playlet_clip.services.llm import LLMService
        return LLMService(LLMSettings(api_key="test"))

    def test_fill_gaps_basic(self, llm_service):
        """测试基本间隔填充"""
        # 模拟有间隔的片段
        segments = [
            NarrationSegment(type="解说", content="测试", start_time=0, end_time=3),
            NarrationSegment(type="video", start_time=3, end_time=11),
            # 间隔: 11s - 60s
            NarrationSegment(type="解说", content="测试2", start_time=60, end_time=63),
            NarrationSegment(type="video", start_time=63, end_time=75),
        ]

        video_duration = 100.0

        filled = llm_service.fill_gaps(segments, video_duration)

        print(f"\n原始片段: {len(segments)} 个")
        print(f"填充后: {len(filled)} 个")

        for i, seg in enumerate(filled):
            seg_type = "解说" if seg.is_narration else "视频"
            content = f" '{seg.content}'" if seg.content else ""
            print(f"  [{i+1}] {seg_type}: {seg.start_time:.2f}s - {seg.end_time:.2f}s{content}")

        # 应该填充 11-60s 的间隔和 75-100s 的间隔
        assert len(filled) > len(segments)

        # 验证连续性
        prev_end = 0.0
        for seg in filled:
            assert seg.start_time >= prev_end - 0.5, f"Gap at {prev_end}s - {seg.start_time}s"
            prev_end = seg.end_time

        # 验证覆盖到视频末尾
        assert filled[-1].end_time >= video_duration - 0.5

        print(f"✓ 间隔填充正确，覆盖 0s - {video_duration}s")

    def test_fill_gaps_no_gaps(self, llm_service):
        """测试无间隔的情况"""
        segments = [
            NarrationSegment(type="解说", content="测试", start_time=0, end_time=5),
            NarrationSegment(type="video", start_time=5, end_time=10),
        ]

        video_duration = 10.0
        filled = llm_service.fill_gaps(segments, video_duration)

        # 无间隔时应该保持原样
        assert len(filled) == len(segments)
        print(f"✓ 无间隔时保持原样: {len(filled)} 个片段")

    def test_fill_gaps_start_gap(self, llm_service):
        """测试开头有间隔的情况"""
        segments = [
            NarrationSegment(type="解说", content="测试", start_time=5, end_time=8),
            NarrationSegment(type="video", start_time=8, end_time=15),
        ]

        video_duration = 15.0
        filled = llm_service.fill_gaps(segments, video_duration)

        # 应该在开头填充 0-5s
        assert filled[0].start_time == 0.0
        assert filled[0].end_time == 5.0
        assert filled[0].type == "video"
        print(f"✓ 开头间隔已填充: 0s - 5s")

    def test_fill_real_llm_response(self, llm_service):
        """测试真实 LLM 响应的间隔填充"""
        # 模拟真实的 LLM 返回（有较大间隔）
        llm_response = [
            {"type": "解说", "content": "这个女人刚回家，就掉进死亡陷阱", "time": "00:00:00,000 --> 00:00:03,000"},
            {"type": "video", "time": "00:00:03,000 --> 00:00:11,089"},
            {"type": "解说", "content": "大哥的愤怒，藏着不为人知的秘密", "time": "00:01:00,360 --> 00:01:03,360"},
            {"type": "video", "time": "00:01:03,360 --> 00:01:15,140"},
            {"type": "解说", "content": "养女的眼泪，竟是致命毒计的伪装", "time": "00:01:28,000 --> 00:01:32,000"},
            {"type": "video", "time": "00:01:32,000 --> 00:01:49,480"},
            {"type": "解说", "content": "她发现自己在小说里，结局注定惨死", "time": "00:02:54,880 --> 00:02:58,880"},
            {"type": "video", "time": "00:02:58,880 --> 00:03:37,509"},
            {"type": "video", "time": "00:03:37,509 --> 00:04:07,892"},
        ]

        segments = [NarrationSegment.from_llm_response(d) for d in llm_response]
        video_duration = 250.0  # 约4分钟

        print(f"\n原始片段:")
        for i, seg in enumerate(segments):
            seg_type = "解说" if seg.is_narration else "视频"
            print(f"  [{i+1}] {seg_type}: {seg.start_time:.2f}s - {seg.end_time:.2f}s")

        filled = llm_service.fill_gaps(segments, video_duration)

        print(f"\n填充后片段 ({len(filled)} 个):")
        total_duration = 0
        for i, seg in enumerate(filled):
            seg_type = "解说" if seg.is_narration else "视频"
            duration = seg.end_time - seg.start_time
            total_duration += duration
            print(f"  [{i+1}] {seg_type}: {seg.start_time:.2f}s - {seg.end_time:.2f}s ({duration:.2f}s)")

        print(f"\n总覆盖时长: {total_duration:.2f}s / {video_duration}s")

        # 验证连续性
        prev_end = 0.0
        for seg in filled:
            gap = seg.start_time - prev_end
            assert gap < 1.0, f"存在间隔: {prev_end:.2f}s - {seg.start_time:.2f}s ({gap:.2f}s)"
            prev_end = seg.end_time

        print(f"✓ 所有间隔已填充，视频完整覆盖")


class TestNarrationSegmentProcessing:
    """测试解说片段处理"""

    @pytest.fixture
    def tts_service(self) -> TTSService:
        return TTSService(TTSSettings(backend="edge_tts"))

    @pytest.fixture
    def video_service(self) -> VideoService:
        return VideoService(VideoSettings())

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_generate_narration_audio(self, tts_service: TTSService, temp_dir: Path):
        """测试为解说片段生成 TTS 音频"""
        segment = NarrationSegment(
            type="解说",
            content="这个女人刚回家，就掉进死亡陷阱",
            start_time=0.0,
            end_time=3.0,
        )

        output_base = temp_dir / "narration_0"

        print(f"\n生成解说音频: {segment.content}")

        result = await tts_service.synthesize(
            text=segment.content,
            output_path=output_base,
            generate_subtitle=True,
        )

        # 更新 segment
        segment.audio_path = result.audio_path
        segment.subtitle_path = result.subtitle_path

        assert segment.audio_path.exists()
        assert segment.subtitle_path.exists()

        print(f"✓ 音频生成成功:")
        print(f"  - 音频: {segment.audio_path}")
        print(f"  - 字幕: {segment.subtitle_path}")
        print(f"  - 时长: {result.duration:.2f}s")

        # 检查字幕内容
        with open(segment.subtitle_path, "r", encoding="utf-8") as f:
            print(f"  - 字幕内容:\n{f.read()}")

    @pytest.mark.asyncio
    async def test_process_narration_segment(
        self,
        video_service: VideoService,
        tts_service: TTSService,
        sample_video_path: Path | None,
        temp_dir: Path,
    ):
        """测试处理解说片段 (裁剪 + 替换音频 + 添加字幕)"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        # 创建解说片段
        segment = NarrationSegment(
            type="解说",
            content="注意看，这个女人刚回家",
            start_time=0.0,
            end_time=3.0,
        )

        # 1. 生成 TTS 音频
        print(f"\n[Step 1] 生成 TTS 音频...")
        tts_result = await tts_service.synthesize(
            text=segment.content,
            output_path=temp_dir / "narration",
            generate_subtitle=True,
        )
        segment.audio_path = tts_result.audio_path
        segment.subtitle_path = tts_result.subtitle_path
        print(f"  ✓ 音频: {segment.audio_path}")
        print(f"  ✓ 字幕: {segment.subtitle_path}")

        # 2. 处理视频片段
        print(f"\n[Step 2] 处理视频片段...")
        output_path = temp_dir / "segment_narration.mp4"

        await video_service.process_segment(
            source_video=sample_video_path,
            segment=segment,
            output_path=output_path,
            temp_dir=temp_dir / "processing",
            segment_index=0,
        )

        assert output_path.exists()
        print(f"  ✓ 输出视频: {output_path}")

        # 验证输出时长
        duration = await video_service.get_duration(output_path)
        print(f"  ✓ 视频时长: {duration:.2f}s")


class TestVideoSegmentProcessing:
    """测试视频片段处理"""

    @pytest.fixture
    def video_service(self) -> VideoService:
        return VideoService(VideoSettings())

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_process_video_segment(
        self,
        video_service: VideoService,
        sample_video_path: Path | None,
        temp_dir: Path,
    ):
        """测试处理视频片段 (直接裁剪)"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        # 创建视频片段
        segment = NarrationSegment(
            type="video",
            start_time=3.0,
            end_time=8.0,
        )

        print(f"\n处理视频片段: {segment.start_time}s - {segment.end_time}s")

        output_path = temp_dir / "segment_video.mp4"

        await video_service.process_segment(
            source_video=sample_video_path,
            segment=segment,
            output_path=output_path,
            temp_dir=temp_dir / "processing",
            segment_index=0,
        )

        assert output_path.exists()

        duration = await video_service.get_duration(output_path)
        expected_duration = segment.end_time - segment.start_time

        print(f"✓ 视频片段处理成功:")
        print(f"  - 输出: {output_path}")
        print(f"  - 期望时长: {expected_duration:.2f}s")
        print(f"  - 实际时长: {duration:.2f}s")

        # 允许 0.5s 误差
        assert abs(duration - expected_duration) < 0.5


class TestFullEditingPipeline:
    """测试完整剪辑流程"""

    @pytest.fixture
    def tts_service(self) -> TTSService:
        return TTSService(TTSSettings(backend="edge_tts"))

    @pytest.fixture
    def video_service(self) -> VideoService:
        return VideoService(VideoSettings())

    @pytest.fixture
    def temp_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_full_editing_flow(
        self,
        video_service: VideoService,
        tts_service: TTSService,
        sample_video_path: Path | None,
        temp_dir: Path,
    ):
        """测试完整的剪辑流程"""
        if sample_video_path is None:
            pytest.skip("测试视频不存在")

        video_duration = await video_service.get_duration(sample_video_path)
        print(f"\n源视频时长: {video_duration:.2f}s")

        # 模拟 LLM 返回的片段 (根据实际视频时长调整)
        max_time = min(video_duration, 15.0)

        segments_data = [
            {
                "type": "解说",
                "content": "注意看，这个场景很有趣",
                "time": "00:00:00,000 --> 00:00:03,000"
            },
            {
                "type": "video",
                "time": f"00:00:03,000 --> 00:00:{int(max_time/2):02d},000"
            },
            {
                "type": "解说",
                "content": "接下来发生的事情让人意外",
                "time": f"00:00:{int(max_time/2):02d},000 --> 00:00:{int(max_time/2)+3:02d},000"
            },
            {
                "type": "video",
                "time": f"00:00:{int(max_time/2)+3:02d},000 --> 00:00:{int(max_time):02d},000"
            },
        ]

        # 过滤超出视频时长的片段
        segments = []
        for data in segments_data:
            seg = NarrationSegment.from_llm_response(data)
            if seg.end_time <= video_duration:
                segments.append(seg)

        print(f"\n片段数量: {len(segments)}")
        for i, seg in enumerate(segments):
            seg_type = "解说" if seg.is_narration else "视频"
            print(f"  [{i+1}] {seg_type}: {seg.start_time:.2f}s - {seg.end_time:.2f}s")

        # Step 1: 为解说片段生成 TTS 音频
        print(f"\n[Step 1] 生成解说音频...")
        audio_dir = temp_dir / "tts"
        audio_dir.mkdir(exist_ok=True)

        for i, seg in enumerate(segments):
            if seg.is_narration:
                result = await tts_service.synthesize(
                    text=seg.content,
                    output_path=audio_dir / f"narration_{i:03d}",
                    generate_subtitle=True,
                )
                seg.audio_path = result.audio_path
                seg.subtitle_path = result.subtitle_path
                print(f"  ✓ 片段 {i+1}: {result.audio_path}")

        # Step 2: 处理所有片段
        print(f"\n[Step 2] 处理视频片段...")
        segments_dir = temp_dir / "segments"

        segment_paths = await video_service.process_all_segments(
            source_video=sample_video_path,
            segments=segments,
            output_dir=segments_dir,
            temp_dir=temp_dir / "processing",
        )

        assert len(segment_paths) == len(segments)
        for i, path in enumerate(segment_paths):
            assert path.exists()
            duration = await video_service.get_duration(path)
            print(f"  ✓ 片段 {i+1}: {path.name} ({duration:.2f}s)")

        # Step 3: 拼接所有片段
        print(f"\n[Step 3] 拼接视频...")
        output_path = temp_dir / "final_output.mp4"

        final_path = await video_service.concat(segment_paths, output_path)

        assert final_path.exists()
        final_duration = await video_service.get_duration(final_path)

        print(f"\n✓ 最终视频生成成功:")
        print(f"  - 路径: {final_path}")
        print(f"  - 时长: {final_duration:.2f}s")


class TestEdgeCases:
    """边界情况测试"""

    def test_time_parsing_with_milliseconds(self):
        """测试毫秒时间解析"""
        data = {
            "type": "video",
            "time": "00:01:23,456 --> 00:02:34,789"
        }

        segment = NarrationSegment.from_llm_response(data)

        # 1分23秒456毫秒 = 83.456秒
        assert abs(segment.start_time - 83.456) < 0.001
        # 2分34秒789毫秒 = 154.789秒
        assert abs(segment.end_time - 154.789) < 0.001
        print(f"✓ 时间解析正确: {segment.start_time}s - {segment.end_time}s")

    def test_time_parsing_hours(self):
        """测试小时时间解析"""
        data = {
            "type": "video",
            "time": "01:30:00,000 --> 01:35:30,500"
        }

        segment = NarrationSegment.from_llm_response(data)

        # 1小时30分 = 5400秒
        assert segment.start_time == 5400.0
        # 1小时35分30.5秒 = 5730.5秒
        assert abs(segment.end_time - 5730.5) < 0.001
        print(f"✓ 小时时间解析正确: {segment.start_time}s - {segment.end_time}s")


# 独立运行函数
def run_editing_test():
    """独立运行剪辑测试"""
    print("=" * 50)
    print("视频剪辑流程测试")
    print("=" * 50)

    # 测试片段解析
    print("\n--- 测试片段解析 ---")

    llm_response = [
        {"type": "解说", "content": "这个女人刚回家", "time": "00:00:00,000 --> 00:00:03,000"},
        {"type": "video", "time": "00:00:03,000 --> 00:00:11,089"},
        {"type": "解说", "content": "大哥的愤怒", "time": "00:01:00,360 --> 00:01:03,360"},
        {"type": "video", "time": "00:01:03,360 --> 00:01:15,140"},
    ]

    segments = [NarrationSegment.from_llm_response(d) for d in llm_response]

    print(f"解析 {len(segments)} 个片段:")
    for i, seg in enumerate(segments):
        if seg.is_narration:
            print(f"  [{i+1}] 解说: {seg.start_time:.2f}s-{seg.end_time:.2f}s '{seg.content}'")
        else:
            print(f"  [{i+1}] 视频: {seg.start_time:.2f}s-{seg.end_time:.2f}s")

    # 检查测试视频
    test_video = Path("data/input/test.mp4")
    if not test_video.exists():
        print("\n⚠ 测试视频不存在: data/input/test.mp4")
        print("  请放置测试视频后运行完整测试")
        return

    print("\n--- 测试完整流程 ---")

    async def run_full_test():
        from playlet_clip.services.tts import TTSService
        from playlet_clip.services.video import VideoService
        from playlet_clip.core.config import TTSSettings, VideoSettings

        tts_service = TTSService(TTSSettings(backend="edge_tts"))
        video_service = VideoService(VideoSettings())

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            video_duration = await video_service.get_duration(test_video)

            print(f"视频时长: {video_duration:.2f}s")

            # 创建测试片段
            segments = [
                NarrationSegment(type="解说", content="测试解说", start_time=0, end_time=3),
                NarrationSegment(type="video", start_time=3, end_time=min(8, video_duration)),
            ]

            # 生成 TTS
            for i, seg in enumerate(segments):
                if seg.is_narration:
                    result = await tts_service.synthesize(
                        text=seg.content,
                        output_path=temp_dir / f"tts_{i}",
                        generate_subtitle=True,
                    )
                    seg.audio_path = result.audio_path
                    seg.subtitle_path = result.subtitle_path
                    print(f"✓ TTS 生成: {result.duration:.2f}s")

            # 处理片段
            segment_paths = await video_service.process_all_segments(
                source_video=test_video,
                segments=segments,
                output_dir=temp_dir / "segments",
                temp_dir=temp_dir / "processing",
            )

            # 拼接
            output = temp_dir / "output.mp4"
            await video_service.concat(segment_paths, output)

            final_duration = await video_service.get_duration(output)
            print(f"✓ 最终视频: {final_duration:.2f}s")

    asyncio.run(run_full_test())


if __name__ == "__main__":
    run_editing_test()
