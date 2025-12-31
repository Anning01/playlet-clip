#!/bin/bash
# 测试运行脚本
# 用于单独运行各个服务的测试

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Playlet-Clip 测试运行器${NC}"
echo -e "${BLUE}========================================${NC}"

# 显示帮助
show_help() {
    echo ""
    echo "用法: ./scripts/run_tests.sh [选项]"
    echo ""
    echo "选项:"
    echo "  all       运行所有测试"
    echo "  asr       运行 ASR 语音识别测试"
    echo "  tts       运行 TTS 语音合成测试"
    echo "  llm       运行 LLM 解说生成测试"
    echo "  video     运行视频处理测试"
    echo "  pipeline  运行完整流程测试"
    echo "  quick     快速测试 (只测试基础功能)"
    echo ""
    echo "示例:"
    echo "  ./scripts/run_tests.sh asr       # 只测试 ASR"
    echo "  ./scripts/run_tests.sh tts       # 只测试 TTS"
    echo "  ./scripts/run_tests.sh all       # 运行所有测试"
    echo ""
    echo "环境变量:"
    echo "  OPENAI_API_KEY    OpenAI API 密钥 (LLM 测试必需)"
    echo "  OPENAI_BASE_URL   OpenAI API 地址 (可选)"
    echo ""
    echo "测试数据:"
    echo "  请放置测试视频到 data/input/test.mp4"
    echo "  请放置测试音频到 data/input/test.wav (可选)"
    echo ""
}

# 检查环境
check_env() {
    echo -e "\n${YELLOW}检查环境...${NC}"

    # 检查 uv
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}✗ uv 未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ uv 已安装${NC}"

    # 检查 ffmpeg
    if ! command -v ffmpeg &> /dev/null; then
        echo -e "${YELLOW}⚠ ffmpeg 未安装 (视频测试需要)${NC}"
    else
        echo -e "${GREEN}✓ ffmpeg 已安装${NC}"
    fi

    # 检查 API Key
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}⚠ OPENAI_API_KEY 未设置 (LLM 测试需要)${NC}"
    else
        echo -e "${GREEN}✓ OPENAI_API_KEY 已设置${NC}"
    fi

    # 检查测试视频
    if [ -f "data/input/test.mp4" ]; then
        echo -e "${GREEN}✓ 测试视频存在: data/input/test.mp4${NC}"
    else
        echo -e "${YELLOW}⚠ 测试视频不存在 (部分测试会跳过)${NC}"
    fi
}

# 运行 ASR 测试
run_asr_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Step 1: ASR 语音识别测试${NC}"
    echo -e "${BLUE}========================================${NC}"
    uv run pytest tests/test_01_asr.py -v -s
}

# 运行 TTS 测试
run_tts_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Step 2: TTS 语音合成测试${NC}"
    echo -e "${BLUE}========================================${NC}"
    uv run pytest tests/test_02_tts.py -v -s
}

# 运行 LLM 测试
run_llm_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Step 3: LLM 解说生成测试${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}跳过: OPENAI_API_KEY 未设置${NC}"
        return
    fi

    uv run pytest tests/test_03_llm.py -v -s
}

# 运行视频测试
run_video_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Step 4: 视频处理测试${NC}"
    echo -e "${BLUE}========================================${NC}"
    uv run pytest tests/test_04_video.py -v -s
}

# 运行 Pipeline 测试
run_pipeline_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Step 5: 完整流程测试${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}跳过: OPENAI_API_KEY 未设置${NC}"
        return
    fi

    uv run pytest tests/test_05_pipeline.py -v -s
}

# 运行快速测试
run_quick_test() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  快速测试 (基础功能)${NC}"
    echo -e "${BLUE}========================================${NC}"

    # 只运行基础测试，跳过耗时的测试
    uv run pytest tests/ -v -s -k "creation or basic or available" --ignore=tests/test_05_pipeline.py
}

# 运行所有测试
run_all_tests() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  运行所有测试${NC}"
    echo -e "${BLUE}========================================${NC}"
    uv run pytest tests/ -v -s
}

# 主函数
main() {
    case "${1:-help}" in
        help|--help|-h)
            show_help
            ;;
        all)
            check_env
            run_all_tests
            ;;
        asr)
            check_env
            run_asr_test
            ;;
        tts)
            check_env
            run_tts_test
            ;;
        llm)
            check_env
            run_llm_test
            ;;
        video)
            check_env
            run_video_test
            ;;
        pipeline)
            check_env
            run_pipeline_test
            ;;
        quick)
            check_env
            run_quick_test
            ;;
        1)
            check_env
            run_asr_test
            ;;
        2)
            check_env
            run_tts_test
            ;;
        3)
            check_env
            run_llm_test
            ;;
        4)
            check_env
            run_video_test
            ;;
        5)
            check_env
            run_pipeline_test
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
