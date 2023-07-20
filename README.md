# 🐶 Codedog

[![Checkstyle](https://github.com/Arcadia822/codedog/actions/workflows/flake8.yml/badge.svg)](https://github.com/Arcadia822/codedog/actions/workflows/flake8.yml)
[![Pytest](https://github.com/Arcadia822/codedog/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/Arcadia822/codedog/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Arcadia822/ce38dae58995aeffef42065093fcfe84/raw/codedog_master.json)](https://github.com/Arcadia822/codedog/actions/workflows/test.yml)


Review your Github/Gitlab PR with ChatGPT

![Design](docs/design.png)

## Setup Project

```shell
poetry install --with dev
```

## Configuration

settings:

| 环境变量                | 是否必要 | 默认值                 | 说明                                |
| ----------------------- | -------- | ---------------------- | ----------------------------------- |
| CODEDOG_WORKER_NUM      | 否       | 1                      | 服务线程数                          |
| CODEDOG_ENV             | 否       | "unknown"              | 表明 codedog 实例所属环境           |
| DATADOG_METRIC          | 否       |                        | 值为 True 时向 datadog 发送统计指标 |
| DATADOG_AGENT_HOST      | 否       | localhost              | datadog agent host                  |
| DATADOG_DOGSTATSD_PORT  | 否       | 8125                   | datadog agent dogstatsd port        |
| GITHUB_TOKEN            | 否       |                        | 用于连接 github 和评论              |
| GITHUB_APP_ID           | 否       | 0                      | 用于配置 github app id              |
| GITHUB_PRIVATE_KEY_PATH | 否       | "/app/private_key.pem" | 用于生成 github app jwt token       |
| OPENAI_API_KEY          | 是       |                        | 调用 OPENAI 的 API KEY              |
| OPENAI_PROXY            | 否       |                        | 设置到 openai.proxy                 |

## Start Server

```shell
poetry run start
```

## How To Use

### Github


### Gitlab
