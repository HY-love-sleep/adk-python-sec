# Local Server - Higress WASM 插件服务器

## 📋 目录概述

本目录提供两个核心服务：

1. **WASM 插件服务器** - 为 Higress 网关提供 WASM 插件下载服务
2. **模拟用户服务** - 提供用户数据 API 并注册到 Nacos 服务注册中心

## 🗂️ 目录结构

```
local-server/
├── app.py                      # Flask 用户服务（Nacos 注册）
├── plugin_server.py            # WASM 插件 HTTP 服务器（独立运行）
├── deploy/                     # Docker 部署配置
│   ├── Dockerfile.wasm-server  # WASM 服务器 Docker 镜像
│   ├── wasm_server.py          # WASM 服务器（容器内运行）
│   ├── key-auth.wasm           # 密钥认证插件
│   └── mcp-server.wasm         # MCP 服务器插件
└── README.md                   # 本文档
```

---

## 🚀 快速开始

### 方式 1：本地运行 WASM 插件服务器

#### 前置条件

- Python 3.8+
- WASM 插件文件（`.wasm`）

#### 启动步骤

```bash
# 进入目录
cd local-server

# 修改 plugin_server.py 中的 WASM 目录路径（如需要）
# 默认路径：/data/higress-data/wasm

# 启动服务器
python3 plugin_server.py
```

服务器将在 `http://0.0.0.0:8888` 启动，支持以下端点：

- `GET /` - 插件列表页面（Web UI）
- `GET /health` - 健康检查
- `GET /plugins/{plugin-name}` - 下载指定 WASM 插件

**示例请求**：
```bash
# 查看可用插件
curl http://localhost:8888/

# 健康检查
curl http://localhost:8888/health

# 下载插件
curl -O http://localhost:8888/plugins/key-auth
curl -O http://localhost:8888/plugins/mcp-server
```

---

### 方式 2：Docker 容器运行

#### 构建镜像

```bash
cd local-server/deploy

# 构建 WASM 服务器镜像
docker build -t wasm-plugin-server:latest -f Dockerfile.wasm-server .
```

#### 运行容器

```bash
# 方式 A：使用本地 WASM 目录
docker run -d \
  --name wasm-server \
  -p 8888:8080 \
  -v /path/to/wasm-plugins:/data/wasm-plugins \
  wasm-plugin-server:latest

# 方式 B：将 WASM 文件复制到容器
docker run -d \
  --name wasm-server \
  -p 8888:8080 \
  wasm-plugin-server:latest

# 复制 WASM 文件到容器
docker cp key-auth.wasm wasm-server:/data/wasm-plugins/
docker cp mcp-server.wasm wasm-server:/data/wasm-plugins/

# 重启容器
docker restart wasm-server
```

#### 验证运行

```bash
# 检查容器状态
docker ps | grep wasm-server

# 查看日志
docker logs -f wasm-server

# 健康检查
curl http://localhost:8888/health
```

---

## 📦 WASM 插件管理

### 可用插件

| 插件名称 | 文件名 | 功能描述 |
|---------|--------|---------|
| `key-auth` | `key-auth.wasm` | API 密钥认证插件 |
| `mcp-server` | `mcp-server.wasm` | MCP 服务器插件 |

### 添加新插件

```bash
# 本地运行方式
cp your-plugin.wasm /data/higress-data/wasm/

# Docker 方式
docker cp your-plugin.wasm wasm-server:/data/wasm-plugins/
docker restart wasm-server
```

### 插件 URL 格式

```
http://<server-ip>:8888/plugins/<plugin-name>
```

**示例**：
- `http://192.168.39.55:8888/plugins/key-auth`
- `http://192.168.39.55:8888/plugins/mcp-server`

---

## 🧪 模拟用户服务（app.py）

### 功能特性

- 提供用户数据 RESTful API
- 自动注册到 Nacos 服务注册中心
- 支持心跳保活（每 30 秒）
- 支持优雅关闭（自动注销服务）

### 启动服务

```bash
# 启动用户服务
python3 app.py
```

服务将在 `http://0.0.0.0:8082` 启动。

### API 端点

| 方法 | 路径 | 描述 | 示例 |
|-----|------|------|------|
| `GET` | `/health` | 健康检查 | `curl http://localhost:8082/health` |
| `GET` | `/api/users` | 获取用户列表 | `curl http://localhost:8082/api/users` |
| `POST` | `/api/users` | 创建用户 | `curl -X POST http://localhost:8082/api/users` |
| `GET` | `/api/user_age?username=xxx` | 获取用户年龄 | `curl http://localhost:8082/api/user_age?username=hongyan` |

### Nacos 配置

修改 `app.py` 中的配置：

```python
NACOS_SERVER = "http://192.168.39.55:8848"
SERVICE_NAME = "user-service"
SERVICE_IP = "192.168.39.55"
SERVICE_PORT = 8082
NAMESPACE_ID = "public"
GROUP_NAME = "DEFAULT_GROUP"
```

---

## 🔧 配置说明

### WASM 插件服务器配置

在 `plugin_server.py` 中修改：

```python
class WasmPluginHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # 修改 WASM 文件目录
        self.wasm_dir = "/data/higress-data/wasm"  # ← 自定义路径
        super().__init__(*args, **kwargs)

def main():
    # 修改监听地址和端口
    host = "0.0.0.0"  # ← 绑定地址
    port = 8888       # ← 监听端口
```

### 用户服务配置

在 `app.py` 中修改：

```python
# Nacos 服务器地址
NACOS_SERVER = "http://<nacos-ip>:8848"

# 服务配置
SERVICE_NAME = "user-service"
SERVICE_IP = "<your-ip>"
SERVICE_PORT = 8082
```

---

## 🔗 与 Higress 集成

### 在 Higress 中使用 WASM 插件

#### 步骤 1：配置插件源

在 Higress 配置中添加插件源：

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: key-auth-plugin
  namespace: higress-system
spec:
  url: http://192.168.39.55:8888/plugins/key-auth
  phase: AUTHN
  priority: 100
```

#### 步骤 2：应用插件到路由

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: user-service-ingress
  annotations:
    higress.io/wasm-plugins: key-auth-plugin
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 8082
```

#### 步骤 3：验证插件加载

```bash
# 查看 Higress 日志
kubectl logs -n higress-system deployment/higress-gateway -f

# 测试 API（应该需要认证）
curl -H "Host: api.example.com" http://<higress-ip>/api/users
```

---

## 🐛 故障排查

### 问题 1：WASM 插件服务器无法启动

**原因**：WASM 目录不存在

**解决**：
```bash
# 创建目录
mkdir -p /data/higress-data/wasm

# 或修改 plugin_server.py 中的路径
```

### 问题 2：Higress 无法下载插件

**检查步骤**：

```bash
# 1. 检查服务器是否运行
curl http://<server-ip>:8888/health

# 2. 检查插件是否存在
curl http://<server-ip>:8888/

# 3. 测试下载
curl -I http://<server-ip>:8888/plugins/key-auth

# 4. 检查网络连通性（从 Higress Pod）
kubectl exec -n higress-system deployment/higress-gateway -- \
  curl http://<server-ip>:8888/health
```

### 问题 3：Nacos 注册失败

**检查步骤**：

```bash
# 1. 检查 Nacos 可达性
curl http://<nacos-ip>:8848/nacos/

# 2. 查看服务日志
# 日志中应该有 "服务注册成功" 消息

# 3. 在 Nacos 控制台验证
# 访问 http://<nacos-ip>:8848/nacos/
# 查看 "服务管理 -> 服务列表" 是否有 user-service
```

### 问题 4：CORS 错误

如果从浏览器访问遇到 CORS 错误，WASM 服务器已经配置了 CORS 头：

```python
self.send_header('Access-Control-Allow-Origin', '*')
self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
```

---

## 📊 监控与日志

### WASM 插件服务器日志

```bash
# 本地运行
# 日志直接输出到控制台

# Docker 运行
docker logs -f wasm-server
```

日志格式：
```
2024-01-01 10:00:00,123 - INFO - WASM 插件服务器启动成功
2024-01-01 10:00:01,234 - INFO - 收到请求: /plugins/key-auth
2024-01-01 10:00:01,235 - INFO - 查找插件文件: /data/wasm-plugins/key-auth.wasm
2024-01-01 10:00:01,345 - INFO - 成功提供插件: key-auth (123456 bytes)
```

### 健康检查响应示例

```json
{
  "status": "healthy",
  "wasm_dir": "/data/higress-data/wasm",
  "available_plugins": [
    {
      "name": "key-auth",
      "filename": "key-auth.wasm",
      "size": 123456
    },
    {
      "name": "mcp-server",
      "filename": "mcp-server.wasm",
      "size": 234567
    }
  ]
}
```

---

## 🔐 安全建议

1. **不要在生产环境暴露插件服务器到公网**
   - 使用内网地址
   - 或配置防火墙规则

2. **添加认证机制**（可选）
   ```python
   # 在 do_GET 方法中添加 API Key 验证
   auth_header = self.headers.get('Authorization')
   if auth_header != 'Bearer your-secret-key':
       self._send_error_response(401, "Unauthorized")
       return
   ```

3. **使用 HTTPS**（生产环境）
   - 配置 TLS 证书
   - 使用 Nginx/Apache 作为反向代理

4. **限制访问来源**
   ```python
   # 只允许 Higress Pod IP 访问
   allowed_ips = ['192.168.39.0/24']
   if not is_ip_allowed(self.client_address[0], allowed_ips):
       self._send_error_response(403, "Forbidden")
       return
   ```

---

## 📚 参考资料

- [Higress 官方文档](https://higress.io/zh-cn/docs/user/wasm-go.html)
- [WebAssembly 规范](https://webassembly.org/)
- [Nacos 服务注册](https://nacos.io/zh-cn/docs/open-api.html)
- [Flask 文档](https://flask.palletsprojects.com/)

---


**最后更新**: 2025-11-19

