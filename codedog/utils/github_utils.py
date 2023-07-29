import time

import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from github import Github

default_url = "https://api.github.com"


def load_github_client(
    *,
    token: str = None,
    installation_id: int = None,
    private_key: str = None,
    app_id: str = None,
    base_url: str = default_url,
):
    if installation_id is not None and private_key is not None and app_id is not None:
        _token = get_token_by_installation(installation_id, private_key, app_id, base_url)
        client = Github(_token)
    elif token:
        client = Github(token)
    else:
        raise RuntimeError("Could not find a valid way to initiate Github Client.")
    return client


def get_token_by_installation(installation_id: int, private_key: str, app_id: str, base_url: str) -> str:
    jwt_token = get_jwt_token(private_key, app_id)
    access_token = get_access_token_by_installation_id(installation_id, jwt_token, base_url)
    return access_token


def get_jwt_token(private_key: str, app_id: str):
    # 获取当前时间
    now = int(time.time())

    # 准备 JWT 的 payload
    payload = {
        # 发行人
        "iat": now,
        # JWT 的过期时间，这里设置为1分钟后
        "exp": now + (10 * 60),
        # GitHub App 的 ID
        "iss": app_id,
    }

    # 生成JWT
    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
    return jwt_token


def get_access_token_by_installation_id(installation_id: int, jwt_token: str, base_url: str):
    if installation_id is None:
        return None
    # 使用installation_id生成访问令牌
    # TODO: dynatic github base url
    token_url = f"{base_url}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": "Bearer {}".format(jwt_token),
        "Accept": "application/vnd.github.machine-man-preview+json",
    }
    response = requests.post(token_url, headers=headers)
    response.raise_for_status()
    token_info = response.json()
    return token_info["token"]


def load_private_key(filename):
    # 从文件中读取你的私钥
    with open(filename, "rb") as key_file:
        private_key = serialization.load_pem_private_key(key_file.read(), password=None, backend=default_backend())
    return private_key
