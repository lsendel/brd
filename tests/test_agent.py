import unittest
from unittest.mock import patch, MagicMock
import os
import importlib # For reloading modules
import json # For testing JSON responses

# Ensures tests run without real API access if OPENAI_API_KEY is checked by modules
os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing_agent"

import brd.agent # Import after setting dummy key, before other brd imports
from brd.agent import (
    generate_initial_brd_sections,
    get_clarification_questions,
    refine_project_understanding
)
from brd.prompts import (
    STRATA_BRD_PRO_PERSONA,
    INITIAL_BRD_SECTIONS_TASK_TEMPLATE,
    CLARIFICATION_QUESTIONS_TEMPLATE,
    REFINE_UNDERSTANDING_TEMPLATE
)
from langchain_core.messages import AIMessage
from openai import APIError, RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError
# ChatOpenAI is imported in brd.agent, we patch it there.

class TestAgentFunctions(unittest.TestCase):
    """Test suite for functions in brd.agent module."""

    def setUp(self):
        """Set up for each test. Stores original env vars and reloads brd.agent."""
        self.original_api_key = os.environ.get("OPENAI_API_KEY")
        self.original_model_name = os.environ.get("OPENAI_MODEL_NAME")
        self.original_temperature = os.environ.get("OPENAI_TEMPERATURE")
        os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing"


    def tearDown(self):
        # Restore original environment variables
        if self.original_api_key is None:
            del os.environ["OPENAI_API_KEY"]
        else:
            os.environ["OPENAI_API_KEY"] = self.original_api_key

        if self.original_model_name is None:
            if "OPENAI_MODEL_NAME" in os.environ: del os.environ["OPENAI_MODEL_NAME"]
        else:
            os.environ["OPENAI_MODEL_NAME"] = self.original_model_name

        if self.original_temperature is None:
            if "OPENAI_TEMPERATURE" in os.environ: del os.environ["OPENAI_TEMPERATURE"]
        else:
            os.environ["OPENAI_TEMPERATURE"] = self.original_temperature

        # Reload brd.agent to reset its global `llm` instance based on current env vars.
        # This ensures that changes to env vars in setUp/tearDown are reflected if llm is initialized at module level.
        importlib.reload(brd.agent)

    @patch('brd.agent.ChatOpenAI')
    def test_llm_initialization_with_env_vars(self, mock_chat_openai_class):
        """Test that ChatOpenAI is initialized with model and temperature from env vars."""
        os.environ["OPENAI_MODEL_NAME"] = "env-test-model"
        os.environ["OPENAI_TEMPERATURE"] = "0.123"

        # Mock ChatOpenAI's return value for this specific reload context
        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance

        importlib.reload(brd.agent) # Reload to trigger LLM initialization with new env vars

        mock_chat_openai_class.assert_called_with(model="env-test-model", temperature=0.123)
        self.assertIsNotNone(brd.agent.llm, "LLM instance should be created.")
        self.assertEqual(brd.agent.llm, mock_llm_instance, "LLM instance should be the one from mocked ChatOpenAI.")

    @patch('brd.agent.ChatOpenAI')
    def test_llm_initialization_defaults(self, mock_chat_openai_class):
        """Test ChatOpenAI initialization with default model and temperature."""
        # Ensure specific env vars are not set or are removed
        if "OPENAI_MODEL_NAME" in os.environ: del os.environ["OPENAI_MODEL_NAME"]
        if "OPENAI_TEMPERATURE" in os.environ: del os.environ["OPENAI_TEMPERATURE"]

        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance

        importlib.reload(brd.agent)

        mock_chat_openai_class.assert_called_with(model="gpt-3.5-turbo", temperature=0.7)
        self.assertIsNotNone(brd.agent.llm)

    @patch('brd.agent.llm')
    def test_generate_initial_brd_sections_success(self, mock_llm_instance):
        """Test successful BRD generation with mocked LLM."""
        mock_response_content = "## Executive Summary\nMocked BRD content."
        user_input = "Test input for BRD generation"

        mock_chain = MagicMock()
        # If agent.llm is directly used and is an LLM instance (not a chain)
        mock_llm_instance.invoke.return_value = AIMessage(content=mock_response_content)

        # If the agent constructs a chain like prompt | llm
        # We need to mock the chain construction if llm is not directly invoked.
        # For this test, assuming generate_initial_brd_sections uses `llm.invoke` after forming a prompt.
        # The patch on `brd.agent.llm` replaces the global llm object with our mock_llm_instance.
        # So, any ChatPromptTemplate().from_messages(...) | llm will use our mock.

        # To assert the prompt, we patch ChatPromptTemplate's creation
        with patch('langchain_core.prompts.ChatPromptTemplate.from_messages') as mock_template_builder:
            mock_prompt_instance = MagicMock()
            # When this prompt instance is chained with `| self.mock_llm` (which is `mock_llm_instance` here),
            # it should produce a runnable chain. We make this runnable chain our `mock_llm_instance` itself
            # by having its `invoke` method pre-configured.
            # So, prompt | llm_mock effectively becomes llm_mock if llm_mock is also the chain.
            # A cleaner way: mock_prompt_instance.__or__ = MagicMock(return_value=mock_llm_instance)
            # And then llm_instance.invoke is what we check.

            # Let's refine the mocking for `prompt | llm` structure
            mock_final_chain = MagicMock()
            mock_final_chain.invoke.return_value = AIMessage(content=mock_response_content)
            mock_prompt_instance.__or__ = MagicMock(return_value=mock_final_chain)
            mock_template_builder.return_value = mock_prompt_instance

            result = generate_initial_brd_sections(user_input)

        mock_template_builder.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        ])
        mock_final_chain.invoke.assert_called_once_with({"user_input": user_input})
        self.assertEqual(result, mock_response_content)

    @patch('brd.agent.llm')
    def test_generate_initial_brd_sections_api_error(self, mock_llm_instance):
        """Test APIError during BRD generation."""
        user_input = "Test input for error"

        mock_final_chain = MagicMock()
        mock_final_chain.invoke.side_effect = APIError("LLM API Error", response=MagicMock(status_code=500), body={})
        with patch('langchain_core.prompts.ChatPromptTemplate.from_messages') as mock_template_builder:
            mock_prompt_instance = MagicMock()
            mock_prompt_instance.__or__ = MagicMock(return_value=mock_final_chain)
            mock_template_builder.return_value = mock_prompt_instance

            result = generate_initial_brd_sections(user_input)
        self.assertTrue("Error: An OpenAI API issue occurred (APIError) while generating BRD content." in result)

    @patch('brd.agent.llm')
    def test_generate_initial_brd_sections_auth_error(self, mock_llm_instance):
        """Test AuthenticationError during BRD generation."""
        user_input = "Test input for auth error"
        mock_final_chain = MagicMock()
        mock_final_chain.invoke.side_effect = AuthenticationError("Invalid API Key", response=MagicMock(status_code=401), body={})
        with patch('langchain_core.prompts.ChatPromptTemplate.from_messages') as mock_template_builder:
            mock_prompt_instance = MagicMock()
            mock_prompt_instance.__or__ = MagicMock(return_value=mock_final_chain)
            mock_template_builder.return_value = mock_prompt_instance

            result = generate_initial_brd_sections(user_input)
        self.assertEqual(result, "Error: LLM authentication failed. Please check your API key. BRD generation could not be completed.")

    def test_generate_initial_brd_sections_llm_none(self):
        """Test BRD generation behavior when LLM is None (e.g., API key missing)."""
        # This test needs to ensure brd.agent.llm is None *globally* within the module for this test's scope.
        # setUp and tearDown with importlib.reload handle resetting the module's llm.
        with patch('brd.agent.llm', None): # Temporarily set the module's llm to None
            result = generate_initial_brd_sections("Some input")
        self.assertTrue("ERROR: LLM NOT AVAILABLE" in result)
        self.assertTrue("Input received: \"Some input" in result)


class TestGetClarificationQuestions(unittest.TestCase):
    """Test suite for get_clarification_questions function."""
    def setUp(self):
        """Set up for each test, ensuring a mocked LLM environment."""
        # Store and restore env vars that might affect llm initialization
        self.original_api_key = os.environ.get("OPENAI_API_KEY")
        self.original_model_name = os.environ.get("OPENAI_MODEL_NAME")
        self.original_temperature = os.environ.get("OPENAI_TEMPERATURE")
        os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing" # Ensure key for this scope
        importlib.reload(brd.agent) # Reload to apply env var changes to llm object if necessary

        # Patch the llm instance within brd.agent for all tests in this class
        self.llm_patcher = patch('brd.agent.llm')
        self.mock_llm_instance = self.llm_patcher.start()

        # This mock_llm_instance will be used by the chain. It needs an invoke method.
        self.mock_llm_instance.invoke = MagicMock()

        # Mock the chain construction (ChatPromptTemplate.from_messages(...) | llm)
        self.chain_patcher = patch('langchain_core.prompts.ChatPromptTemplate.from_messages')
        self.mock_from_messages = self.chain_patcher.start()

        self.mock_prompt_object = MagicMock() # This is what from_messages returns
        self.mock_final_chain_object = MagicMock() # This is what (prompt | llm) returns

        self.mock_from_messages.return_value = self.mock_prompt_object
        self.mock_prompt_object.__or__ = MagicMock(return_value=self.mock_final_chain_object)

    def tearDown(self):
        """Tear down after each test."""
        self.llm_patcher.stop()
        self.chain_patcher.stop()

        # Restore original environment variables
        if self.original_api_key is None:
            if "OPENAI_API_KEY" in os.environ: del os.environ["OPENAI_API_KEY"]
        else:
            os.environ["OPENAI_API_KEY"] = self.original_api_key

        if self.original_model_name is None:
            if "OPENAI_MODEL_NAME" in os.environ: del os.environ["OPENAI_MODEL_NAME"]
        else:
            os.environ["OPENAI_MODEL_NAME"] = self.original_model_name

        if self.original_temperature is None:
            if "OPENAI_TEMPERATURE" in os.environ: del os.environ["OPENAI_TEMPERATURE"]
        else:
            os.environ["OPENAI_TEMPERATURE"] = self.original_temperature

        importlib.reload(brd.agent) # Reload agent to reflect original env var state for llm

    def test_no_questions_needed(self):
        """Test when LLM indicates no clarification questions are needed."""
        self.mock_final_chain_object.invoke.return_value = AIMessage(content="NO_QUESTIONS_NEEDED")

        questions = get_clarification_questions("summary", "utterance")

        self.assertEqual(questions, [])
        self.mock_from_messages.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", CLARIFICATION_QUESTIONS_TEMPLATE)
        ])
        self.mock_final_chain_object.invoke.assert_called_once_with({
            "current_project_summary": "summary",
            "latest_user_utterance": "utterance"
        })

    def test_questions_returned_json(self):
        """Test successful parsing of JSON formatted questions from LLM."""
        expected_qs = ["Question one?", "Question two?"]
        json_response = json.dumps(expected_qs)
        self.mock_chain.invoke.return_value = AIMessage(content=json_response)
        questions = get_clarification_questions("summary", "utterance")
        self.assertEqual(questions, expected_qs)

    def test_questions_fallback_parsing(self):
        response_content = "1. Fallback Q1?\n2. Fallback Q2?"
        expected_qs = ["Fallback Q1?", "Fallback Q2?"]
        self.mock_chain.invoke.return_value = AIMessage(content=response_content)
        # Mock json.loads to fail, forcing fallback
        with patch('json.loads', side_effect=json.JSONDecodeError("mock error", "doc", 0)):
            questions = get_clarification_questions("summary", "utterance for fallback")
        self.assertEqual(questions, expected_qs)

    def test_questions_json_not_list_fallback(self):
        response_content = json.dumps({"not_a": "list"}) # Valid JSON, but not a list
        # Fallback should try to parse "{"not_a": "list"}" as a question itself.
        # The current regex fallback might parse this strangely or return it as one line.
        # The prompt now asks for JSON list of strings. If it's not that, it's malformed from LLM.
        # The agent code has: `print("WARNING: LLM response was valid JSON but not a list of strings. Falling back to text parsing.")`
        # The fallback will then try to parse the string `{"not_a": "list"}`.
        # `re.sub(r"^\s*(\d+[\.\)]\s*|-\s*)", "", original_line_stripped).strip()` will not change it.
        # So it will be added as is.
        expected_qs = ['{"not_a": "list"}']
        self.mock_chain.invoke.return_value = AIMessage(content=response_content)
        questions = get_clarification_questions("summary", "utterance for json not list")
        self.assertEqual(questions, expected_qs)


    def test_questions_llm_api_error(self):
        self.mock_chain.invoke.side_effect = APIError("LLM API Error", response=MagicMock(), body={})
        questions = get_clarification_questions("summary", "utterance")
        self.assertEqual(questions, ["LLM_API_ERROR: APIError. Could not get clarification questions."])

    def test_questions_llm_auth_error(self):
        self.mock_chain.invoke.side_effect = AuthenticationError("Invalid API Key", response=MagicMock(), body={})
        questions = get_clarification_questions("summary", "utterance")
        self.assertEqual(questions, ["LLM_AUTH_ERROR: Authentication failed. Could not get clarification questions."])

    def test_llm_none_get_clarification_questions(self):
        self.patcher.stop() # Stop the main patch for brd.agent.llm
        self.mock_prompt_template_patcher.stop() # also stop this one

        import brd.agent
        original_llm_val = brd.agent.llm
        brd.agent.llm = None
        try:
            questions = get_clarification_questions("summary", "utterance")
            self.assertEqual(questions, ["LLM_UNAVAILABLE: Could not generate clarification questions due to missing API key."])
        finally:
            brd.agent.llm = original_llm_val
            # Re-patch for other tests if this test class continues
            self.patcher.start()
            self.mock_prompt_template_patcher.start()


# --- Tests for refine_project_understanding ---
class TestRefineProjectUnderstanding(unittest.TestCase):
    def setUp(self):
        os.environ["OPENAI_API_KEY"] = "dummy_api_key_for_testing"
        self.patcher = patch('brd.agent.llm')
        self.mock_llm = self.patcher.start()

        self.mock_chain = MagicMock()
        self.mock_llm.invoke = self.mock_chain.invoke

        self.mock_prompt_template_patcher = patch('langchain_core.prompts.ChatPromptTemplate.from_messages')
        self.mock_from_messages = self.mock_prompt_template_patcher.start()
        self.mock_prompt_obj = MagicMock()
        self.mock_prompt_obj.__or__ = MagicMock(return_value=self.mock_chain)
        self.mock_from_messages.return_value = self.mock_prompt_obj

    def tearDown(self):
        self.patcher.stop()
        self.mock_prompt_template_patcher.stop()
        import importlib
        import brd.agent
        importlib.reload(brd.agent)

    def test_summary_refined_successfully(self):
        expected_refined_summary = "This is the revised summary."
        self.mock_chain.invoke.return_value = AIMessage(content=expected_refined_summary)

        summary = refine_project_understanding("Original summary", ["Q1?"], "A1.")
        self.assertEqual(summary, expected_refined_summary)
        self.mock_from_messages.assert_called_once_with([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", REFINE_UNDERSTANDING_TEMPLATE)
        ])
        self.mock_chain.invoke.assert_called_once_with({
            "current_project_summary": "Original summary",
            "questions_that_were_asked": "1. Q1?",
            "user_answers": "A1."
        })

    def test_refine_llm_api_error(self):
        original_summary_text = "Original summary before error."
        self.mock_chain.invoke.side_effect = APIError("LLM API Error", response=MagicMock(), body={})

        summary = refine_project_understanding(original_summary_text, ["Q1?"], "A1.")
        self.assertEqual(summary, f"{original_summary_text}\n\n[LLM_API_ERROR: APIError. Could not refine project understanding.]")

    def test_refine_llm_auth_error(self):
        original_summary_text = "Original summary before auth error."
        self.mock_chain.invoke.side_effect = AuthenticationError("Bad Key", response=MagicMock(), body={})

        summary = refine_project_understanding(original_summary_text, ["Q1?"], "A1.")
        self.assertEqual(summary, f"{original_summary_text}\n\n[LLM_AUTH_ERROR: Authentication failed. Could not refine project understanding.]")


    def test_llm_none_refine_project_understanding(self):
        self.patcher.stop() # Stop the main patch for brd.agent.llm
        self.mock_prompt_template_patcher.stop()

        import brd.agent
        original_llm_val = brd.agent.llm
        brd.agent.llm = None
        original_summary_text = "Original summary, LLM is None."
        try:
            summary = refine_project_understanding(original_summary_text, ["Q1?"], "A1.")
            self.assertEqual(summary, f"{original_summary_text}\n\n[LLM_UNAVAILABLE: Could not refine project understanding due to missing API key. The above understanding is based on previous information only.]")
        finally:
            brd.agent.llm = original_llm_val
            self.patcher.start()
            self.mock_prompt_template_patcher.start()

    def test_refine_with_error_placeholder_questions(self):
        expected_refined_summary = "Refined summary based on answers to no valid questions."
        self.mock_chain.invoke.return_value = AIMessage(content=expected_refined_summary)

        summary = refine_project_understanding(
            "Initial concept.",
            ["LLM_AUTH_ERROR: Authentication failed."],
            "User provides an answer anyway."
        )
        self.assertEqual(summary, expected_refined_summary)
        self.mock_chain.invoke.assert_called_once_with({
            "current_project_summary": "Initial concept.",
            "questions_that_were_asked": "No valid questions were previously generated due to an error.",
            "user_answers": "User provides an answer anyway."
        })


if __name__ == '__main__':
    unittest.main()
