"""
TTS (语音合成) 服务测试

测试多后端 TTS 功能:
1. Edge-TTS (云服务，无需 GPU)
2. CosyVoice API (Docker 部署)
3. CosyVoice Local (本地部署)

运行方式:
    uv run pytest tests/test_02_tts.py -v -s

    # 只测试 edge-tts
    uv run pytest tests/test_02_tts.py -v -s -k "edge"

    # 只测试 cosyvoice
    uv run pytest tests/test_02_tts.py -v -s -k "cosyvoice"
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from playlet_clip.core.config import TTSSettings
from playlet_clip.services.tts import TTSService


class TestTTSServiceBasic:
    """TTS 服务基础测试"""

    @pytest.fixture
    def tts_settings_edge(self) -> TTSSettings:
        """Edge-TTS 配置"""
        return TTSSettings(
            backend="edge_tts",
            default_voice="中文女",
            speed=1.0,
        )

    @pytest.fixture
    def tts_settings_auto(self) -> TTSSettings:
        """自动选择后端配置"""
        return TTSSettings(
            backend="auto",
            default_voice="中文女",
        )

    def test_tts_service_creation(self, tts_settings_edge: TTSSettings):
        """测试 TTS 服务创建"""
        service = TTSService(tts_settings_edge)
        assert service is not None
        print(f"✓ TTS 服务创建成功")
        print(f"  - 配置后端: {service.config.backend}")
        print(f"  - 默认音色: {service.config.default_voice}")

    def test_list_voices(self, tts_settings_edge: TTSSettings):
        """测试列出可用音色"""
        service = TTSService(tts_settings_edge)
        voices = service.list_voices()

        assert len(voices) > 0
        print(f"✓ 可用音色 ({len(voices)} 个):")
        for voice in voices:
            print(f"  - {voice}")

    def test_backend_detection(self, tts_settings_auto: TTSSettings):
        """测试后端自动检测"""
        service = TTSService(tts_settings_auto)

        # 触发初始化
        service._ensure_initialized()

        backend = service.get_backend()
        print(f"✓ 检测到后端: {backend}")


class TestEdgeTTS:
    """Edge-TTS 测试"""

    @pytest.fixture
    def tts_service(self) -> TTSService:
        return TTSService(TTSSettings(backend="edge_tts"))

    @pytest.fixture
    def temp_output_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_edge_tts_synthesize(self, tts_service: TTSService, temp_output_dir: Path):
        """测试 Edge-TTS 语音合成"""
        text = "你好，这是一个测试。欢迎使用语音合成服务。"
        output_path = temp_output_dir / "test_output"

        print(f"\n合成文本: {text}")

        result = await tts_service.synthesize(
            text=text,
            output_path=output_path,
            voice="中文女",
            generate_subtitle=True,
        )

        assert result.audio_path.exists()
        assert result.duration > 0
        print(f"✓ 合成成功:")
        print(f"  - 音频: {result.audio_path}")
        print(f"  - 时长: {result.duration:.2f}s")
        print(f"  - 采样率: {result.sample_rate}")
        if result.subtitle_path:
            print(f"  - 字幕: {result.subtitle_path}")
            print(f"  - 字幕内容:")
            with open(result.subtitle_path, "r", encoding="utf-8") as f:
                print(f.read()[:500])

    @pytest.mark.asyncio
    async def test_edge_tts_different_voices(self, tts_service: TTSService, temp_output_dir: Path):
        """测试不同音色"""
        voices_to_test = ["中文女", "中文男", "英文女"]
        text = "Hello, 你好"

        for voice in voices_to_test:
            output_path = temp_output_dir / f"test_{voice}"
            print(f"\n测试音色: {voice}")

            try:
                result = await tts_service.synthesize(
                    text=text,
                    output_path=output_path,
                    voice=voice,
                    generate_subtitle=False,
                )
                print(f"  ✓ 成功 - 时长: {result.duration:.2f}s")
            except Exception as e:
                print(f"  ✗ 失败: {e}")

    @pytest.mark.asyncio
    async def test_edge_tts_with_progress(self, tts_service: TTSService, temp_output_dir: Path):
        """测试带进度回调的合成"""
        text = "这是一段较长的文本，用于测试进度回调功能。我们需要确保进度更新正常工作。"
        output_path = temp_output_dir / "test_progress"

        progress_updates = []

        def on_progress(progress: float, message: str):
            progress_updates.append((progress, message))
            print(f"  进度: {progress:.0f}% - {message}")

        print("\n开始合成 (带进度):")

        result = await tts_service.synthesize(
            text=text,
            output_path=output_path,
            progress_callback=on_progress,
        )

        assert len(progress_updates) > 0
        print(f"✓ 完成，收到 {len(progress_updates)} 次进度更新")


class TestCosyVoiceAPI:
    """CosyVoice API 测试 (需要 Docker 服务运行)"""

    @pytest.fixture
    def tts_service(self) -> TTSService:
        return TTSService(
            TTSSettings(
                backend="cosyvoice_api",
                cosyvoice_api_url="http://localhost:8080",
            )
        )

    @pytest.fixture
    def temp_output_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_cosyvoice_api_available(self, tts_service: TTSService):
        """测试 CosyVoice API 是否可用"""
        try:
            tts_service._ensure_initialized()
            backend = tts_service.get_backend()
            if backend == "cosyvoice_api":
                print(f"✓ CosyVoice API 可用")
            else:
                pytest.skip(f"CosyVoice API 不可用，实际后端: {backend}")
        except Exception as e:
            pytest.skip(f"CosyVoice API 连接失败: {e}")

    @pytest.mark.asyncio
    async def test_cosyvoice_api_synthesize(self, tts_service: TTSService, temp_output_dir: Path):
        """测试 CosyVoice API 语音合成"""
        try:
            tts_service._ensure_initialized()
            if tts_service.get_backend() != "cosyvoice_api":
                pytest.skip("CosyVoice API 不可用")
        except Exception:
            pytest.skip("CosyVoice API 不可用")

        text = "你好，这是 CosyVoice 语音合成测试。"
        output_path = temp_output_dir / "cosyvoice_test"

        print(f"\n合成文本: {text}")

        result = await tts_service.synthesize(
            text=text,
            output_path=output_path,
            voice="中文女",
        )

        assert result.audio_path.exists()
        print(f"✓ CosyVoice API 合成成功:")
        print(f"  - 音频: {result.audio_path}")
        print(f"  - 时长: {result.duration:.2f}s")


class TestCosyVoiceLocal:
    """CosyVoice 本地测试 (需要安装 CosyVoice)"""

    @pytest.fixture
    def tts_service(self) -> TTSService:
        return TTSService(
            TTSSettings(
                backend="cosyvoice_local",
                model_name="pretrained_models/CosyVoice-300M-SFT",
                device="cuda",
            )
        )

    @pytest.fixture
    def temp_output_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_cosyvoice_local_available(self, tts_service: TTSService):
        """测试 CosyVoice 本地是否可用"""
        try:
            tts_service._ensure_initialized()
            backend = tts_service.get_backend()
            if backend == "cosyvoice_local":
                print(f"✓ CosyVoice 本地可用")
            else:
                pytest.skip(f"CosyVoice 本地不可用，实际后端: {backend}")
        except Exception as e:
            pytest.skip(f"CosyVoice 本地初始化失败: {e}")

    @pytest.mark.asyncio
    async def test_cosyvoice_local_synthesize(
        self, tts_service: TTSService, temp_output_dir: Path
    ):
        """测试 CosyVoice 本地语音合成"""
        try:
            tts_service._ensure_initialized()
            if tts_service.get_backend() != "cosyvoice_local":
                pytest.skip("CosyVoice 本地不可用")
        except Exception:
            pytest.skip("CosyVoice 本地不可用")

        text = "你好，这是 CosyVoice 本地语音合成测试。"
        output_path = temp_output_dir / "cosyvoice_local_test"

        print(f"\n合成文本: {text}")

        result = await tts_service.synthesize(
            text=text,
            output_path=output_path,
            voice="中文女",
        )

        assert result.audio_path.exists()
        print(f"✓ CosyVoice 本地合成成功:")
        print(f"  - 音频: {result.audio_path}")
        print(f"  - 时长: {result.duration:.2f}s")


class TestTTSSubtitleGeneration:
    """字幕生成测试"""

    @pytest.fixture
    def tts_service(self) -> TTSService:
        return TTSService(TTSSettings(backend="edge_tts"))

    def test_split_text_to_segments(self, tts_service: TTSService):
        """测试文本分割"""
        text = "这是第一句话。这是第二句话，包含逗号。还有第三句！"
        duration = 10.0

        segments = tts_service._split_text_to_segments(text, duration)

        assert len(segments) > 0
        print(f"✓ 文本分割成 {len(segments)} 个片段:")
        for seg in segments:
            print(f"  [{seg.start_time:.2f}s - {seg.end_time:.2f}s] {seg.text}")

    def test_split_long_text(self, tts_service: TTSService):
        """测试长文本分割"""
        text = "这是一个非常非常非常非常非常非常长的句子需要被分割成多个字幕片段来显示"
        duration = 15.0

        segments = tts_service._split_text_to_segments(text, duration, max_chars=10)

        assert len(segments) > 1
        print(f"✓ 长文本分割成 {len(segments)} 个片段:")
        for seg in segments:
            assert len(seg.text) <= 15  # 允许一些溢出
            print(f"  [{seg.start_time:.2f}s - {seg.end_time:.2f}s] {seg.text}")


# 独立测试函数
def run_tts_test():
    """独立运行 TTS 测试"""
    print("=" * 50)
    print("TTS 服务测试")
    print("=" * 50)

    # 测试 Edge-TTS
    print("\n--- Edge-TTS 测试 ---")
    service = TTSService(TTSSettings(backend="edge_tts"))
    print(f"✓ 服务创建成功")

    # 列出音色
    voices = service.list_voices()
    print(f"✓ 可用音色: {', '.join(voices)}")

    # 合成测试
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test"
        text = "你好，这是语音合成测试。"

        print(f"\n合成: {text}")
        result = asyncio.run(
            service.synthesize(text=text, output_path=output_path, generate_subtitle=True)
        )
        print(f"✓ 合成成功:")
        print(f"  - 音频: {result.audio_path}")
        print(f"  - 时长: {result.duration:.2f}s")

        if result.subtitle_path and result.subtitle_path.exists():
            print(f"  - 字幕内容:")
            with open(result.subtitle_path, "r", encoding="utf-8") as f:
                print(f.read())


if __name__ == "__main__":
    run_tts_test()
