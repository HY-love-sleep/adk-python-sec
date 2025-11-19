from flask import Flask, jsonify, request
import requests
import time
import threading
import atexit

app = Flask(__name__)

# Nacos 配置
NACOS_SERVER = "http://192.168.39.55:8848"
SERVICE_NAME = "user-service"
SERVICE_IP = "192.168.39.55"
SERVICE_PORT = 8082
NAMESPACE_ID = "public"
GROUP_NAME = "DEFAULT_GROUP"


def register_to_nacos():
    """向 Nacos 注册服务"""
    url = f"{NACOS_SERVER}/nacos/v1/ns/instance"
    data = {
        'serviceName': SERVICE_NAME,
        'ip': SERVICE_IP,
        'port': SERVICE_PORT,
        'namespaceId': NAMESPACE_ID,
        'groupName': GROUP_NAME,
        'healthy': True,
        'weight': 1.0
    }

    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"服务注册成功: {SERVICE_NAME}@{SERVICE_IP}:{SERVICE_PORT}")
        else:
            print(f"服务注册失败: {response.text}")
    except Exception as e:
        print(f"服务注册异常: {e}")


def deregister_from_nacos():
    """从 Nacos 注销服务"""
    url = f"{NACOS_SERVER}/nacos/v1/ns/instance"
    data = {
        'serviceName': SERVICE_NAME,
        'ip': SERVICE_IP,
        'port': SERVICE_PORT,
        'namespaceId': NAMESPACE_ID,
        'groupName': GROUP_NAME
    }

    try:
        response = requests.delete(url, data=data)
        if response.status_code == 200:
            print(f"服务注销成功: {SERVICE_NAME}")
        else:
            print(f"服务注销失败: {response.text}")
    except Exception as e:
        print(f"服务注销异常: {e}")


def heartbeat():
    """心跳检测，保持服务活跃"""
    while True:
        time.sleep(30)  # 每30秒发送一次心跳
        register_to_nacos()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})


@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify({
        "users": ["alice", "bob", "charlie"],
        "total": 3,
        "timestamp": time.time()
    })


@app.route('/api/users', methods=['POST'])
def create_user():
    return jsonify({
        "message": "User created successfully",
        "timestamp": time.time()
    })

@app.route('/api/user_age', methods=['GET'])
def get_user_age_by_param():
    """通过 query 参数查询用户年龄 (mock 数据)"""
    username = request.args.get("username")

    if not username:
        return jsonify({
            "error": "Missing required parameter 'username'",
            "timestamp": time.time()
        }), 400

    mock_ages = {
        "hongyan": 28,
        "zhangchang": 27,
        "洪岩": 28,
        "张畅": 27
    }

    age = mock_ages.get(username)
    if age is not None:
        return jsonify({
            "username": username,
            "age": age,
            "timestamp": time.time()
        })
    else:
        return jsonify({
            "error": f"User '{username}' not found",
            "timestamp": time.time()
        }), 404


if __name__ == '__main__':
    # 启动时注册服务
    register_to_nacos()

    # 注册退出时注销服务
    atexit.register(deregister_from_nacos)

    # 启动心跳线程
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    # 启动 Flask 应用
    app.run(host='0.0.0.0', port=8082, debug=True)