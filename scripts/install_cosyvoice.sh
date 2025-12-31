#!/bin/bash
# CosyVoice 安装脚本 - 使用 ModelScope 下载模型
set -e

echo "=========================================="
echo "CosyVoice 安装脚本"
echo "=========================================="

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 1. 克隆 CosyVoice 源码到 third_party
echo "[1/4] 克隆 CosyVoice 源码..."
mkdir -p third_party
if [ ! -d "third_party/CosyVoice" ]; then
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git third_party/CosyVoice
else
    echo "CosyVoice 已存在，跳过克隆"
fi

# 2. 安装 CosyVoice 依赖
echo "[2/4] 安装 CosyVoice 依赖..."
cd third_party/CosyVoice
uv pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
cd "$PROJECT_ROOT"

# 3. 安装 sox (仅 Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "[3/4] 安装 sox..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y sox libsox-dev
    elif command -v yum &> /dev/null; then
        sudo yum install -y sox sox-devel
    fi
else
    echo "[3/4] 跳过 sox 安装 (非 Linux 系统)"
fi

# 4. 使用 ModelScope 下载模型
echo "[4/4] 下载 CosyVoice 模型..."
uv run python << 'PYTHON_SCRIPT'
import os
from pathlib import Path

try:
    from modelscope import snapshot_download
except ImportError:
    print("正在安装 modelscope...")
    import subprocess
    subprocess.run(["uv", "pip", "install", "modelscope", "-i", "https://mirrors.aliyun.com/pypi/simple/"])
    from modelscope import snapshot_download

models_dir = Path("pretrained_models")
models_dir.mkdir(exist_ok=True)

# 下载 CosyVoice-300M-SFT (约 1.2GB)
model_id = "iic/CosyVoice-300M-SFT"
local_dir = models_dir / "CosyVoice-300M-SFT"

if local_dir.exists():
    print(f"模型已存在: {local_dir}")
else:
    print(f"下载模型: {model_id}")
    snapshot_download(model_id, local_dir=str(local_dir))
    print(f"模型已下载到: {local_dir}")

print("\n✅ 安装完成!")
PYTHON_SCRIPT

# 创建环境变量设置脚本
cat > setup_cosyvoice_env.sh << 'EOF'
#!/bin/bash
# CosyVoice 环境变量设置
export PYTHONPATH="$PYTHONPATH:$(pwd)/third_party/CosyVoice:$(pwd)/third_party/CosyVoice/third_party/Matcha-TTS"
echo "CosyVoice 环境变量已设置"
EOF
chmod +x setup_cosyvoice_env.sh

echo ""
echo "=========================================="
echo "✅ 安装完成!"
echo "=========================================="
echo ""
echo "使用方法:"
echo "  1. 设置环境变量: source setup_cosyvoice_env.sh"
echo "  2. 修改 config/config.yaml:"
echo "     tts:"
echo "       backend: cosyvoice_local"
echo "       model_name: pretrained_models/CosyVoice-300M-SFT"
echo "  3. 启动应用: uv run python -m playlet_clip.main"
