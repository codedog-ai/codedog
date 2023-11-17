# 🐶 Codedog

[![Checkstyle](https://github.com/Arcadia822/codedog/actions/workflows/flake8.yml/badge.svg)](https://github.com/Arcadia822/codedog/actions/workflows/flake8.yml)
[![Pytest](https://github.com/Arcadia822/codedog/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/Arcadia822/codedog/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Arcadia822/ce38dae58995aeffef42065093fcfe84/raw/codedog_master.json)](https://github.com/Arcadia822/codedog/actions/workflows/test.yml)
[![](https://dcbadge.vercel.app/api/server/wzfsvaDQ?compact=true&style=flat)](https://discord.gg/6adMQxSpJS)

Review your Github/Gitlab PR with ChatGPT

## What is codedog?

Codedog is a code review automation tool benefit the power of LLM (Large Language Model) to help developers
review code faster and more accurately.

Codedog is based on OpenAI API and Langchain.

## Quickstart

### Review your pull request via Github App

Install our github app [codedog-assistant](https://github.com/apps/codedog-assistant)

### Start with your own code

As a example, we will use codedog to review a pull request on Github.

0. Install codedog

```bash
pip install codedog
```

codedog currently only supports python 3.10.

1. Get a github pull request
```python
from github import Github

github_token="YOUR GITHUB TOKEN"
repository = "codedog-ai/codedog"
pull_request_number = 2

github = Github(github_token)
retriever = GithubRetriever(github, repository, pull_requeest_number)
```


2. Summarize the pull request

Since `PRSummaryChain` uses langchain's output parser, we suggest to use GPT-4 to improve formatting accuracy.

```python
from codedog.chains import PRSummaryChain

openai_api_key = "YOUR OPENAI API KEY WITH GPT4"

# PR Summary uses output parser
llm35 = ChatOpenAI(openai_api_key=openai_api_key, model="gpt-3.5-turbo")

llm4 = ChatOpenAI(openai_api_key=openai_api_key, model="gpt-4")

summary_chain = PRSummaryChain.from_llm(code_summary_llm=llm35, pr_summary_llm=llm4, verbose=True)

summary = summary_chain({"pull_request": retriever.pull_request}, include_run_info=True)

print(summary)
```

3. Review each code file changes in the pull request

```python
review_chain = CodeReviewChain.from_llm(llm=llm35, verbose=True)

reviews = review_chain({"pull_request": retriever.pull_request}, include_run_info=True)

print(reviews)
```

4. Format review result

Format review result to a markdown report.

```python
from codedog.actors.reporters.pull_request import PullRequestReporter

reporter = PullRequestReporter(
    pr_summary=summary["pr_summary"],
    code_summaries=summary["code_summaries"],
    pull_request=retriever.pull_request,
    code_reviews=reviews["code_reviews"],
)

md_report = reporter.report()

print(md_report)
```

## Deployment

We have a simple server demo to deploy codedog as a service with fastapi and handle Github webhook.
Basicly you can also use it with workflow or Github Application.

see `examples/server.py`

Note that codedog don't have fastapi and unicorn as dependency, you need to install them manually.

## Configuration

Codedog currently load config from environment variables.

settings:

| Config Name                    | Required | Default           | Description                             |
| ------------------------------ | -------- | ----------------- | --------------------------------------- |
| OPENAI_API_KEY                 | No       |                   | Api Key for calling openai gpt api      |
| AZURE_OPENAI                   | No       |                   | Use azure openai if not blank           |
| AZURE_OPENAI_API_KEY           | No       |                   | Azure openai api key                    |
| AZURE_OPENAI_API_BASE          | No       |                   | Azure openai api base                   |
| AZURE_OPENAI_DEPLOYMENT_ID     | No       |                   | Azure openai deployment id for gpt 3.5  |
| AZURE_OPENAI_GPT4_DEPLOYMENT_ID| No       |                   | Azure openai deployment id for gpt 4    |
