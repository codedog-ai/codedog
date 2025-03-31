import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Tuple


@dataclass
class CommitInfo:
    """存储提交信息的数据类"""
    hash: str
    author: str
    date: datetime
    message: str
    files: List[str]
    diff: str


def get_commits_by_author_and_timeframe(
    author: str,
    start_date: str,
    end_date: str,
    repo_path: Optional[str] = None,
) -> List[CommitInfo]:
    """
    获取指定作者在指定时间段内的所有提交
    
    Args:
        author: 作者名或邮箱（部分匹配）
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        repo_path: Git仓库路径，默认为当前目录
        
    Returns:
        List[CommitInfo]: 提交信息列表
    """
    cwd = repo_path or os.getcwd()
    
    try:
        # 查询在指定时间段内指定作者的提交
        cmd = [
            "git", "log",
            f"--author={author}",
            f"--after={start_date}",
            f"--before={end_date}",
            "--format=%H|%an|%aI|%s"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
        
        commits = []
        
        # 解析结果
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
                
            hash_val, author_name, date_str, message = line.split("|", 3)
            
            # 获取提交修改的文件列表
            files_cmd = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", hash_val]
            files_result = subprocess.run(
                files_cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                check=True,
            )
            files = [f for f in files_result.stdout.strip().split("\n") if f]
            
            # 获取完整diff
            diff_cmd = ["git", "show", hash_val]
            diff_result = subprocess.run(
                diff_cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                check=True,
            )
            diff = diff_result.stdout
            
            commit_info = CommitInfo(
                hash=hash_val,
                author=author_name,
                date=datetime.fromisoformat(date_str),
                message=message,
                files=files,
                diff=diff,
            )
            
            commits.append(commit_info)
            
        return commits
        
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving commits: {e}")
        print(f"Error output: {e.stderr}")
        return []


def filter_code_files(
    commits: List[CommitInfo],
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
) -> List[CommitInfo]:
    """
    过滤提交，只保留修改了代码文件的提交
    
    Args:
        commits: 提交信息列表
        include_extensions: 要包含的文件扩展名列表（例如['.py', '.js']）
        exclude_extensions: 要排除的文件扩展名列表
        
    Returns:
        List[CommitInfo]: 过滤后的提交信息列表
    """
    if not include_extensions and not exclude_extensions:
        return commits
    
    filtered_commits = []
    
    for commit in commits:
        # 如果没有文件，跳过
        if not commit.files:
            continue
            
        # 过滤文件
        filtered_files = []
        for file in commit.files:
            _, ext = os.path.splitext(file)
            
            if include_extensions and ext not in include_extensions:
                continue
                
            if exclude_extensions and ext in exclude_extensions:
                continue
                
            filtered_files.append(file)
        
        # 如果过滤后还有文件，保留这个提交
        if filtered_files:
            # 创建一个新的CommitInfo对象，但只包含过滤后的文件
            filtered_commit = CommitInfo(
                hash=commit.hash,
                author=commit.author,
                date=commit.date,
                message=commit.message,
                files=filtered_files,
                diff=commit.diff,  # 暂时保留完整diff，后续可能需要更精确地过滤
            )
            filtered_commits.append(filtered_commit)
    
    return filtered_commits


def extract_file_diffs(commit: CommitInfo) -> Dict[str, str]:
    """
    从提交的diff中提取每个文件的差异内容
    
    Args:
        commit: 提交信息
        
    Returns:
        Dict[str, str]: 文件路径到diff内容的映射
    """
    file_diffs = {}
    
    # git show输出的格式是复杂的，需要解析
    diff_lines = commit.diff.split("\n")
    
    current_file = None
    current_diff = []
    
    for line in diff_lines:
        # 检测新文件的开始
        if line.startswith("diff --git"):
            # 保存上一个文件的diff
            if current_file and current_diff:
                file_diffs[current_file] = "\n".join(current_diff)
            
            # 重置状态
            current_file = None
            current_diff = []
            
        # 找到文件名
        elif line.startswith("--- a/") or line.startswith("+++ b/"):
            file_path = line[6:]  # 移除前缀 "--- a/" 或 "+++ b/"
            if file_path in commit.files:
                current_file = file_path
                
        # 收集diff内容
        if current_file:
            current_diff.append(line)
    
    # 保存最后一个文件的diff
    if current_file and current_diff:
        file_diffs[current_file] = "\n".join(current_diff)
    
    return file_diffs


def get_file_diffs_by_timeframe(
    author: str,
    start_date: str,
    end_date: str,
    repo_path: Optional[str] = None,
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
) -> Tuple[List[CommitInfo], Dict[str, Dict[str, str]]]:
    """
    获取指定作者在特定时间段内修改的所有文件的差异内容
    
    Args:
        author: 作者名或邮箱（部分匹配）
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        repo_path: Git仓库路径，默认为当前目录
        include_extensions: 要包含的文件扩展名列表（例如['.py', '.js']）
        exclude_extensions: 要排除的文件扩展名列表
        
    Returns:
        Tuple[List[CommitInfo], Dict[str, Dict[str, str]]]: 
            1. 过滤后的提交信息列表
            2. 每个提交的每个文件的diff内容映射 {commit_hash: {file_path: diff_content}}
    """
    # 获取提交
    commits = get_commits_by_author_and_timeframe(
        author, start_date, end_date, repo_path
    )
    
    if not commits:
        return [], {}
    
    # 过滤提交
    filtered_commits = filter_code_files(
        commits, include_extensions, exclude_extensions
    )
    
    if not filtered_commits:
        return [], {}
    
    # 提取每个提交中每个文件的diff
    commit_file_diffs = {}
    
    for commit in filtered_commits:
        file_diffs = extract_file_diffs(commit)
        commit_file_diffs[commit.hash] = file_diffs
    
    return filtered_commits, commit_file_diffs 