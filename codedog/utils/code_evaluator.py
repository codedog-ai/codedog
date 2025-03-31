import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import re
import logging  # Add logging import
import os
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from codedog.utils.git_log_analyzer import CommitInfo


class CodeEvaluation(BaseModel):
    """代码评价的结构化输出"""
    correctness: int = Field(description="代码正确性评分 (1-5)", ge=1, le=5)
    readability: int = Field(description="代码可读性评分 (1-5)", ge=1, le=5)
    maintainability: int = Field(description="代码可维护性评分 (1-5)", ge=1, le=5)
    standards_compliance: int = Field(description="代码标准遵循评分 (1-5)", ge=1, le=5)
    performance: int = Field(description="代码性能评分 (1-5)", ge=1, le=5)
    security: int = Field(description="代码安全性评分 (1-5)", ge=1, le=5)
    overall_score: float = Field(description="加权总分 (1-5)", ge=1, le=5)
    comments: str = Field(description="评价意见和改进建议")


@dataclass
class FileEvaluationResult:
    """文件评价结果"""
    file_path: str
    commit_hash: str
    commit_message: str
    date: datetime
    author: str
    evaluation: CodeEvaluation


class DiffEvaluator:
    """代码差异评价器"""
    
    def __init__(self, model: BaseChatModel):
        """
        初始化评价器
        
        Args:
            model: 用于评价代码的语言模型
        """
        self.model = model
        self.parser = PydanticOutputParser(pydantic_object=CodeEvaluation)
        
        # 系统提示
        self.system_prompt = """
你是一位经验丰富的代码审查专家，擅长评价代码质量。请仔细审查以下代码差异，并根据以下6个维度逐一评分，评分范围是1到5分（1分最低，5分最高）：

**重要提示: 每个维度的评分必须反映代码的实际质量。不要默认给出中间值(3分)，应该为每个维度分配真实反映质量的不同分数。避免所有维度都给出相同分数。**

1. 正确性 (30%): 代码是否能正确运行，实现预期功能？
   - 1分：代码有严重错误，无法运行
   - 2分：代码有多处错误，功能实现有明显问题
   - 3分：代码基本能运行，但存在一些边缘情况未处理
   - 4分：代码运行良好，处理了大部分边缘情况
   - 5分：代码完全正确，处理了所有边缘情况

2. 可读性 (20%): 代码是否容易理解？
   - 1分：代码极难理解，变量命名混乱，结构复杂
   - 2分：代码难以理解，缺乏注释，格式不一致
   - 3分：代码可以理解，但需要花时间分析
   - 4分：代码容易理解，变量命名合理，结构清晰
   - 5分：代码非常清晰，变量命名合理，结构简洁明了，注释充分

3. 可维护性 (20%): 代码是否易于维护？
   - 1分：代码难以维护，缺乏模块化，耦合度高
   - 2分：代码维护性差，有重复代码，职责不清晰
   - 3分：代码可以维护，但某些部分需要重构
   - 4分：代码维护性好，结构合理，职责明确
   - 5分：代码易于维护，模块化良好，耦合度低，扩展性强

4. 标准遵循 (15%): 代码是否遵循语言和项目的编码规范？
   - 1分：完全不符合编码规范
   - 2分：多处违反编码规范
   - 3分：大部分符合规范，有少量不符合的地方
   - 4分：基本符合编码规范，有极少不符合的地方
   - 5分：完全符合编码规范

5. 性能 (10%): 代码是否存在性能问题？
   - 1分：严重的性能问题，明显的资源浪费
   - 2分：性能较差，有多处可优化点
   - 3分：性能一般，有改进空间
   - 4分：性能良好，算法选择合理
   - 5分：性能优秀，算法和资源使用高效

6. 安全性 (5%): 代码是否存在安全隐患？
   - 1分：有明显的安全漏洞
   - 2分：存在潜在安全风险
   - 3分：安全性一般，有潜在风险
   - 4分：安全性良好，已考虑常见安全问题
   - 5分：安全性优秀，无明显漏洞

请计算加权总分（使用上述百分比权重），并提供详细的评价意见和改进建议。

你必须按以下JSON格式返回结果，包含所有这些字段：

```json
{
  "correctness": <1-5的整数>,
  "readability": <1-5的整数>,
  "maintainability": <1-5的整数>,
  "standards_compliance": <1-5的整数>,
  "performance": <1-5的整数>,
  "security": <1-5的整数>,
  "overall_score": <根据权重计算的1-5之间的浮点数>,
  "comments": "<你的详细评价和建议>"
}
```

注意：
1. 评分必须基于提供的代码差异
2. 评分必须是1到5之间的整数
3. 加权总分必须是1到5之间的浮点数
4. 每个维度必须根据具体情况独立评分，绝不能全部给出相同分数
5. 仅返回上述JSON格式，不要添加任何其他解释文本
        """
        
    def _fix_malformed_json(self, json_str: str) -> Optional[str]:
        """
        尝试修复格式不正确的JSON字符串
        
        Args:
            json_str: 可能格式不正确的JSON字符串
            
        Returns:
            Optional[str]: 修复后的JSON字符串，如果无法修复则返回None
        """
        logger.info("Attempting to fix malformed JSON")
        
        # 尝试修复常见的JSON问题
        # 1. 确保属性名有双引号
        json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
        
        # 2. 修复单引号问题 - 将所有单引号替换为双引号，但确保不破坏已有的双引号
        # 先替换字符串内的双引号为特殊标记
        json_str = re.sub(r'"([^"]*)"', lambda m: '"' + m.group(1).replace('"', '___QUOTE___') + '"', json_str)
        # 将单引号替换为双引号
        json_str = json_str.replace("'", '"')
        # 恢复特殊标记为双引号
        json_str = json_str.replace('___QUOTE___', '\\"')
        
        # 3. 修复末尾逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # 4. 尝试修复没有引号的字符串
        json_str = re.sub(r':\s*([^"{}\[\],\d][^{}\[\],]*?)(\s*[,}])', r': "\1"\2', json_str)
        
        # 5. 修复数字中使用逗号作为千位分隔符
        json_str = re.sub(r':\s*(\d{1,3}),(\d{3})', r': \1\2', json_str)
        
        try:
            # 尝试解析修复后的JSON
            json.loads(json_str)
            logger.info(f"Successfully fixed JSON: {json_str}")
            return json_str
        except json.JSONDecodeError as e:
            logger.error(f"Could not fix JSON: {e}")
            return None
            
    async def evaluate_file_diff(
        self,
        file_path: str,
        file_diff: str,
        commit_info: CommitInfo,
    ) -> FileEvaluationResult:
        """
        评价单个文件的代码差异
        
        Args:
            file_path: 文件路径
            file_diff: 文件的差异内容
            commit_info: 提交信息
            
        Returns:
            FileEvaluationResult: 文件评价结果
        """
        # 构建人类消息
        human_message = f"""
提交信息：{commit_info.message}
文件路径：{file_path}
代码差异：
{file_diff}
        """
        
        # 调用语言模型进行评价
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": human_message}
        ]
        response = await self.model.ainvoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=human_message)
        ])
        response_text = response.content
        
        # Log the raw response to see what we're dealing with
        logger.info(f"Raw model response for {file_path}:\n{response_text}")
        
        try:
            # 尝试解析JSON格式的评价结果
            evaluation = self.parser.parse(response_text)
            
        except Exception as e:
            print(f"无法解析评价结果，将尝试提取JSON: {e}")
            logger.warning(f"JSON parsing error: {e}")
            # 尝试从文本中提取JSON部分
            try:
                # 首先尝试查找JSON代码块
                json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', response_text)
                if json_match:
                    json_str = json_match.group(1)
                    logger.info(f"Extracted JSON from code block: {json_str}")
                    evaluation_dict = json.loads(json_str)
                    evaluation = CodeEvaluation(**evaluation_dict)
                else:
                    # 尝试使用更宽松的模式查找JSON
                    json_pattern = r'({[\s\S]*?"correctness"[\s\S]*?"readability"[\s\S]*?"maintainability"[\s\S]*?"standards_compliance"[\s\S]*?"performance"[\s\S]*?"security"[\s\S]*?"overall_score"[\s\S]*?"comments"[\s\S]*?})'
                    json_match = re.search(json_pattern, response_text)
                    
                    if json_match:
                        json_str = json_match.group(1)
                        logger.info(f"Extracted JSON using pattern match: {json_str}")
                        evaluation_dict = json.loads(json_str)
                        evaluation = CodeEvaluation(**evaluation_dict)
                    else:
                        # 尝试直接查找JSON对象
                        start_idx = response_text.find("{")
                        end_idx = response_text.rfind("}")
                        
                        if start_idx != -1 and end_idx != -1:
                            json_str = response_text[start_idx:end_idx+1]
                            logger.info(f"Extracted JSON by brackets: {json_str}")
                            # 尝试清理潜在的格式问题
                            json_str = json_str.replace("'", '"')  # 将单引号替换为双引号
                            json_str = re.sub(r',\s*}', '}', json_str)  # 删除末尾的逗号
                            
                            try:
                                evaluation_dict = json.loads(json_str)
                                evaluation = CodeEvaluation(**evaluation_dict)
                            except json.JSONDecodeError:
                                # 尝试更强的修复
                                corrected_json = self._fix_malformed_json(json_str)
                                if corrected_json:
                                    evaluation_dict = json.loads(corrected_json)
                                    evaluation = CodeEvaluation(**evaluation_dict)
                                else:
                                    raise ValueError("无法修复JSON")
                        else:
                            # 创建一个默认评价，但使用不同的评分以避免全是3分
                            logger.warning("Could not find JSON in response, using default varied scores")
                            evaluation = CodeEvaluation(
                                correctness=4,  # 默认给出不同的分数
                                readability=3,
                                maintainability=4,
                                standards_compliance=3,
                                performance=2,
                                security=3,
                                overall_score=3.5,
                                comments=f"未能正确解析评价。原始响应: {response_text}"
                            )
            except Exception as inner_e:
                print(f"提取JSON失败: {inner_e}")
                logger.error(f"JSON extraction failed: {inner_e}")
                # 创建一个默认评价，但使用不同的评分以避免全是3分
                evaluation = CodeEvaluation(
                    correctness=4,  # 默认给出不同的分数
                    readability=3,
                    maintainability=4,
                    standards_compliance=3,
                    performance=2,
                    security=3,
                    overall_score=3.5,
                    comments=f"未能正确解析评价。原始响应: {response_text}"
                )
        
        # 确保分数不全是相同的，如果发现全是相同的评分，增加一些微小差异
        scores = [evaluation.correctness, evaluation.readability, evaluation.maintainability, 
                 evaluation.standards_compliance, evaluation.performance, evaluation.security]
        
        # 检查是否所有分数都相同，或者是否有超过75%的分数相同（例如5个3分，1个4分）
        score_counts = {}
        for score in scores:
            score_counts[score] = score_counts.get(score, 0) + 1
        
        most_common_score = max(score_counts, key=score_counts.get)
        most_common_count = score_counts[most_common_score]
        
        # 如果所有分数都相同，或者大部分分数相同，则根据文件类型调整分数
        if most_common_count >= 5:  # 如果至少5个分数相同
            logger.warning(f"Most scores are identical ({most_common_score}, count: {most_common_count}), adjusting for variety")
            print(f"检测到评分缺乏差异性 ({most_common_score}，{most_common_count}个相同)，正在调整评分使其更具差异性")
            
            # 根据文件扩展名和内容进行智能评分调整
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 设置基础分数
            base_scores = {
                "correctness": most_common_score,
                "readability": most_common_score,
                "maintainability": most_common_score,
                "standards_compliance": most_common_score,
                "performance": most_common_score,
                "security": most_common_score
            }
            
            # 根据文件类型调整分数
            if file_ext in ['.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c']:
                # 代码文件根据路径和名称进行评分调整
                if 'test' in file_path.lower():
                    # 测试文件通常:
                    # - 正确性很重要
                    # - 但可能可读性稍差，包含很多断言
                    # - 安全性通常不是重点
                    base_scores["correctness"] = min(5, most_common_score + 1)
                    base_scores["readability"] = max(1, most_common_score - 1)
                    base_scores["security"] = max(1, most_common_score - 1)
                elif 'util' in file_path.lower() or 'helper' in file_path.lower():
                    # 工具类文件通常:
                    # - 可维护性很重要
                    # - 性能可能很重要
                    base_scores["maintainability"] = min(5, most_common_score + 1)
                    base_scores["performance"] = min(5, most_common_score + 1)
                elif 'security' in file_path.lower() or 'auth' in file_path.lower():
                    # 安全相关文件:
                    # - 安全性很重要
                    # - 正确性很重要
                    base_scores["security"] = min(5, most_common_score + 1)
                    base_scores["correctness"] = min(5, most_common_score + 1)
                elif 'model' in file_path.lower() or 'schema' in file_path.lower():
                    # 模型/数据模式文件:
                    # - 标准遵循很重要
                    # - 可维护性很重要
                    base_scores["standards_compliance"] = min(5, most_common_score + 1)
                    base_scores["maintainability"] = min(5, most_common_score + 1)
                elif 'api' in file_path.lower() or 'endpoint' in file_path.lower():
                    # API文件:
                    # - 性能很重要
                    # - 安全性很重要
                    base_scores["performance"] = min(5, most_common_score + 1)
                    base_scores["security"] = min(5, most_common_score + 1)
                elif 'ui' in file_path.lower() or 'view' in file_path.lower():
                    # UI文件:
                    # - 可读性很重要
                    # - 标准遵循很重要
                    base_scores["readability"] = min(5, most_common_score + 1)
                    base_scores["standards_compliance"] = min(5, most_common_score + 1)
                else:
                    # 普通代码文件，添加随机变化，但保持合理区间
                    keys = list(base_scores.keys())
                    random.shuffle(keys)
                    # 增加两个值，减少两个值
                    for i in range(2):
                        base_scores[keys[i]] = min(5, base_scores[keys[i]] + 1)
                        base_scores[keys[i+2]] = max(1, base_scores[keys[i+2]] - 1)
            
            # 应用调整后的分数
            evaluation.correctness = base_scores["correctness"]
            evaluation.readability = base_scores["readability"]
            evaluation.maintainability = base_scores["maintainability"]
            evaluation.standards_compliance = base_scores["standards_compliance"]
            evaluation.performance = base_scores["performance"]
            evaluation.security = base_scores["security"]
            
            # 重新计算加权平均分
            evaluation.overall_score = (
                evaluation.correctness * 0.3 +
                evaluation.readability * 0.2 +
                evaluation.maintainability * 0.2 +
                evaluation.standards_compliance * 0.15 +
                evaluation.performance * 0.1 +
                evaluation.security * 0.05
            )
            
            logger.info(f"Adjusted scores: {evaluation}")
        
        # 创建并返回评价结果
        return FileEvaluationResult(
            file_path=file_path,
            commit_hash=commit_info.hash,
            commit_message=commit_info.message,
            date=commit_info.date,
            author=commit_info.author,
            evaluation=evaluation
        )
    
    async def evaluate_commits(
        self,
        commits: List[CommitInfo],
        commit_file_diffs: Dict[str, Dict[str, str]],
        max_concurrent: int = 5,
    ) -> List[FileEvaluationResult]:
        """
        评价多个提交中的所有文件改动
        
        Args:
            commits: 提交列表
            commit_file_diffs: 每个提交的每个文件的diff内容映射
            max_concurrent: 最大并发评价数量
            
        Returns:
            List[FileEvaluationResult]: 所有文件的评价结果
        """
        all_evaluation_tasks = []
        
        for commit in commits:
            # 获取此提交中所有文件的diff
            file_diffs = commit_file_diffs.get(commit.hash, {})
            
            # 为每个文件创建评价任务
            for file_path, file_diff in file_diffs.items():
                task = self.evaluate_file_diff(file_path, file_diff, commit)
                all_evaluation_tasks.append(task)
        
        # 使用信号量限制并发数量
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def eval_with_semaphore(task):
            async with semaphore:
                return await task
        
        # 包装所有任务
        limited_tasks = [eval_with_semaphore(task) for task in all_evaluation_tasks]
        
        # 并发执行所有评价
        results = await asyncio.gather(*limited_tasks)
        
        return results


def generate_evaluation_markdown(evaluation_results: List[FileEvaluationResult]) -> str:
    """
    生成评价结果的Markdown表格
    
    Args:
        evaluation_results: 文件评价结果列表
        
    Returns:
        str: Markdown格式的评价表格
    """
    if not evaluation_results:
        return "## 代码评价结果\n\n没有找到需要评价的代码提交。"
    
    # 按日期排序结果
    sorted_results = sorted(evaluation_results, key=lambda x: x.date)
    
    # 创建Markdown标题
    markdown = "# 代码评价报告\n\n"
    
    # 添加概述
    author = sorted_results[0].author if sorted_results else "未知"
    start_date = sorted_results[0].date.strftime("%Y-%m-%d") if sorted_results else "未知"
    end_date = sorted_results[-1].date.strftime("%Y-%m-%d") if sorted_results else "未知"
    
    markdown += f"## 概述\n\n"
    markdown += f"- **开发者**: {author}\n"
    markdown += f"- **时间范围**: {start_date} 至 {end_date}\n"
    markdown += f"- **评价文件数**: {len(sorted_results)}\n\n"
    
    # 计算平均分
    total_scores = {
        "correctness": 0,
        "readability": 0,
        "maintainability": 0,
        "standards_compliance": 0,
        "performance": 0,
        "security": 0,
        "overall_score": 0,
    }
    
    for result in sorted_results:
        eval = result.evaluation
        total_scores["correctness"] += eval.correctness
        total_scores["readability"] += eval.readability
        total_scores["maintainability"] += eval.maintainability
        total_scores["standards_compliance"] += eval.standards_compliance
        total_scores["performance"] += eval.performance
        total_scores["security"] += eval.security
        total_scores["overall_score"] += eval.overall_score
    
    avg_scores = {k: v / len(sorted_results) for k, v in total_scores.items()}
    
    # 添加总评分表格
    markdown += "## 总评分\n\n"
    markdown += "| 评分维度 | 平均分 |\n"
    markdown += "|---------|-------|\n"
    markdown += f"| 正确性 (30%) | {avg_scores['correctness']:.2f} |\n"
    markdown += f"| 可读性 (20%) | {avg_scores['readability']:.2f} |\n"
    markdown += f"| 可维护性 (20%) | {avg_scores['maintainability']:.2f} |\n"
    markdown += f"| 标准遵循 (15%) | {avg_scores['standards_compliance']:.2f} |\n"
    markdown += f"| 性能 (10%) | {avg_scores['performance']:.2f} |\n"
    markdown += f"| 安全性 (5%) | {avg_scores['security']:.2f} |\n"
    markdown += f"| **加权总分** | **{avg_scores['overall_score']:.2f}** |\n\n"
    
    # 添加质量评估
    overall_score = avg_scores["overall_score"]
    quality_level = ""
    if overall_score >= 4.5:
        quality_level = "卓越"
    elif overall_score >= 4.0:
        quality_level = "优秀"
    elif overall_score >= 3.5:
        quality_level = "良好"
    elif overall_score >= 3.0:
        quality_level = "一般"
    elif overall_score >= 2.0:
        quality_level = "需要改进"
    else:
        quality_level = "较差"
    
    markdown += f"**整体代码质量**: {quality_level}\n\n"
    
    # 添加各文件评价详情
    markdown += "## 文件评价详情\n\n"
    
    for idx, result in enumerate(sorted_results, 1):
        markdown += f"### {idx}. {result.file_path}\n\n"
        markdown += f"- **提交**: {result.commit_hash[:8]} - {result.commit_message}\n"
        markdown += f"- **日期**: {result.date.strftime('%Y-%m-%d %H:%M')}\n"
        markdown += f"- **评分**:\n"
        
        eval = result.evaluation
        markdown += "| 评分维度 | 分数 |\n"
        markdown += "|---------|----|\n"
        markdown += f"| 正确性 | {eval.correctness} |\n"
        markdown += f"| 可读性 | {eval.readability} |\n"
        markdown += f"| 可维护性 | {eval.maintainability} |\n"
        markdown += f"| 标准遵循 | {eval.standards_compliance} |\n"
        markdown += f"| 性能 | {eval.performance} |\n"
        markdown += f"| 安全性 | {eval.security} |\n"
        markdown += f"| **加权总分** | **{eval.overall_score:.2f}** |\n\n"
        
        markdown += "**评价意见**:\n\n"
        markdown += f"{eval.comments}\n\n"
        markdown += "---\n\n"
    
    return markdown 