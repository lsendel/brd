import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Set a dummy API key for tests.
os.environ["OPENAI_API_KEY"] = "test_key_for_graph"

# Try to import langgraph-dependent modules, skip tests if not available
try:
    from brd.graph import create_graph, AgentState # AgentState is imported for type hinting if needed
    # HumanMessage and AIMessage are used for verifying final_state['messages']
    from langchain_core.messages import HumanMessage, AIMessage # Ensure BaseMessage is also available if needed for broader checks
    from brd.agent import llm as agent_llm # To control LLM presence for graph tests testing
    LANGGRAPH_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Skipping graph tests due to import error: {e}")
    LANGGRAPH_AVAILABLE = False

@unittest.skipIf(not LANGGRAPH_AVAILABLE, "langgraph module not available")
class TestGraph(unittest.TestCase):
    """Tests for the main graph creation and basic flow."""

    @unittest.skipIf(not LANGGRAPH_AVAILABLE, "langgraph module not available")
    def setUp(self):
        """Set up for graph tests."""
        # Store original LLM from brd.agent, then set to None to ensure no real API calls
        # if agent functions are not perfectly mocked. Agent functions should handle llm=None.
        self.original_agent_llm = agent_llm
        import brd.agent # Ensure we are modifying the correct module's llm
        brd.agent.llm = None

        self.app = create_graph()
        self.thread_id_counter = 0 # For generating unique thread IDs

    def tearDown(self):
        """Restore original LLM in brd.agent."""
        import brd.agent
        brd.agent.llm = self.original_agent_llm
        # Reloading might be more robust if other module-level things changed
        # import importlib
        # importlib.reload(brd.agent)


    def _get_config(self, test_name: str = "default_test") -> dict:
        """Helper to generate unique config for each test run."""
        self.thread_id_counter += 1
        return {"configurable": {"thread_id": f"test-graph-thread-{test_name}-{self.thread_id_counter}"}}

    def test_create_graph_returns_graph(self):
        """Test if create_graph returns a compiled graph object."""
        self.assertIsNotNone(self.app, "Graph app should not be None.")
        self.assertTrue(hasattr(self.app, "invoke"), "Graph app should have an invoke method.")
        self.assertTrue(hasattr(self.app, "stream"), "Graph app should have a stream method.")

    @patch('brd.graph.generate_initial_brd_sections') # Patch where it's used by graph.py
    def test_graph_invocation_simple_flow(self, mock_gen_brd):
        """Test a simple flow: input -> start_node -> analyze_input (no questions) -> generate_brd -> END."""
        mock_brd_content = "Mocked BRD from graph test - simple flow"
        mock_gen_brd.return_value = mock_brd_content

        # Mock get_clarification_questions to return no questions
        with patch('brd.graph.get_clarification_questions') as mock_get_questions:
            mock_get_questions.return_value = [] # No questions needed

            initial_state: AgentState = {
                "userInput": "Test graph input for simple flow",
                "messages": [],
                # Other fields will be initialized by start_node
            }
            config = self._get_config("simple_flow")
            final_state = self.app.invoke(initial_state, config=config)

            mock_get_questions.assert_called_once()
            mock_gen_brd.assert_called_once_with("Test graph input for simple flow") # Based on current_understanding

            self.assertEqual(final_state.get('current_brd_content'), mock_brd_content)
            self.assertIn(HumanMessage(content="Test graph input for simple flow"), final_state['messages'])
            self.assertTrue(
                any(isinstance(msg, AIMessage) and mock_brd_content in msg.content for msg in final_state['messages']),
                "AIMessage with mocked BRD content not found."
            )

# Renaming for clarity and consistency
@unittest.skipIf(not LANGGRAPH_AVAILABLE, "langgraph module not available")
class TestGraphClarificationLoop(unittest.TestCase):
    """Tests focusing on the clarification loop within the graph."""

    @unittest.skipIf(not LANGGRAPH_AVAILABLE, "langgraph module not available")
    def setUp(self):
        """Set up for clarification loop tests."""
        self.app = create_graph()
        self.thread_id_counter = 0

        # Ensure brd.agent.llm is None for these tests to rely on mocks or llm=None paths in agent functions.
        self.original_agent_llm = agent_llm
        import brd.agent
        brd.agent.llm = None

    def tearDown(self):
        """Restore original LLM in brd.agent."""
        import brd.agent
        brd.agent.llm = self.original_agent_llm

    def _get_config(self, test_name_suffix: str = "") -> dict:
        """Helper to generate unique config for each test run."""
        self.thread_id_counter +=1
        return {"configurable": {"thread_id": f"clarification-loop-{test_name_suffix}-{self.thread_id_counter}"}}

    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_no_questions_needed_straight_to_brd(self, mock_gen_brd, mock_get_questions):
        """Test graph flow when no clarification questions are needed."""
        mock_get_questions.return_value = []
        mock_gen_brd.return_value = "Mocked BRD Content - No Questions"

        initial_state: AgentState = {"userInput": "Perfect input, no questions needed", "messages": []}
        config = self._get_config("no_q_straight")
        final_state = self.app.invoke(initial_state, config=config)

        mock_get_questions.assert_called_once_with(
            current_project_summary="Perfect input, no questions needed", # From start_node's current_understanding
            latest_user_utterance="Perfect input, no questions needed"  # From start_node's userInput
        )
        mock_gen_brd.assert_called_once_with("Perfect input, no questions needed")
        self.assertEqual(final_state.get('current_brd_content'), "Mocked BRD Content - No Questions")
        self.assertFalse(final_state.get('clarification_questions_pending_answer'))
        self.assertEqual(final_state.get('current_clarification_round'), 0)

    @patch('brd.graph.refine_project_understanding')
    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_one_round_clarification_then_brd(self, mock_gen_brd, mock_get_questions, mock_refine_understanding):
        """Test a single round of clarification: ask, answer, refine, generate."""
        config = self._get_config("one_round_clarification")
        initial_userInput = "Needs some details for one round"

        # --- Turn 1: Agent asks questions ---
        questions_to_ask = ["Q1: What's the primary objective?"]
        mock_get_questions.return_value = questions_to_ask # First call

        initial_state_turn1: AgentState = {"userInput": initial_userInput, "messages": []}
        final_state_turn1 = self.app.invoke(initial_state_turn1, config=config)

        mock_get_questions.assert_called_once_with(
            current_project_summary=initial_userInput, latest_user_utterance=initial_userInput
        )
        self.assertTrue(final_state_turn1.get('clarification_questions_pending_answer'))
        self.assertEqual(final_state_turn1.get('clarification_questions'), questions_to_ask)
        self.assertIn("Q1: What's the primary objective?", final_state_turn1['messages'][-1].content)
        self.assertEqual(final_state_turn1.get('current_clarification_round'), 0)

        # --- Turn 2: User answers, Agent generates BRD ---
        current_state_turn2 = final_state_turn1.copy()
        current_state_turn2["messages"] = list(final_state_turn1["messages"])
        user_answers = "A1: Objective is to test this."
        current_state_turn2["messages"].append(HumanMessage(content=user_answers))

        refined_text = f"Refined: {initial_userInput}. Objective: test this."
        mock_refine_understanding.return_value = refined_text
        mock_get_questions.reset_mock() # Reset for the second call to get_clarification_questions
        mock_get_questions.return_value = [] # No more questions after refinement
        mock_gen_brd.return_value = "BRD from One Round Refined Understanding"

        final_state_turn2 = self.app.invoke(current_state_turn2, config=config)

        mock_refine_understanding.assert_called_once_with(
            current_summary=initial_userInput,
            questions_asked=questions_to_ask,
            user_answers=user_answers
        )
        self.assertEqual(final_state_turn2.get('current_understanding'), refined_text)
        self.assertEqual(final_state_turn2.get('current_clarification_round'), 1)
        mock_get_questions.assert_called_once_with(
            current_project_summary=refined_text, latest_user_utterance=user_answers
        )
        self.assertFalse(final_state_turn2.get('clarification_questions_pending_answer'))
        mock_gen_brd.assert_called_once_with(refined_text)
        self.assertEqual(final_state_turn2.get('current_brd_content'), "BRD from One Round Refined Understanding")

    @patch('brd.graph.refine_project_understanding')
    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_max_clarification_rounds_reached(self, mock_gen_brd, mock_get_questions, mock_refine_understanding):
        """Test graph behavior when max_clarification_rounds is reached."""
        config = self._get_config("max_rounds_test")
        # Default max_rounds is 3, set by start_node if not in initial_state
        # For this test, we'll rely on that default.
        max_rounds_expected = 3

        mock_get_questions.return_value = ["Another question?"] # Always returns a question

        # Mock refine_project_understanding to show accumulation
        def refine_side_effect(current_summary, questions_asked, user_answers):
            return f"{current_summary} + {user_answers}"
        mock_refine_understanding.side_effect = refine_side_effect
        mock_gen_brd.return_value = "BRD after max rounds reached"

        current_state: AgentState = {"userInput": "Very vague idea", "messages": []}

        for i in range(max_rounds_expected): # Loop for max_rounds times to provide answers
            # print(f"\n--- Test Max Rounds: Iteration {i + 1} (Asking/Processing Round {current_state.get('current_clarification_round',0)}) ---")
            # Invoke to ask question
            state_after_asking = self.app.invoke(current_state, config=config)
            self.assertTrue(state_after_asking.get('clarification_questions_pending_answer'))

            # Prepare state for providing answer
            current_state = state_after_asking.copy()
            current_state["messages"] = list(state_after_asking["messages"])
            current_state["messages"].append(HumanMessage(content=f"Answer round {i+1}"))

        # One final invocation to process the last answer and hit the max_rounds limit
        final_state = self.app.invoke(current_state, config=config)

        self.assertFalse(final_state.get('clarification_questions_pending_answer'))
        self.assertEqual(final_state.get('current_clarification_round'), max_rounds_expected)
        # get_clarification_questions is called:
        # 1 (initial) + max_rounds_expected (after each answer) = max_rounds_expected + 1
        self.assertEqual(mock_get_questions.call_count, max_rounds_expected + 1)
        self.assertEqual(mock_refine_understanding.call_count, max_rounds_expected)
        mock_gen_brd.assert_called_once()
        self.assertEqual(final_state.get('current_brd_content'), "BRD after max rounds reached")
        self.assertTrue(any("Clarification round limit reached" in msg.content for msg in final_state.get('messages', []) if isinstance(msg, AIMessage)))

    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_max_clarification_rounds_configurable(self, mock_gen_brd, mock_get_questions):
        """Test that max_clarification_rounds can be configured via initial state."""
        config = self._get_config("max_rounds_configurable_test")
        custom_max_rounds = 1

        mock_get_questions.return_value = ["A question?"]
        mock_gen_brd.return_value = "BRD after 1 custom round"

        initial_state_turn1: AgentState = {
            "userInput": "Configurable max rounds test",
            "messages": [],
            "max_clarification_rounds": custom_max_rounds # Override default
        }

        # Turn 1: Agent asks questions (current_round is 0)
        final_state_turn1 = self.app.invoke(initial_state_turn1, config=config)
        self.assertTrue(final_state_turn1.get('clarification_questions_pending_answer'))
        self.assertEqual(final_state_turn1.get('max_clarification_rounds'), custom_max_rounds)

        # Turn 2: User provides answers. Round becomes 1. analyze_input sees current_round >= max_rounds.
        current_state_turn2 = final_state_turn1.copy()
        current_state_turn2["messages"] = list(final_state_turn1["messages"])
        current_state_turn2["messages"].append(HumanMessage(content="Answer for custom max_rounds"))

        with patch('brd.graph.refine_project_understanding') as mock_refine:
            mock_refine.return_value = "Refined from custom max_rounds test"
            final_state_turn2 = self.app.invoke(current_state_turn2, config=config)

        self.assertEqual(final_state_turn2.get('current_clarification_round'), custom_max_rounds)
        self.assertEqual(mock_get_questions.call_count, custom_max_rounds + 1) # Initial + after answer
        self.assertFalse(final_state_turn2.get('clarification_questions_pending_answer'))
        mock_gen_brd.assert_called_once_with("Refined from custom max_rounds test")
        self.assertTrue(any("Clarification round limit reached" in msg.content for msg in final_state_turn2.get('messages', []) if isinstance(msg, AIMessage)))

    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_error_propagation_from_get_questions(self, mock_gen_brd, mock_get_questions):
        """Test error propagation when get_clarification_questions returns an error message."""
        config = self._get_config("error_get_questions_test")
        error_message = "LLM_UNAVAILABLE: Test error getting questions"
        mock_get_questions.return_value = [error_message]
        mock_gen_brd.return_value = "BRD content (error path)"

        initial_state: AgentState = {"userInput": "Input for get_questions error test", "messages": []}
        final_state = self.app.invoke(initial_state, config=config)

        self.assertTrue(any(f"Agent Error: Could not retrieve clarification questions. Details: {error_message}" in msg.content
                            for msg in final_state.get('messages', []) if isinstance(msg, AIMessage)))
        mock_gen_brd.assert_called_once() # Graph should proceed to generation
        self.assertFalse(final_state.get('clarification_questions_pending_answer'))

    @patch('brd.graph.generate_initial_brd_sections')
    def test_error_propagation_from_generate_brd(self, mock_gen_brd):
        """Test error propagation when generate_initial_brd_sections returns an error."""
        config = self._get_config("error_generate_brd_test")
        error_message_brd = "ERROR: LLM not available for BRD generation (test)"

        with patch('brd.graph.get_clarification_questions') as mock_get_questions_for_err:
            mock_get_questions_for_err.return_value = [] # No questions
            mock_gen_brd.return_value = error_message_brd

            initial_state: AgentState = {"userInput": "Input for generate_brd error test", "messages": []}
            final_state = self.app.invoke(initial_state, config=config)

        self.assertEqual(final_state.get('current_brd_content'), error_message_brd)
        self.assertTrue(any(f"Could not generate BRD. Details: {error_message_brd}" in msg.content
                            for msg in final_state.get('messages', []) if isinstance(msg, AIMessage)))

    @patch('brd.graph.refine_project_understanding')
    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_error_propagation_from_refine_understanding(self, mock_gen_brd, mock_get_questions, mock_refine_understanding):
        """Test error propagation when refine_project_understanding returns an error."""
        config = self._get_config("error_refine_test")
        initial_userInput = "Input for refine_understanding error test"

        # Turn 1: Ask questions
        questions_to_ask = ["Q_refine_error?"]
        mock_get_questions.side_effect = [questions_to_ask, []]
        initial_state_turn1: AgentState = {"userInput": initial_userInput, "messages": []}
        final_state_turn1 = self.app.invoke(initial_state_turn1, config=config)
        self.assertTrue(final_state_turn1.get('clarification_questions_pending_answer'))

        # Turn 2: Provide answers, refine_project_understanding returns an error
        current_state_turn2 = final_state_turn1.copy()
        current_state_turn2["messages"] = list(final_state_turn1["messages"]) + [HumanMessage(content="A_refine_error")]

        error_message_refine = "[LLM_AUTH_ERROR: Refinement failed (test)]"
        mock_refine_understanding.return_value = error_message_refine
        mock_gen_brd.return_value = "BRD after refinement error (test)"

        final_state_turn2 = self.app.invoke(current_state_turn2, config=config)

        self.assertTrue(any(f"Agent Error during understanding refinement. Details: {error_message_refine}" in msg.content
                            for msg in final_state_turn2.get('messages', []) if isinstance(msg, AIMessage)))
        self.assertEqual(final_state_turn2.get('current_understanding'), initial_userInput) # Should revert to pre-error understanding
        mock_gen_brd.assert_called_once()
        self.assertEqual(final_state_turn2.get('current_brd_content'), "BRD after refinement error (test)")

    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_insufficient_input_to_end_due_to_error_route(self, mock_gen_brd, mock_get_questions):
        """Test graph routing to END if initial input and understanding are empty."""
        config = self._get_config("insufficient_input_test")
        initial_state: AgentState = {"userInput": "", "messages": []} # current_understanding will also be empty
        mock_get_questions.return_value = [] # Should not be called if error route taken first

        final_state = self.app.invoke(initial_state, config=config)

        expected_error_msg = "INTERNAL ERROR: Cannot proceed with question generation due to missing context."
        self.assertTrue(
            any(expected_error_msg in msg.content for msg in final_state.get('messages', []) if isinstance(msg, AIMessage))
        )
        mock_gen_brd.assert_not_called()
        self.assertFalse(final_state.get('clarification_questions_pending_answer'))

if __name__ == '__main__':
    unittest.main()
