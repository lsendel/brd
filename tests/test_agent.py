import unittest
from unittest.mock import patch, MagicMock, call
import os

os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing"

from brd.agent import generate_initial_brd_sections, STRATA_BRD_PRO_PERSONA # Import persona for assertion
from brd.prompts import INITIAL_BRD_SECTIONS_TASK_TEMPLATE
from langchain_core.prompts import ChatPromptTemplate # Correct import
from langchain_core.messages import AIMessage

class TestAgent(unittest.TestCase):

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_generate_initial_brd_sections_mocked_llm(self, mock_chat_prompt_template_from_messages):
        mock_response_content = "## Executive Summary\nMocked BRD content."
        user_input = "Test input for BRD generation"

        mock_llm_instance = MagicMock() # Stand-in for the actual llm
        mock_prompt_template = MagicMock() # Stand-in for the prompt template
        mock_chain = MagicMock() # Stand-in for the combined chain (prompt_template | llm)

        # ChatPromptTemplate.from_messages returns our mock_prompt_template
        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template

        # The __or__ method of mock_prompt_template (when `| llm` is called)
        # should return our mock_chain
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)

        # Configure the invoke method of the final chain object
        mock_chain.invoke = MagicMock(return_value=AIMessage(content=mock_response_content))

        # Patch 'brd.agent.llm' so that when `prompt_template | llm` is evaluated in agent code,
        # 'llm' is our 'mock_llm_instance'.
        with patch('brd.agent.llm', mock_llm_instance):
            result = generate_initial_brd_sections(user_input)

        # Verify ChatPromptTemplate.from_messages was called correctly
        mock_chat_prompt_template_from_messages.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        ])

        # Verify that the prompt template's __or__ method was called with our mock_llm_instance
        mock_prompt_template.__or__.assert_called_once_with(mock_llm_instance)

        # Verify that invoke was called on the final chain object with the correct arguments
        mock_chain.invoke.assert_called_once_with({"user_input": user_input})

        self.assertEqual(result, mock_response_content)

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_generate_initial_brd_sections_error_handling(self, mock_chat_prompt_template_from_messages):
        user_input = "Test input for error"

        mock_llm_instance = MagicMock()
        mock_prompt_template = MagicMock()
        mock_chain = MagicMock()

        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)

        # Configure the invoke method of the final chain object to raise an error
        mock_chain.invoke = MagicMock(side_effect=Exception("LLM API Error"))

        with patch('brd.agent.llm', mock_llm_instance):
            result = generate_initial_brd_sections(user_input)

        mock_chat_prompt_template_from_messages.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        ])
        mock_prompt_template.__or__.assert_called_once_with(mock_llm_instance)
        mock_chain.invoke.assert_called_once_with({"user_input": user_input})
        self.assertEqual(result, "Error: An unexpected issue occurred while generating BRD content.")

if __name__ == '__main__':
    unittest.main()
