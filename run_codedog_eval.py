#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from codedog.utils.git_log_analyzer import get_file_diffs_by_timeframe
from codedog.utils.code_evaluator import DiffEvaluator, generate_evaluation_markdown
from codedog.utils.langchain_utils import load_model_by_name
from codedog.utils.email_utils import send_report_email
from langchain_community.callbacks.manager import get_openai_callback


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="CodeDog Eval - 按时间段和开发者评价代码提交")
    
    # 必需参数
    parser.add_argument("author", help="开发者名称或邮箱（部分匹配）")
    
    # 可选参数
    parser.add_argument("--start-date", help="开始日期 (YYYY-MM-DD)，默认为7天前")
    parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)，默认为今天")
    parser.add_argument("--repo", help="Git仓库路径，默认为当前目录")
    parser.add_argument("--include", help="包含的文件扩展名，逗号分隔，例如 .py,.js")
    parser.add_argument("--exclude", help="排除的文件扩展名，逗号分隔，例如 .md,.txt")
    parser.add_argument("--model", help="评价模型，默认为环境变量CODE_REVIEW_MODEL或gpt-3.5")
    parser.add_argument("--email", help="报告发送的邮箱地址，逗号分隔")
    parser.add_argument("--output", help="报告输出文件路径，默认为 codedog_eval_<author>_<date>.md")
    
    return parser.parse_args()


async def main():
    """主程序"""
    args = parse_args()
    
    # 处理日期参数
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    start_date = args.start_date or week_ago
    end_date = args.end_date or today
    
    # 生成默认输出文件名
    if not args.output:
        author_slug = args.author.replace("@", "_at_").replace(" ", "_").replace("/", "_")
        date_slug = datetime.now().strftime("%Y%m%d")
        args.output = f"codedog_eval_{author_slug}_{date_slug}.md"
    
    # 处理文件扩展名参数
    include_extensions = [ext.strip() for ext in args.include.split(",")] if args.include else None
    exclude_extensions = [ext.strip() for ext in args.exclude.split(",")] if args.exclude else None
    
    # 获取模型
    model_name = args.model or os.environ.get("CODE_REVIEW_MODEL", "gpt-3.5")
    model = load_model_by_name(model_name)
    
    print(f"正在评价 {args.author} 在 {start_date} 至 {end_date} 期间的代码提交...")
    
    # 获取提交和diff
    commits, commit_file_diffs = get_file_diffs_by_timeframe(
        args.author, 
        start_date, 
        end_date, 
        args.repo,
        include_extensions,
        exclude_extensions
    )
    
    if not commits:
        print(f"未找到 {args.author} 在指定时间段内的提交记录")
        return
    
    print(f"找到 {len(commits)} 个提交，共修改了 {sum(len(diffs) for diffs in commit_file_diffs.values())} 个文件")
    
    # 初始化评价器
    evaluator = DiffEvaluator(model)
    
    # 计时和统计
    start_time = time.time()
    
    with get_openai_callback() as cb:
        # 执行评价
        print("正在评价代码提交...")
        evaluation_results = await evaluator.evaluate_commits(commits, commit_file_diffs)
        
        # 生成Markdown报告
        report = generate_evaluation_markdown(evaluation_results)
        
        # 计算成本和时间
        total_cost = cb.total_cost
        total_tokens = cb.total_tokens
        
    # 添加评价统计信息
    elapsed_time = time.time() - start_time
    telemetry_info = (
        f"\n## 评价统计\n\n"
        f"- **评价模型**: {model_name}\n"
        f"- **评价时间**: {elapsed_time:.2f} 秒\n"
        f"- **消耗Token**: {total_tokens}\n"
        f"- **评价成本**: ${total_cost:.4f}\n"
    )
    
    report += telemetry_info
    
    # 保存报告
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存至 {args.output}")
    
    # 发送邮件报告
    if args.email:
        email_list = [email.strip() for email in args.email.split(",")]
        subject = f"[CodeDog] {args.author} 的代码评价报告 ({start_date} 至 {end_date})"
        
        sent = send_report_email(
            to_emails=email_list,
            subject=subject,
            markdown_content=report,
        )
        
        if sent:
            print(f"报告已发送至 {', '.join(email_list)}")
        else:
            print("邮件发送失败，请检查邮件配置")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被中断")
        sys.exit(1)
    except Exception as e:
        print(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 