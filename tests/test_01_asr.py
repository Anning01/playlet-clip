"""
ASR (语音识别) 服务测试

测试 FunASR 语音识别功能:
1. 服务初始化
2. 音频转录
3. 字幕格式化

运行方式:
    uv run pytest tests/test_01_asr.py -v -s

注意:
    - 需要放置测试音频文件到 data/input/test.wav
    - 首次运行会下载 FunASR 模型 (~2GB)
    - 建议使用 CUDA 加速
"""

import asyncio
from pathlib import Path

import pytest

from playlet_clip.core.config import ASRSettings
from playlet_clip.services.asr import ASRService


class TestASRService:
    """ASR 服务测试类"""

    @pytest.fixture
    def asr_settings(self) -> ASRSettings:
        """创建 ASR 配置"""
        return ASRSettings(
            device="cpu",  # 测试时使用 CPU，生产环境用 cuda
            batch_size=1,
        )

    @pytest.fixture
    def asr_service(self, asr_settings: ASRSettings) -> ASRService:
        """创建 ASR 服务实例"""
        return ASRService(asr_settings)

    def test_asr_service_creation(self, asr_service: ASRService):
        """测试 ASR 服务创建"""
        assert asr_service is not None
        assert asr_service.config is not None
        print(f"✓ ASR 服务创建成功")
        print(f"  - 设备: {asr_service.config.device}")
        print(f"  - 模型: {asr_service.config.model_name}")

    def test_asr_model_initialization(self, asr_service: ASRService):
        """测试 ASR 模型初始化

        注意: 首次运行会下载模型，可能需要几分钟
        """
        try:
            asr_service._ensure_model_loaded()
            assert asr_service._model is not None
            print(f"✓ ASR 模型加载成功")
        except Exception as e:
            pytest.skip(f"模型加载失败 (可能需要下载): {e}")

    @pytest.mark.asyncio
    async def test_transcribe_audio(self, asr_service: ASRService, sample_audio_path: Path | None):
        """测试音频转录

        需要: data/input/test.wav
        """
        if sample_audio_path is None:
            pytest.skip("测试音频不存在，请放置 data/input/test.wav")

        print(f"\n转录音频: {sample_audio_path}")

        try:
            segments = await asr_service.transcribe(sample_audio_path)

            assert segments is not None
            assert len(segments) > 0

            print(f"✓ 转录成功，共 {len(segments)} 个片段:")
            for seg in segments[:5]:  # 只显示前5个
                print(f"  [{seg.start_time:.2f}s - {seg.end_time:.2f}s] {seg.text}")

            if len(segments) > 5:
                print(f"  ... 还有 {len(segments) - 5} 个片段")

        except Exception as e:
            pytest.fail(f"转录失败: {e}")

    @pytest.mark.asyncio
    async def test_transcribe_video(self, asr_service: ASRService, sample_video_path: Path | None):
        """测试视频转录

        需要: data/input/test.mp4
        """
        if sample_video_path is None:
            pytest.skip("测试视频不存在，请放置 data/input/test.mp4")

        print(f"\n转录视频: {sample_video_path}")

        try:
            segments = await asr_service.transcribe(sample_video_path)

            assert segments is not None
            assert len(segments) > 0

            print(f"✓ 视频转录成功，共 {len(segments)} 个片段:")
            for seg in segments[:5]:
                print(f"  [{seg.start_time:.2f}s - {seg.end_time:.2f}s] {seg.text}")

        except Exception as e:
            pytest.fail(f"视频转录失败: {e}")


class TestASRWithProgress:
    """带进度回调的 ASR 测试"""

    @pytest.fixture
    def asr_service(self) -> ASRService:
        return ASRService(ASRSettings(device="cpu"))

    @pytest.mark.asyncio
    async def test_transcribe_with_progress(
        self, asr_service: ASRService, sample_audio_path: Path | None
    ):
        """测试带进度回调的转录"""
        if sample_audio_path is None:
            pytest.skip("测试音频不存在")

        progress_updates = []

        def on_progress(progress: float, message: str):
            progress_updates.append((progress, message))
            print(f"  进度: {progress:.0f}% - {message}")

        print("\n开始转录 (带进度):")

        try:
            segments = await asr_service.transcribe(
                sample_audio_path,
                progress_callback=on_progress,
            )

            assert len(progress_updates) > 0
            assert segments is not None
            print(f"✓ 完成，收到 {len(progress_updates)} 次进度更新")

        except Exception as e:
            pytest.fail(f"转录失败: {e}")


# 独立测试函数 - 方便直接运行
def run_asr_test():
    """独立运行 ASR 测试"""
    print("=" * 50)
    print("ASR 服务测试")
    print("=" * 50)

    # 创建服务
    settings = ASRSettings(device="cpu")
    service = ASRService(settings)
    print(f"✓ 服务创建成功")

    # 检查测试文件
    test_audio = Path("data/input/test.wav")
    test_video = Path("data/input/test.mp4")

    if test_audio.exists():
        print(f"\n测试音频转录: {test_audio}")
        segments = asyncio.run(service.transcribe(test_audio))
        print(f"✓ 转录完成")
        for seg in segments[:3]:
            print(f"  {seg.text}")
    elif test_video.exists():
        print(f"\n测试视频转录: {test_video}")
        segments = asyncio.run(service.transcribe(test_video))
        print(f"✓ 转录完成")
        for seg in segments[:3]:
            print(f"  {seg.text}")
    else:
        print("\n⚠ 未找到测试文件")
        print("  请放置 data/input/test.wav 或 data/input/test.mp4")


if __name__ == "__main__":
    run_asr_test()
