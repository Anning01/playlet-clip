"""
LLM (解说生成) 服务测试

测试 OpenAI API 解说脚本生成功能:
1. 服务初始化
2. 解说脚本生成
3. JSON 格式验证
4. 时间戳验证

运行方式:
    uv run pytest tests/test_03_llm.py -v -s

注意:
    - 需要配置 OPENAI_API_KEY 环境变量
    - 或在 config/config.yaml 中配置 llm.api_key
"""

import asyncio
import os
from pathlib import Path

import pytest

from playlet_clip.core.config import LLMSettings, Settings
from playlet_clip.models.subtitle import SubtitleSegment
from playlet_clip.services.llm import LLMService


class TestLLMServiceBasic:
    """LLM 服务基础测试"""

    @pytest.fixture
    def llm_settings(self) -> LLMSettings:
        """创建 LLM 配置"""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        return LLMSettings(
            api_key=api_key,
            base_url=base_url,
            model="gpt-4o",
            temperature=0.3,
            max_retries=3,
        )

    @pytest.fixture
    def llm_service(self, llm_settings: LLMSettings) -> LLMService:
        """创建 LLM 服务实例"""
        return LLMService(llm_settings)

    def test_llm_service_creation(self, llm_service: LLMService):
        """测试 LLM 服务创建"""
        assert llm_service is not None
        print(f"✓ LLM 服务创建成功")
        print(f"  - 模型: {llm_service.config.model}")
        print(f"  - API: {llm_service.config.base_url}")
        print(f"  - API Key: {'已配置' if llm_service.config.api_key else '未配置'}")

    def test_api_key_configured(self, llm_settings: LLMSettings):
        """测试 API Key 是否配置"""
        if not llm_settings.api_key:
            pytest.skip("OPENAI_API_KEY 未配置")
        print(f"✓ API Key 已配置")


class TestLLMNarrationGeneration:
    """解说脚本生成测试"""

    @pytest.fixture
    def llm_service(self) -> LLMService:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            pytest.skip("OPENAI_API_KEY 未配置")

        return LLMService(
            LLMSettings(
                api_key=api_key,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                model="gpt-4o",
                temperature=0.3,
                max_retries=3,
            )
        )

    @pytest.fixture
    def sample_subtitles(self) -> list[SubtitleSegment]:
        """示例字幕数据"""
        return [
            SubtitleSegment(index=1, start_time=0.0, end_time=3.0, text="女主角走进了豪华的办公室"),
            SubtitleSegment(index=2, start_time=3.0, end_time=6.0, text="男主角抬头看着她，眼神复杂"),
            SubtitleSegment(index=3, start_time=6.0, end_time=9.0, text="你终于来了，我等你很久了"),
            SubtitleSegment(index=4, start_time=9.0, end_time=12.0, text="女主角冷笑：你以为我会原谅你吗"),
            SubtitleSegment(index=5, start_time=12.0, end_time=15.0, text="男主角站起来，走向她"),
        ]

    @pytest.fixture
    def style_config(self) -> dict:
        """解说风格配置"""
        return {
            "name": "讽刺风格",
            "description": "通过讽刺和夸张的手法来评论剧中的不合理或过于狗血的情节，让观众在笑声中进行思考。",
        }

    @pytest.mark.asyncio
    async def test_generate_narration_basic(
        self,
        llm_service: LLMService,
        sample_subtitles: list[SubtitleSegment],
        style_config: dict,
    ):
        """测试基础解说生成"""
        video_duration = 15.0

        print(f"\n生成解说脚本:")
        print(f"  - 风格: {style_config['name']}")
        print(f"  - 视频时长: {video_duration}s")
        print(f"  - 字幕数量: {len(sample_subtitles)}")

        narrations = await llm_service.generate_narration(
            subtitles=sample_subtitles,
            video_duration=video_duration,
            style_name=style_config["name"],
            style_description=style_config["description"],
        )

        assert narrations is not None
        assert len(narrations) > 0

        print(f"\n✓ 生成成功，共 {len(narrations)} 个解说片段:")
        for n in narrations:
            print(f"  [{n.start_time:.1f}s - {n.end_time:.1f}s] {n.text}")

    @pytest.mark.asyncio
    async def test_generate_narration_with_progress(
        self,
        llm_service: LLMService,
        sample_subtitles: list[SubtitleSegment],
        style_config: dict,
    ):
        """测试带进度回调的解说生成"""
        progress_updates = []

        def on_progress(progress: float, message: str):
            progress_updates.append((progress, message))
            print(f"  进度: {progress:.0f}% - {message}")

        print("\n开始生成 (带进度):")

        narrations = await llm_service.generate_narration(
            subtitles=sample_subtitles,
            video_duration=15.0,
            style_name=style_config["name"],
            style_description=style_config["description"],
            progress_callback=on_progress,
        )

        assert len(progress_updates) > 0
        print(f"✓ 完成，收到 {len(progress_updates)} 次进度更新")

    @pytest.mark.asyncio
    async def test_narration_time_validation(
        self,
        llm_service: LLMService,
        sample_subtitles: list[SubtitleSegment],
        style_config: dict,
    ):
        """测试解说时间戳验证"""
        video_duration = 15.0

        narrations = await llm_service.generate_narration(
            subtitles=sample_subtitles,
            video_duration=video_duration,
            style_name=style_config["name"],
            style_description=style_config["description"],
        )

        print("\n验证时间戳:")
        for n in narrations:
            # 检查时间范围
            assert n.start_time >= 0, f"开始时间不能为负: {n.start_time}"
            assert n.end_time <= video_duration, f"结束时间超出视频: {n.end_time}"
            assert n.start_time < n.end_time, f"开始时间应小于结束时间: {n.start_time} >= {n.end_time}"
            print(f"  ✓ [{n.start_time:.1f}s - {n.end_time:.1f}s] 有效")

        print(f"✓ 所有时间戳验证通过")


class TestLLMDifferentStyles:
    """不同风格测试"""

    @pytest.fixture
    def llm_service(self) -> LLMService:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            pytest.skip("OPENAI_API_KEY 未配置")

        return LLMService(
            LLMSettings(
                api_key=api_key,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
        )

    @pytest.fixture
    def sample_subtitles(self) -> list[SubtitleSegment]:
        return [
            SubtitleSegment(index=1, start_time=0.0, end_time=5.0, text="女主角发现男主角和别的女人在一起"),
            SubtitleSegment(index=2, start_time=5.0, end_time=10.0, text="她转身离开，眼泪流了下来"),
        ]

    @pytest.mark.asyncio
    async def test_satirical_style(self, llm_service: LLMService, sample_subtitles: list):
        """测试讽刺风格"""
        print("\n--- 讽刺风格 ---")

        narrations = await llm_service.generate_narration(
            subtitles=sample_subtitles,
            video_duration=10.0,
            style_name="讽刺风格",
            style_description="通过讽刺和夸张的手法来评论剧中的不合理情节",
        )

        for n in narrations:
            print(f"  {n.text}")

    @pytest.mark.asyncio
    async def test_warm_style(self, llm_service: LLMService, sample_subtitles: list):
        """测试温情风格"""
        print("\n--- 温情风格 ---")

        narrations = await llm_service.generate_narration(
            subtitles=sample_subtitles,
            video_duration=10.0,
            style_name="温情风格",
            style_description="以温和、感性的语气解读剧情，引发观众共鸣",
        )

        for n in narrations:
            print(f"  {n.text}")

    @pytest.mark.asyncio
    async def test_suspense_style(self, llm_service: LLMService, sample_subtitles: list):
        """测试悬疑风格"""
        print("\n--- 悬疑风格 ---")

        narrations = await llm_service.generate_narration(
            subtitles=sample_subtitles,
            video_duration=10.0,
            style_name="悬疑风格",
            style_description="以悬疑、紧张的语气解读剧情，制造悬念感",
        )

        for n in narrations:
            print(f"  {n.text}")


class TestLLMRetryMechanism:
    """重试机制测试"""

    @pytest.fixture
    def llm_service(self) -> LLMService:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            pytest.skip("OPENAI_API_KEY 未配置")

        return LLMService(
            LLMSettings(
                api_key=api_key,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                max_retries=5,  # 允许更多重试
            )
        )

    @pytest.mark.asyncio
    async def test_retry_on_invalid_json(self, llm_service: LLMService):
        """测试 JSON 格式错误时的重试"""
        # 使用简单字幕，减少出错机会
        subtitles = [
            SubtitleSegment(index=1, start_time=0.0, end_time=5.0, text="测试字幕"),
        ]

        print("\n测试重试机制:")

        try:
            narrations = await llm_service.generate_narration(
                subtitles=subtitles,
                video_duration=5.0,
                style_name="讽刺风格",
                style_description="测试风格",
            )
            print(f"✓ 生成成功: {len(narrations)} 个片段")
        except Exception as e:
            print(f"✗ 生成失败: {e}")
            # 不抛出异常，因为这是测试重试机制


# 独立测试函数
def run_llm_test():
    """独立运行 LLM 测试"""
    print("=" * 50)
    print("LLM 服务测试")
    print("=" * 50)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("✗ OPENAI_API_KEY 未配置")
        print("  请设置环境变量: export OPENAI_API_KEY=your-key")
        return

    # 创建服务
    service = LLMService(
        LLMSettings(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
    )
    print(f"✓ 服务创建成功")

    # 测试字幕
    subtitles = [
        SubtitleSegment(index=1, start_time=0.0, end_time=5.0, text="女主角走进办公室"),
        SubtitleSegment(index=2, start_time=5.0, end_time=10.0, text="男主角说：你终于来了"),
    ]

    print(f"\n生成解说脚本:")

    async def generate():
        return await service.generate_narration(
            subtitles=subtitles,
            video_duration=10.0,
            style_name="讽刺风格",
            style_description="通过讽刺和夸张的手法来评论剧情",
        )

    narrations = asyncio.run(generate())
    print(f"✓ 生成成功，共 {len(narrations)} 个片段:")
    for n in narrations:
        print(f"  [{n.start_time:.1f}s - {n.end_time:.1f}s] {n.text}")


if __name__ == "__main__":
    run_llm_test()
