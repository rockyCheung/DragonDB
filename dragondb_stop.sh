#!/bin/bash
# DragonDB 停止脚本
# 用法: ./dragondb_stop.sh [选项]
# 选项:
#   --node <节点名>      停止单个节点
#   --all                停止所有节点
#   -h, --help           显示帮助

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 显示帮助
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "DragonDB 停止脚本"
    echo "用法: $0 [--node <节点名> | --all]"
    echo ""
    echo "示例:"
    echo "  $0 --node node1            # 停止节点 node1"
    echo "  $0 --all                    # 停止所有节点"
    exit 0
fi

# 检查参数
if [ $# -eq 0 ]; then
    echo "错误: 请指定 --node 或 --all"
    echo "查看帮助: $0 --help"
    exit 1
fi

# 停止指定节点
stop_node() {
    local node_name=$1
    # 查找包含 "python start.py --node $node_name" 的进程
    pids=$(ps aux | grep "python.*start.py.*--node.*$node_name" | grep -v grep | awk '{print $2}')
    if [ -z "$pids" ]; then
        echo "未找到节点 $node_name 的进程"
    else
        echo "正在停止节点 $node_name (PID: $pids)"
        kill $pids 2>/dev/null || echo "进程 $pids 可能已停止"
    fi
}

# 停止所有节点
stop_all() {
    # 查找所有包含 "python start.py --node" 的进程
    pids=$(ps aux | grep "python.*start.py.*--node" | grep -v grep | awk '{print $2}')
    if [ -z "$pids" ]; then
        echo "未找到任何 DragonDB 节点进程"
    else
        echo "正在停止所有节点 (PID: $pids)"
        kill $pids 2>/dev/null || echo "部分进程可能已停止"
    fi
}

# 解析参数
case "$1" in
    --node)
        if [ -z "$2" ]; then
            echo "错误: --node 需要指定节点名"
            exit 1
        fi
        stop_node "$2"
        ;;
    --all)
        stop_all
        ;;
    *)
        echo "未知参数: $1"
        echo "查看帮助: $0 --help"
        exit 1
        ;;
esac

echo "完成"