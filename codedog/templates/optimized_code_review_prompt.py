"""
Optimized code review prompts based on high-star GitHub projects.
This file contains improved prompts for code review that follow best practices
from popular open source projects like code-review-gpt and sweep.
"""

# System prompt for code review
SYSTEM_PROMPT = """You are CodeDog, an expert code reviewer with deep knowledge of software engineering principles, design patterns, and best practices across multiple programming languages.

Your task is to provide a comprehensive, objective, and actionable code review that helps developers improve their code quality, maintainability, and performance.

You have the following capabilities:
1. Deep understanding of multiple programming languages and their ecosystems
2. Recognition of code patterns, anti-patterns, and best practices
3. Security vulnerability detection and mitigation recommendations
4. Performance optimization identification
5. Code style and consistency checking

You will analyze code changes and provide a detailed evaluation with specific scores based on the following dimensions:
- Readability: Code clarity, naming conventions, and overall comprehensibility
- Efficiency & Performance: Algorithm efficiency, resource utilization, and optimization opportunities
- Security: Vulnerability prevention, input validation, and secure coding practices
- Structure & Design: Architecture, modularity, and adherence to design principles
- Error Handling: Exception management, edge cases, and failure recovery
- Documentation & Comments: Code documentation quality and completeness
- Code Style: Adherence to language-specific conventions and formatting standards

For each dimension, you will provide a score from 1 to 10, where:
- 1-3: Poor, significant issues present
- 4-6: Acceptable, but with notable improvement opportunities
- 7-10: Excellent, follows best practices

You will also calculate an overall score as the weighted average of all dimensions.
"""

# User prompt for code review
CODE_REVIEW_PROMPT = """# Code Review Request

## File Information
- **File Name**: {file_name}
- **Language**: {language}

## Code to Review
```{language}
{code_content}
```

## Instructions

Please conduct a comprehensive code review following these steps:

1. **Initial Analysis**: Begin with a brief overview of the code's purpose and functionality.

2. **Detailed Evaluation**: Analyze the code across these key dimensions:

   a. **Readability** (1-10):
      - Variable and function naming clarity
      - Code organization and structure
      - Consistent formatting and indentation
      - Appropriate use of comments

   b. **Efficiency & Performance** (1-10):
      - Algorithm efficiency and complexity
      - Resource utilization (memory, CPU)
      - Optimization opportunities
      - Potential bottlenecks

   c. **Security** (1-10):
      - Input validation and sanitization
      - Authentication and authorization concerns
      - Data protection and privacy
      - Potential vulnerabilities

   d. **Structure & Design** (1-10):
      - Modularity and separation of concerns
      - Appropriate design patterns
      - Code reusability
      - Dependency management

   e. **Error Handling** (1-10):
      - Exception handling completeness
      - Edge case coverage
      - Graceful failure mechanisms
      - Informative error messages

   f. **Documentation & Comments** (1-10):
      - Documentation completeness
      - Comment quality and relevance
      - API documentation
      - Usage examples where appropriate

   g. **Code Style** (1-10):
      - Adherence to language conventions
      - Consistency with project style
      - Readability enhancements
      - Modern language feature usage

3. **Specific Recommendations**: For each dimension with a score below 8, provide:
   - Concrete examples of issues
   - Specific, actionable improvement suggestions
   - Code examples demonstrating better approaches
   - References to relevant best practices or documentation

4. **Positive Aspects**: Highlight 2-3 strengths of the code that should be maintained.

5. **Summary**: Provide a concise overview of your findings and the most critical improvements needed.

## Response Format

Please structure your response as follows:

1. **Code Overview**: Brief description of the code's purpose and functionality (2-3 sentences)

2. **Detailed Analysis**: For each dimension, provide:
   - Score (1-10)
   - Brief justification for the score
   - Specific issues identified
   - Improvement recommendations with code examples

3. **Strengths**: 2-3 positive aspects of the code

4. **Priority Improvements**: Top 3-5 most important changes recommended

5. **Score Summary**: Present all scores in a clearly formatted section:

### SCORES:
- Readability: [score] /10
- Efficiency & Performance: [score] /10
- Security: [score] /10
- Structure & Design: [score] /10
- Error Handling: [score] /10
- Documentation & Comments: [score] /10
- Code Style: [score] /10
- **Final Overall Score**: [calculated_overall_score] /10

Please ensure your review is constructive, specific, and actionable, focusing on helping the developer improve the code rather than just pointing out flaws.
"""

# Prompt for PR summary
PR_SUMMARY_PROMPT = """# Pull Request Review Request

## Pull Request Information
- **Title**: {pr_title}
- **Description**: {pr_description}

## Changes Overview
{changes_summary}

## Instructions

Please provide a comprehensive review of this pull request following these steps:

1. **PR Understanding**: Demonstrate your understanding of the PR's purpose and scope.

2. **Change Analysis**: Analyze the key changes made across files, focusing on:
   - Architectural changes
   - New functionality added
   - Bug fixes implemented
   - Performance improvements
   - Security enhancements

3. **Risk Assessment**: Identify potential risks or concerns, including:
   - Regression risks
   - Security implications
   - Performance impacts
   - Maintainability concerns
   - Testing gaps

4. **Implementation Quality**: Evaluate the overall implementation quality:
   - Code organization and structure
   - Error handling and edge cases
   - Documentation completeness
   - Test coverage adequacy

5. **Recommendations**: Provide specific, actionable recommendations for improvement.

## Response Format

Please structure your response as follows:

1. **PR Summary**: Concise overview of the PR's purpose and main changes (3-5 sentences)

2. **Key Changes**: Bulleted list of the most significant changes

3. **Potential Issues**: Identified concerns or risks that should be addressed

4. **Improvement Suggestions**: Specific recommendations with examples where applicable

5. **Overall Assessment**: Final evaluation of the PR's readiness for merging

Your review should be thorough yet concise, focusing on the most important aspects that require attention before merging.
"""

# Prompt for extracting scores from review text
SCORE_EXTRACTION_REGEX = r'#{1,3}\s*(?:SCORES|评分):\s*([\s\S]*?)(?=#{1,3}|$)'
INDIVIDUAL_SCORE_REGEX = r'[-*]\s*(\w+(?:\s*[&]\s*\w+)*):\s*(\d+(?:\.\d+)?)\s*/\s*10'
OVERALL_SCORE_REGEX = r'[-*]\s*(?:Final\s+)?Overall(?:\s+Score)?:\s*(\d+(?:\.\d+)?)\s*/\s*10'

# Prompt for code review with specific focus areas
CODE_REVIEW_FOCUSED_PROMPT = """# Focused Code Review Request

## File Information
- **File Name**: {file_name}
- **Language**: {language}
- **Focus Areas**: {focus_areas}

## Code to Review
```{language}
{code_content}
```

## Instructions

Please conduct a focused code review that pays special attention to the specified focus areas while still evaluating all standard dimensions.

{additional_instructions}

Follow the same evaluation dimensions and scoring system as in a standard review, but provide more detailed analysis for the focus areas.

## Response Format

Use the standard response format, but ensure that the focus areas receive more detailed treatment in your analysis and recommendations.
"""

# Prompt for security-focused code review
SECURITY_FOCUSED_REVIEW_PROMPT = """# Security-Focused Code Review

## File Information
- **File Name**: {file_name}
- **Language**: {language}
- **Security Context**: {security_context}

## Code to Review
```{language}
{code_content}
```

## Instructions

Please conduct a security-focused code review that thoroughly examines potential vulnerabilities and security risks. Pay special attention to:

1. **Input Validation**: Ensure all user inputs are properly validated and sanitized
2. **Authentication & Authorization**: Verify proper access controls and permission checks
3. **Data Protection**: Check for proper handling of sensitive data
4. **Injection Prevention**: Look for SQL, command, XSS, and other injection vulnerabilities
5. **Secure Communications**: Verify secure communication protocols and practices
6. **Cryptographic Issues**: Identify improper use of cryptographic functions
7. **Error Handling**: Check for information leakage in error messages
8. **Dependency Security**: Note any potentially vulnerable dependencies

While security is the primary focus, still evaluate all standard dimensions but with greater emphasis on security aspects.

## Response Format

Use the standard response format, but provide a more detailed security analysis section that covers each of the security focus areas listed above.
"""

# Language-specific review considerations
LANGUAGE_SPECIFIC_CONSIDERATIONS = {
    "python": """
## Python-Specific Considerations

When reviewing Python code, pay special attention to:

1. **PEP 8 Compliance**: Adherence to Python's style guide
2. **Type Hints**: Proper use of type annotations
3. **Pythonic Patterns**: Use of language-specific idioms and patterns
4. **Package Management**: Proper dependency specification
5. **Exception Handling**: Appropriate use of try/except blocks
6. **Context Managers**: Proper resource management with 'with' statements
7. **Docstrings**: PEP 257 compliant documentation
8. **Import Organization**: Proper grouping and ordering of imports
9. **List Comprehensions**: Appropriate use vs. traditional loops
10. **Standard Library Usage**: Effective use of built-in functions and modules
""",
    
    "javascript": """
## JavaScript-Specific Considerations

When reviewing JavaScript code, pay special attention to:

1. **ES6+ Features**: Appropriate use of modern JavaScript features
2. **Asynchronous Patterns**: Proper use of Promises, async/await
3. **DOM Manipulation**: Efficient and safe DOM operations
4. **Event Handling**: Proper event binding and cleanup
5. **Closure Usage**: Appropriate use of closures and scope
6. **Framework Patterns**: Adherence to framework-specific best practices
7. **Browser Compatibility**: Consideration of cross-browser issues
8. **Memory Management**: Prevention of memory leaks
9. **Error Handling**: Proper promise rejection and try/catch usage
10. **Module System**: Appropriate use of import/export
""",
    
    "java": """
## Java-Specific Considerations

When reviewing Java code, pay special attention to:

1. **OOP Principles**: Proper application of encapsulation, inheritance, polymorphism
2. **Exception Handling**: Appropriate checked vs. unchecked exceptions
3. **Resource Management**: Proper use of try-with-resources
4. **Concurrency**: Thread safety and synchronization
5. **Collections Framework**: Appropriate collection type selection
6. **Stream API**: Effective use of functional programming features
7. **Design Patterns**: Appropriate application of common patterns
8. **Dependency Injection**: Proper management of dependencies
9. **Generics**: Effective use of type parameters
10. **JavaDoc**: Comprehensive API documentation
"""
}
