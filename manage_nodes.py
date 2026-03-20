#!/usr/bin/env python3
import sys
import os
import yaml
import asyncio
import aiohttp
import argparse
from urllib.parse import urljoin

async def send_request(url, payload):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                return result, resp.status
        except Exception as e:
            return {'error': str(e)}, 500

async def add_node(config_path, new_node_id, host, port, data_dir):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    nodes = config.get('nodes', {})
    if new_node_id in nodes:
        print(f"Error: Node {new_node_id} already exists in config")
        return 1
    if not nodes:
        print("Error: No nodes in config")
        return 1
    first_node_id = list(nodes.keys())[0]
    first_node = nodes[first_node_id]
    base_url = f"http://{first_node['host']}:{first_node['port']}"
    admin_url = urljoin(base_url, '/admin/cluster/add_node')
    payload = {
        'node_id': new_node_id,
        'host': host,
        'port': port,
        'data_dir': data_dir or f"./data/{new_node_id}"
    }
    print(f"Sending add request to {admin_url}")
    result, status = await send_request(admin_url, payload)
    if status == 200:
        print("Node added successfully.")
        nodes[new_node_id] = {'host': host, 'port': port, 'data_dir': payload['data_dir']}
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        print("Config updated.")
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1

async def remove_node(config_path, node_id):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    nodes = config.get('nodes', {})
    if node_id not in nodes:
        print(f"Error: Node {node_id} not found in config")
        return 1
    first_node_id = list(nodes.keys())[0]
    first_node = nodes[first_node_id]
    base_url = f"http://{first_node['host']}:{first_node['port']}"
    admin_url = urljoin(base_url, '/admin/cluster/remove_node')
    payload = {'node_id': node_id}
    print(f"Sending remove request to {admin_url}")
    result, status = await send_request(admin_url, payload)
    if status == 200:
        print("Node removed successfully.")
        del nodes[node_id]
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        print("Config updated.")
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1

def main():
    parser = argparse.ArgumentParser(description='DragonDB dynamic node management')
    parser.add_argument('--config', default='config.yaml', help='Cluster config file')
    subparsers = parser.add_subparsers(dest='command', required=True)

    parser_add = subparsers.add_parser('add', help='Add a new node')
    parser_add.add_argument('node_id')
    parser_add.add_argument('--host', required=True)
    parser_add.add_argument('--port', type=int, required=True)
    parser_add.add_argument('--data-dir', default=None)

    parser_remove = subparsers.add_parser('remove', help='Remove a node')
    parser_remove.add_argument('node_id')

    args = parser.parse_args()
    if args.command == 'add':
        exit(asyncio.run(add_node(args.config, args.node_id, args.host, args.port, args.data_dir)))
    elif args.command == 'remove':
        exit(asyncio.run(remove_node(args.config, args.node_id)))
    else:
        parser.print_help()
        exit(1)

if __name__ == '__main__':
    main()