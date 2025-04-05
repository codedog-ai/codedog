from modelcontextprotocol.github import GithubMCP
import asyncio
from datetime import datetime

async def fetch_code_samples():
    # Initialize GitHub MCP client
    github_mcp = GithubMCP()
    
    # Search criteria for repositories
    search_query = "language:python stars:>1000 sort:stars"
    
    try:
        with open('sample_code.log', 'w', encoding='utf-8') as log_file:
            log_file.write(f"Code Samples Fetched via MCP on {datetime.now()}\n")
            log_file.write("=" * 80 + "\n\n")
            
            # Get repository suggestions
            repos = await github_mcp.suggest_repositories(search_query, max_results=5)
            
            for repo in repos:
                log_file.write(f"Repository: {repo.full_name}\n")
                log_file.write("-" * 40 + "\n")
                
                # Get file suggestions from the repository
                files = await github_mcp.suggest_files(repo.full_name, max_results=2)
                
                for file in files:
                    if file.name.endswith('.py'):
                        content = await github_mcp.get_file_content(repo.full_name, file.path)
                        
                        log_file.write(f"\nFile: {file.name}\n")
                        log_file.write("```python\n")
                        log_file.write(content)
                        log_file.write("\n```\n")
                        log_file.write("-" * 40 + "\n")
                
                log_file.write("\n" + "=" * 80 + "\n\n")
                
        print("Code samples have been successfully fetched and saved to sample_code.log")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(fetch_code_samples()) 