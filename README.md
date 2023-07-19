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

| Environment Variable | Necessary | Default | Description |
|---|---|---|---|
| CODEDOG_SERVER                | No  | 0.0.0.0        | Server address                               |
| CODEDOG_PORT                  | No  | 32167          | Server port                                  |
| CODEDOG_WORKER_NUM            | No  | 1              | Server worker number                         |
| GITHUB_TOKEN                  | No  |                | Retrive github project content and comment   |
| OPENAI_API_KEY                | NO  |                | Api Key for calling openai api               |
| OPENAI_MODEL                  | No  | gpt-3.5-turbo  | openai model                                 |
| AZURE_OPENAI                  | No  |                | use azure openai if not blank                |
| AZURE_OPENAI_API_KEY          | No  |                | azure openai api key                         |
| AZURE_OPENAI_API_BASE         | No  |                | azure openai api base                        |
| AZURE_OPENAI_DEPLOYMENT_ID    | No  |                | azure openai deployment id                   |
| AZURE_OPENAI_MODEL            | No  | gpt-3.5-turbo  | azure openai model                           |

## Start Server
```shell
poetry run start
```

## How To Use

### Github


### Gitlab
