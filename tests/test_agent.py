import unittest
from unittest.mock import patch, MagicMock
import os

os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing"

from brd.agent import generate_initial_brd_sections
from langchain_core.messages import AIMessage

class TestAgent(unittest.TestCase):

    @patch('brd.agent.llm')
    def test_generate_initial_brd_sections_mocked_llm(self, mock_llm_object):
        mock_response_content = "## Executive Summary\nMocked BRD content."

        # Configure the 'invoke' attribute of the mock_llm_object to be a new MagicMock
        mock_llm_object.invoke = MagicMock(return_value=AIMessage(content=mock_response_content))

        user_input = "Test input for BRD generation"
        result = generate_initial_brd_sections(user_input)

        mock_llm_object.invoke.assert_called_once()
        self.assertEqual(result, mock_response_content)

    @patch('brd.agent.llm')
    def test_generate_initial_brd_sections_error_handling(self, mock_llm_object):
        # Configure the 'invoke' attribute of the mock_llm_object to be a new MagicMock that raises an error
        mock_llm_object.invoke = MagicMock(side_effect=Exception("LLM API Error"))

        user_input = "Test input for error"
        result = generate_initial_brd_sections(user_input)

        self.assertEqual(result, "Error: Could not generate BRD content due to an LLM error.")
        mock_llm_object.invoke.assert_called_once()

if __name__ == '__main__':
    unittest.main()
