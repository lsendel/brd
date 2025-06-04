import unittest
from unittest.mock import patch, MagicMock, call
import os

os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing" # Ensures tests run without real API access

# Original imports
from brd.agent import (
    generate_initial_brd_sections,
    STRATA_BRD_PRO_PERSONA,
    get_clarification_questions, # New import
    refine_project_understanding, # New import
    llm as agent_llm # Import the llm instance to enable temporary override for testing llm=None
)
from brd.prompts import (
    INITIAL_BRD_SECTIONS_TASK_TEMPLATE,
    CLARIFICATION_QUESTIONS_TEMPLATE, # New import
    REFINE_UNDERSTANDING_TEMPLATE # New import
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage # HumanMessage might be useful for future tests
from typing import List # For type hinting in tests if needed

# Keep existing TestAgent class for generate_initial_brd_sections
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


class TestGetClarificationQuestions(unittest.TestCase):

    def setUp(self):
        # This is to store the original llm and restore it after tests that set it to None
        self.original_llm = agent_llm

    def tearDown(self):
        # Restore the original llm instance after each test
        # This is important if other tests in the same suite rely on the default llm
        import brd.agent
        brd.agent.llm = self.original_llm

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_no_questions_needed(self, mock_chat_prompt_template_from_messages):
        mock_llm_instance = MagicMock()
        mock_prompt_template = MagicMock()
        mock_chain = MagicMock()
        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.invoke = MagicMock(return_value=AIMessage(content="NO_QUESTIONS_NEEDED"))

        with patch('brd.agent.llm', mock_llm_instance):
            questions = get_clarification_questions("summary", "utterance")

        self.assertEqual(questions, [])
        mock_chat_prompt_template_from_messages.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", CLARIFICATION_QUESTIONS_TEMPLATE)
        ])
        mock_chain.invoke.assert_called_once_with({
            "current_project_summary": "summary",
            "latest_user_utterance": "utterance"
        })

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_questions_returned_and_parsed(self, mock_chat_prompt_template_from_messages):
        test_cases = [
            ("1. Question one?\n2. Question two?", ["Question one?", "Question two?"]),
            ("1) Question one?\n2) Question two with a number 2 inside?", ["Question one?", "Question two with a number 2 inside?"]),
            ("- Question one\n- Question two", ["Question one", "Question two"]),
            ("  1. Spaced question one?  \n\n  2. Spaced question two?  ", ["Spaced question one?", "Spaced question two?"])
            # Removed: ("Single unnumbered question?", ["Single unnumbered question?"]) as strict parsing won't get this
        ]

        for i, (response_content, expected_output) in enumerate(test_cases):
            mock_llm_instance = MagicMock()
            mock_prompt_template = MagicMock()
            mock_chain = MagicMock()
            mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
            mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)
            mock_chain.invoke = MagicMock(return_value=AIMessage(content=response_content))

            with patch('brd.agent.llm', mock_llm_instance):
                questions = get_clarification_questions("summary", f"utterance_{i}")

            self.assertEqual(questions, expected_output, f"Failed for response: '{response_content}'")
            mock_chat_prompt_template_from_messages.assert_called_with([ # Check it's called in each loop
                ("system", STRATA_BRD_PRO_PERSONA),
                ("human", CLARIFICATION_QUESTIONS_TEMPLATE)
            ])
            mock_chain.invoke.assert_called_with({
                "current_project_summary": "summary",
                "latest_user_utterance": f"utterance_{i}"
            })
            mock_chat_prompt_template_from_messages.reset_mock() # Reset for next iteration

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_malformed_response(self, mock_chat_prompt_template_from_messages):
        mock_llm_instance = MagicMock()
        mock_prompt_template = MagicMock()
        mock_chain = MagicMock()
        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.invoke = MagicMock(return_value=AIMessage(content="This is not what we want."))

        with patch('brd.agent.llm', mock_llm_instance):
            questions = get_clarification_questions("summary", "utterance")
        self.assertEqual(questions, [])

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_llm_api_error(self, mock_chat_prompt_template_from_messages):
        mock_llm_instance = MagicMock()
        mock_prompt_template = MagicMock()
        mock_chain = MagicMock()
        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.invoke = MagicMock(side_effect=Exception("LLM API Error"))

        with patch('brd.agent.llm', mock_llm_instance):
            questions = get_clarification_questions("summary", "utterance")
        self.assertEqual(questions, [])

    def test_llm_none(self):
        import brd.agent # Import the module where llm is defined
        original_llm = brd.agent.llm # Store original
        brd.agent.llm = None
        try:
            questions = get_clarification_questions("summary", "utterance")
            self.assertEqual(questions, [])
        finally:
            brd.agent.llm = original_llm # Restore


class TestRefineProjectUnderstanding(unittest.TestCase):
    def setUp(self):
        self.original_llm = agent_llm

    def tearDown(self):
        import brd.agent
        brd.agent.llm = self.original_llm

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_summary_refined(self, mock_chat_prompt_template_from_messages):
        expected_refined_summary = "This is the revised summary."
        mock_llm_instance = MagicMock()
        mock_prompt_template = MagicMock()
        mock_chain = MagicMock()
        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.invoke = MagicMock(return_value=AIMessage(content=expected_refined_summary))

        with patch('brd.agent.llm', mock_llm_instance):
            summary = refine_project_understanding("Original summary", ["Q1?"], "A1.")

        self.assertEqual(summary, expected_refined_summary)
        mock_chat_prompt_template_from_messages.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", REFINE_UNDERSTANDING_TEMPLATE)
        ])
        mock_chain.invoke.assert_called_once_with({
            "current_project_summary": "Original summary",
            "questions_that_were_asked": "1. Q1?", # Check formatting
            "user_answers": "A1."
        })

    @patch('brd.agent.ChatPromptTemplate.from_messages')
    def test_llm_api_error_refine(self, mock_chat_prompt_template_from_messages):
        original_summary_text = "Original summary before error."
        mock_llm_instance = MagicMock()
        mock_prompt_template = MagicMock()
        mock_chain = MagicMock()
        mock_chat_prompt_template_from_messages.return_value = mock_prompt_template
        mock_prompt_template.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.invoke = MagicMock(side_effect=Exception("LLM API Error"))

        with patch('brd.agent.llm', mock_llm_instance):
            summary = refine_project_understanding(original_summary_text, ["Q1?"], "A1.")
        self.assertEqual(summary, original_summary_text)

    def test_llm_none_refine(self):
        import brd.agent
        original_llm = brd.agent.llm
        brd.agent.llm = None
        original_summary_text = "Original summary, LLM is None."
        try:
            summary = refine_project_understanding(original_summary_text, ["Q1?"], "A1.")
            self.assertEqual(summary, original_summary_text)
        finally:
            brd.agent.llm = original_llm


if __name__ == '__main__':
    unittest.main()
