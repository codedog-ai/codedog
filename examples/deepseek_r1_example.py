import asyncio
import time
from os import environ as env
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from github import Github
from langchain_core.callbacks import get_openai_callback

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.retrievers import GithubRetriever
from codedog.utils.langchain_utils import load_model_by_name

# Load your GitHub token and create a client
github_token = env.get("GITHUB_TOKEN", "")
gh = Github(github_token)

# Initialize the GitHub retriever with your repository and PR number
# Replace these values with your own repository and PR number
repo_name = "your-username/your-repo"
pr_number = 1
retriever = GithubRetriever(gh, repo_name, pr_number)

# Load the DeepSeek R1 model
# Make sure you have set DEEPSEEK_API_KEY and DEEPSEEK_MODEL="deepseek-r1" in your .env file
deepseek_model = load_model_by_name("deepseek")  # Will load R1 model if DEEPSEEK_MODEL is set to "deepseek-r1"

# Create PR summary and code review chains using DeepSeek R1 model
summary_chain = PRSummaryChain.from_llm(
    code_summary_llm=deepseek_model,
    pr_summary_llm=deepseek_model,  # Using same model for both code summaries and PR summary
    verbose=True
)

review_chain = CodeReviewChain.from_llm(
    llm=deepseek_model, 
    verbose=True
)

async def pr_summary():
    """Generate PR summary using DeepSeek R1 model"""
    result = await summary_chain.ainvoke(
        {"pull_request": retriever.pull_request}, include_run_info=True
    )
    return result

async def code_review():
    """Generate code review using DeepSeek R1 model"""
    result = await review_chain.ainvoke(
        {"pull_request": retriever.pull_request}, include_run_info=True
    )
    return result

def generate_report():
    """Generate a complete PR report with both summary and code review"""
    start_time = time.time()
    
    # Run the summary and review processes
    summary_result = asyncio.run(pr_summary())
    print(f"Summary generated successfully")
    
    review_result = asyncio.run(code_review())
    print(f"Code review generated successfully")
    
    # Create the reporter and generate the report
    reporter = PullRequestReporter(
        pr_summary=summary_result["pr_summary"],
        code_summaries=summary_result["code_summaries"],
        pull_request=retriever.pull_request,
        code_reviews=review_result["code_reviews"],
        telemetry={
            "start_time": start_time,
            "time_usage": time.time() - start_time,
            "model": "deepseek-r1",
        },
    )
    
    return reporter.report()

def run():
    """Main function to run the example"""
    print(f"Starting PR analysis for {repo_name} PR #{pr_number} using DeepSeek R1 model")
    
    # Check if DeepSeek API key is set
    if not env.get("DEEPSEEK_API_KEY"):
        print("ERROR: DEEPSEEK_API_KEY is not set in your environment variables or .env file")
        return
    
    # Check if DeepSeek model is set to R1
    model_name = env.get("DEEPSEEK_MODEL", "deepseek-chat")
    if model_name.lower() not in ["r1", "deepseek-r1", "codedog-r1"]:
        print(f"WARNING: DEEPSEEK_MODEL is set to '{model_name}', not specifically to 'deepseek-r1'")
        print("You may want to set DEEPSEEK_MODEL='deepseek-r1' in your .env file")
    
    # Generate and print the report
    result = generate_report()
    print("\n\n========== FINAL REPORT ==========\n")
    print(result)

if __name__ == "__main__":
    run() 