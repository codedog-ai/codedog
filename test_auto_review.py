#!/usr/bin/env python
"""
测试自动代码评审和邮件报告功能

这个文件用于测试 Git 钩子是否能正确触发代码评审并发送邮件报告。
"""

def hello_world():
    """打印 Hello, World! 消息"""
    print("Hello, World!")
    return "Hello, World!"

def calculate_sum(a, b):
    """计算两个数的和

    Args:
        a: 第一个数
        b: 第二个数

    Returns:
        两个数的和
    """
    # 添加类型检查
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("参数必须是数字类型")
    return a + b

if __name__ == "__main__":
    hello_world()
    result = calculate_sum(5, 10)
    print(f"5 + 10 = {result}")
