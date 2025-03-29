import unittest
from unittest.mock import MagicMock, patch
from langchain.chains import LLMChain
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import BaseOutputParser
from codedog.chains.pr_summary.base import PRSummaryChain
from codedog.models import PullRequest, PRSummary, ChangeSummary, PRType

class TestPRSummaryChain(unittest.TestCase):
    def setUp(self):
        # Mock LLM
        self.mock_llm = MagicMock(spec=BaseLanguageModel)
        
        # Mock chains
        self.mock_code_summary_chain = MagicMock(spec=LLMChain)
        self.mock_pr_summary_chain = MagicMock(spec=LLMChain)
        
        # Mock outputs
        self.mock_code_summary_outputs = [
            {"text": "File 1 summary"}
        ]
        self.mock_code_summary_chain.apply.return_value = self.mock_code_summary_outputs
        
        self.mock_pr_summary = PRSummary(
            overview="PR overview",
            pr_type=PRType.feature,
            major_files=["src/main.py"]
        )
        
        self.mock_pr_summary_output = {
            "text": self.mock_pr_summary
        }
        self.mock_pr_summary_chain.return_value = self.mock_pr_summary_output
        
        # Create a real parser instead of a MagicMock
        class TestParser(BaseOutputParser):
            def parse(self, text):
                return PRSummary(
                    overview="Parser result",
                    pr_type=PRType.feature,
                    major_files=["src/main.py"]
                )
                
            def get_format_instructions(self):
                return "Format instructions"
                
        # Create chain with a real parser
        self.test_parser = TestParser()
        self.chain = PRSummaryChain(
            code_summary_chain=self.mock_code_summary_chain,
            pr_summary_chain=self.mock_pr_summary_chain,
            parser=self.test_parser
        )
        
        # Mock PR
        self.mock_pr = MagicMock(spec=PullRequest)
        self.mock_pr.json.return_value = "{}"
        
        # Mock processor
        patcher = patch('codedog.chains.pr_summary.base.processor')
        self.mock_processor = patcher.start()
        self.addCleanup(patcher.stop)
        
        # Setup processor returns
        self.mock_processor.get_diff_code_files.return_value = [MagicMock()]
        self.mock_processor.build_change_summaries.return_value = [
            ChangeSummary(full_name="src/main.py", summary="File 1 summary")
        ]
        self.mock_processor.gen_material_change_files.return_value = "Material: change files"
        self.mock_processor.gen_material_code_summaries.return_value = "Material: code summaries"
        self.mock_processor.gen_material_pr_metadata.return_value = "Material: PR metadata"
        
    def test_process_code_summary_inputs(self):
        result = self.chain._process_code_summary_inputs(self.mock_pr)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        
    def test_call(self):
        # Mock run manager
        mock_run_manager = MagicMock()
        mock_run_manager.get_child.return_value = MagicMock()
        
        # Test the chain
        result = self.chain._call({"pull_request": self.mock_pr}, mock_run_manager)
        
        # Verify code summary chain was called
        self.mock_code_summary_chain.apply.assert_called_once()
        
        # Verify PR summary chain was called
        self.mock_pr_summary_chain.assert_called_once()
        
        # Verify result structure
        self.assertIn("pr_summary", result)
        self.assertIn("code_summaries", result)
        self.assertEqual(len(result["code_summaries"]), 1)
        
    @patch('asyncio.run')
    @patch('codedog.chains.pr_summary.base.processor')
    async def test_async_api(self, mock_processor, mock_asyncio_run):
        # Configure mock processor behavior
        mock_processor.get_diff_code_files.return_value = [MagicMock()]
        mock_processor.build_change_summaries.return_value = [
            ChangeSummary(full_name="src/main.py", summary="File 1 summary")
        ]
        
        # Setup async mocks
        self.mock_code_summary_chain.aapply = MagicMock()
        self.mock_code_summary_chain.aapply.return_value = self.mock_code_summary_outputs
        
        self.mock_pr_summary_chain.ainvoke = MagicMock()
        self.mock_pr_summary_chain.ainvoke.return_value = self.mock_pr_summary_output
        
        # Mock async callbacks manager
        mock_run_manager = MagicMock()
        mock_run_manager.get_child.return_value = MagicMock()
        mock_run_manager.on_text = MagicMock()
        
        # Call async method
        result = await self.chain._acall({"pull_request": self.mock_pr}, mock_run_manager)
        
        # Verify async methods were called
        self.mock_code_summary_chain.aapply.assert_called_once()
        self.mock_pr_summary_chain.ainvoke.assert_called_once()
        
        # Verify result structure
        self.assertIn("pr_summary", result)
        self.assertIn("code_summaries", result)
        
    @patch('codedog.chains.pr_summary.translate_pr_summary_chain.TranslatePRSummaryChain')
    def test_output_parser_failure(self, mock_translate_chain):
        # Create a failing parser
        class FailingParser(BaseOutputParser):
            def parse(self, text):
                raise ValueError("Parsing error")
                
            def get_format_instructions(self):
                return "Format instructions"
        
        # Replace with failing parser
        self.chain.parser = FailingParser()
        
        # The LLM returns text that can't be parsed
        self.mock_pr_summary_chain.return_value = {"text": "Invalid output format"}
        
        # Configure processor to allow test to proceed to the parser
        self.mock_processor.get_diff_code_files.return_value = [MagicMock()]
        
        # Should propagate the parsing error
        with self.assertRaises(ValueError):
            result = self.chain._call({"pull_request": self.mock_pr}, None)

if __name__ == '__main__':
    unittest.main() 