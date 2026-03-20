# start.py
import os
import sys
import yaml
import asyncio
import argparse
from multiprocessing import Process

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from node import DragonDBNode

def load_config(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

async def run_node(node_id, node_config, all_nodes_info, global_cluster_opts):
    """启动单个节点"""
    node = DragonDBNode(
        node_id=node_id,
        all_nodes_info=all_nodes_info,
        http_port=node_config['port'],
        data_dir=node_config.get('data_dir', f"./data/{node_id}"),
        storage_options=node_config.get('storage_options', {}),
        cluster_opts=global_cluster_opts
    )
    await node.start()
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()

def start_node_process(node_id, node_config, all_nodes_info, global_cluster_opts):
    asyncio.run(run_node(node_id, node_config, all_nodes_info, global_cluster_opts))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.yaml')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--node', help='启动单个节点')
    group.add_argument('--all', action='store_true', help='启动所有节点')
    args = parser.parse_args()

    config = load_config(args.config)
    global_cluster_opts = config.get('cluster', {})
    nodes_config = config.get('nodes', {})
    if not nodes_config:
        print("错误: 配置文件中未定义任何节点")
        sys.exit(1)

    # 构建所有节点信息字典（包含地址等）
    all_nodes_info = {}
    for node_id, info in nodes_config.items():
        all_nodes_info[node_id] = {
            'host': info['host'],
            'port': info['port'],
            'data_dir': info.get('data_dir', f"./data/{node_id}"),
            'storage_options': info.get('storage_options', {})
        }

    if args.node:
        if args.node not in nodes_config:
            print(f"节点 {args.node} 未定义")
            sys.exit(1)
        asyncio.run(run_node(args.node, nodes_config[args.node], all_nodes_info, global_cluster_opts))
    elif args.all:
        processes = []
        for node_id, node_config in nodes_config.items():
            p = Process(target=start_node_process, args=(node_id, node_config, all_nodes_info, global_cluster_opts))
            p.start()
            processes.append(p)
        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            for p in processes:
                p.terminate()
            for p in processes:
                p.join()

if __name__ == "__main__":
    main()