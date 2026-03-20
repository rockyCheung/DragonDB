## DragonDB Shell 启动脚本

### `dragondb.sh` (或 `run.sh`)

```bash
#!/bin/bash
# DragonDB 启动脚本
# 用法: ./dragondb_start.sh [选项]
# 选项:
#   --node <节点名>      启动单个节点
#   --all                启动所有节点
#   --config <文件路径>  指定配置文件 (默认: ./config.yaml)
#   -h, --help           显示帮助

set -e  # 遇到错误立即退出

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 显示帮助
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "DragonDB 启动脚本"
    echo "用法: $0 [--node <节点名> | --all] [--config <配置文件路径>]"
    echo ""
    echo "示例:"
    echo "  $0 --node node1            # 启动节点 node1"
    echo "  $0 --all                    # 启动所有节点"
    echo "  $0 --config myconfig.yaml --node node2"
    echo ""
    echo "配置文件默认路径: ./config.yaml"
    exit 0
fi

# 检查 Python 3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请安装 Python 3.10 或更高版本"
    exit 1
fi

# 可选：检查 Python 版本是否满足 3.10+
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.10"
if [[ $(echo "$python_version < $required_version" | bc) -eq 1 ]]; then
    echo "错误: Python 版本必须 >= 3.10，当前版本为 $python_version"
    exit 1
fi

# 提示用户安装依赖（但不会自动安装）
if [ ! -f "requirements.txt" ]; then
    echo "警告: 未找到 requirements.txt 文件，请确保依赖已安装"
else
    echo "提示: 请确保已安装所需依赖，执行以下命令："
    echo "  pip install -r requirements.txt"
fi

# 将项目根目录添加到 PYTHONPATH（确保模块可导入）
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# 执行 Python 启动脚本
echo "正在启动 DragonDB..."
exec python3 start.py "$@"
```

### 使用说明

1. **赋予执行权限**：
   ```bash
   chmod +x dragondb_start.sh
   ```

2. **启动单个节点**：
   ```bash
   ./dragondb_start.sh --node node1
   ```

3. **启动所有节点**：
   ```bash
   ./dragondb_start.sh --all
   ```

4. **指定自定义配置文件**：
   ```bash
   ./dragondb_start.sh --config /path/to/config.yaml --node node2
   ```

### 注意事项
- 该脚本假设 `start.py` 和 `requirements.txt` 与脚本在同一目录。
- 脚本不会自动安装 Python 依赖，只会给出提示，以避免干扰用户环境。
- 使用 `exec` 将 Python 进程替换为当前 shell 进程，使信号（如 Ctrl+C）能直接传递给 Python 程序。
- 如果遇到 `bc: command not found` 错误（用于版本比较），可忽略版本检查或改用 `awk` 比较。若系统无 `bc`，可注释掉版本检查部分。