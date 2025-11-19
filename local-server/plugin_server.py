#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Higress WASM 插件服务器
提供 WASM 文件下载服务
"""

import os
import sys
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import mimetypes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WasmPluginHandler(BaseHTTPRequestHandler):
    """WASM 插件 HTTP 处理器"""

    def __init__(self, *args, **kwargs):
        # WASM 文件目录
        self.wasm_dir = "/data/higress-data/wasm"
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """处理 GET 请求"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            logger.info(f"收到请求: {self.path}")

            # 处理插件请求
            if path.startswith('/plugins/'):
                self._handle_plugin_request(path)
            elif path == '/health':
                self._handle_health_check()
            elif path == '/':
                self._handle_index()
            else:
                self._send_error_response(404, "Not Found")

        except Exception as e:
            logger.error(f"处理请求时出错: {e}")
            self._send_error_response(500, f"Internal Server Error: {str(e)}")

    def _handle_plugin_request(self, path):
        """处理插件请求"""
        # 提取插件名称，支持 /plugins/plugin-name 和 /plugins/plugin-name.wasm 格式
        plugin_name = path.replace('/plugins/', '').replace('.wasm', '')

        # 构建 WASM 文件路径
        wasm_file = os.path.join(self.wasm_dir, f"{plugin_name}.wasm")

        logger.info(f"查找插件文件: {wasm_file}")

        if os.path.exists(wasm_file):
            self._serve_wasm_file(wasm_file, plugin_name)
        else:
            logger.warning(f"插件文件不存在: {wasm_file}")
            self._send_error_response(404, f"Plugin {plugin_name} not found")

    def _serve_wasm_file(self, file_path, plugin_name):
        """提供 WASM 文件"""
        try:
            file_size = os.path.getsize(file_path)

            # 设置响应头
            self.send_response(200)
            self.send_header('Content-Type', 'application/wasm')
            self.send_header('Content-Length', str(file_size))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers',
                             'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()

            # 发送文件内容
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)  # 8KB 块
                    if not chunk:
                        break
                    self.wfile.write(chunk)

            logger.info(f"成功提供插件: {plugin_name} ({file_size} bytes)")

        except Exception as e:
            logger.error(f"提供 WASM 文件时出错: {e}")
            self._send_error_response(500, f"Error serving file: {str(e)}")

    def _handle_health_check(self):
        """健康检查"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        health_data = {
            "status": "healthy",
            "wasm_dir": self.wasm_dir,
            "available_plugins": self._get_available_plugins()
        }

        self.wfile.write(json.dumps(health_data, indent=2).encode('utf-8'))

    def _handle_index(self):
        """首页，显示可用插件列表"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

        plugins = self._get_available_plugins()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Higress WASM 插件服务器</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .plugin {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
                .plugin-name {{ font-weight: bold; color: #333; }}
                .plugin-url {{ color: #666; font-family: monospace; }}
            </style>
        </head>
        <body>
            <h1>Higress WASM 插件服务器</h1>
            <p>WASM 目录: <code>{self.wasm_dir}</code></p>
            <h2>可用插件:</h2>
        """

        for plugin in plugins:
            html += f"""
            <div class="plugin">
                <div class="plugin-name">{plugin['name']}</div>
                <div class="plugin-url">GET /plugins/{plugin['name']}</div>
                <div>大小: {plugin['size']} bytes</div>
            </div>
            """

        html += """
        </body>
        </html>
        """

        self.wfile.write(html.encode('utf-8'))

    def _get_available_plugins(self):
        """获取可用插件列表"""
        plugins = []
        try:
            if os.path.exists(self.wasm_dir):
                for filename in os.listdir(self.wasm_dir):
                    if filename.endswith('.wasm'):
                        file_path = os.path.join(self.wasm_dir, filename)
                        plugin_name = filename.replace('.wasm', '')
                        file_size = os.path.getsize(file_path)
                        plugins.append({
                            'name': plugin_name,
                            'filename': filename,
                            'size': file_size
                        })
        except Exception as e:
            logger.error(f"获取插件列表时出错: {e}")

        return sorted(plugins, key=lambda x: x['name'])

    def _send_error_response(self, code, message):
        """发送错误响应"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        error_data = {
            "error": message,
            "code": code
        }

        self.wfile.write(json.dumps(error_data, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        """重写日志方法"""
        logger.info(f"{self.address_string()} - {format % args}")


def main():
    """主函数"""
    # 检查 WASM 目录是否存在
    wasm_dir = "/data/higress-data/wasm"
    if not os.path.exists(wasm_dir):
        logger.error(f"WASM 目录不存在: {wasm_dir}")
        sys.exit(1)

    # 检查 key_auth.wasm 文件
    key_auth_file = os.path.join(wasm_dir, "key_auth.wasm")
    if not os.path.exists(key_auth_file):
        logger.warning(f"key_auth.wasm 文件不存在: {key_auth_file}")

    # 服务器配置
    host = "0.0.0.0"
    port = 8888

    try:
        # 创建服务器
        server = HTTPServer((host, port), WasmPluginHandler)
        logger.info(f"WASM 插件服务器启动成功")
        logger.info(f"监听地址: http://{host}:{port}")
        logger.info(f"WASM 目录: {wasm_dir}")
        logger.info(f"健康检查: http://{host}:{port}/health")
        logger.info(f"插件列表: http://{host}:{port}/")

        # 启动服务器
        server.serve_forever()

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
        server.shutdown()
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()