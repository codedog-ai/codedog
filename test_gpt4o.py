#!/usr/bin/env python
"""
测试 GPT-4o 模型支持

这个脚本用于测试 CodeDog 对 GPT-4o 模型的支持。
它会加载 GPT-4o 模型并执行一个简单的代码评估任务。
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加当前目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from codedog.utils.langchain_utils import load_model_by_name
from codedog.utils.code_evaluator import DiffEvaluator

# 测试代码差异
TEST_DIFF = """
diff --git a/example.py b/example.py
index 1234567..abcdefg 100644
--- a/example.py
+++ b/example.py
@@ -1,5 +1,7 @@
 def calculate_sum(a, b):
-    return a + b
+    # 添加类型检查
+    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
+        raise TypeError("Arguments must be numbers")
+    return a + b
 
 def main():
     print(calculate_sum(5, 10))
"""

async def test_gpt4o():
    """测试 GPT-4o 模型"""
    print("正在加载 GPT-4o 模型...")
    
    try:
        # 尝试加载 GPT-4o 模型
        model = load_model_by_name("gpt-4o")
        print(f"成功加载模型: {model.__class__.__name__}")
        
        # 创建评估器
        evaluator = DiffEvaluator(model, tokens_per_minute=6000, max_concurrent_requests=1)
        
        # 评估代码差异
        print("正在评估代码差异...")
        result = await evaluator._evaluate_single_diff(TEST_DIFF)
        
        # 打印评估结果
        print("\n评估结果:")
        print(f"可读性: {result.get('readability', 'N/A')}")
        print(f"效率: {result.get('efficiency', 'N/A')}")
        print(f"安全性: {result.get('security', 'N/A')}")
        print(f"结构: {result.get('structure', 'N/A')}")
        print(f"错误处理: {result.get('error_handling', 'N/A')}")
        print(f"文档: {result.get('documentation', 'N/A')}")
        print(f"代码风格: {result.get('code_style', 'N/A')}")
        print(f"总分: {result.get('overall_score', 'N/A')}")
        print(f"\n评价意见: {result.get('comments', 'N/A')}")
        
        print("\nGPT-4o 模型测试成功!")
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gpt4o())
