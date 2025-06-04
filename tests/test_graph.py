import unittest
from unittest.mock import patch, MagicMock
import os

# Set a dummy API key for tests.
os.environ["OPENAI_API_KEY"] = "test_key_for_graph"

from brd.graph import create_graph, AgentState # AgentState is imported for type hinting if needed
# HumanMessage and AIMessage are used for verifying final_state['messages']
from langchain_core.messages import HumanMessage, AIMessage # Ensure BaseMessage is also available if needed for broader checks
from brd.agent import llm as agent_llm # To control LLM presence for graph tests

class TestGraph(unittest.TestCase):

    def setUp(self):
        # Store original LLM, then set to None to ensure no real API calls during graph tests
        # if agent functions are not perfectly mocked. Agent functions themselves should handle llm=None.
        self.original_agent_llm = agent_llm
        import brd.agent
        brd.agent.llm = None
        self.app = create_graph()
        # It's good practice to use unique thread IDs for each test method or even sub-part of a test.
        self.thread_id_counter = 0

    def tearDown(self):
        # Restore original LLM
        import brd.agent
        brd.agent.llm = self.original_agent_llm

    def _get_config(self, test_name="default_test"):
        self.thread_id_counter += 1
        return {"configurable": {"thread_id": f"test-graph-thread-{test_name}-{self.thread_id_counter}"}}

    def test_create_graph_returns_graph(self):
        app = create_graph()
        self.assertIsNotNone(app)
        self.assertTrue(hasattr(app, "invoke"))
        self.assertTrue(hasattr(app, "stream"))

    # Patch generate_initial_brd_sections where it's looked up: in brd.graph's namespace
    @patch('brd.graph.generate_initial_brd_sections')
    def test_graph_invocation_simple_flow(self, mock_generate_brd_sections_in_graph_module):
        mock_brd_content = "Mocked BRD from graph test"
        mock_generate_brd_sections_in_graph_module.return_value = mock_brd_content

        app = create_graph()

        initial_state: AgentState = {
            "userInput": "Test graph input",
            "messages": [],
            "current_brd_content": "",
            "clarification_questions_needed": False,
            "clarification_questions": []
        }
        config = {"configurable": {"thread_id": "test-graph-thread"}}

        final_state = app.invoke(initial_state, config=config)

        # Check if the mocked generate_initial_brd_sections was called correctly.
        # The generate_brd_node in the graph should call it with the user input.
        # The user input is processed by start_node and then passed along.
        # generate_brd_node extracts user_input_for_brd from state['userInput'] or state['messages']
        # In this flow, start_node puts HumanMessage(content="Test graph input") into messages.
        # generate_brd_node should pick this up.
        mock_generate_brd_sections_in_graph_module.assert_called_once_with("Test graph input")

        # Check final state contents
        self.assertEqual(final_state['userInput'], "Test graph input") # userInput should persist

        # Verify messages list
        # 1. HumanMessage from start_node
        # 2. AIMessage from generate_brd_node (containing result from mocked generate_initial_brd_sections)
        self.assertIn(HumanMessage(content="Test graph input"), final_state['messages'])

        found_ai_message = any(
            isinstance(msg, AIMessage) and f"Generated BRD (Partial):\n{mock_brd_content}" in msg.content
            for msg in final_state['messages']
        )
        self.assertTrue(found_ai_message, "AIMessage with mocked BRD content not found or incorrect.")

        self.assertEqual(final_state['current_brd_content'], mock_brd_content)

    # The conceptual clarification flow test remains unchanged as it was already commented out
    # and its patch targets would need similar review if activated.
    # @patch('brd.graph.analyze_input_node')
    # @patch('brd.graph.generate_initial_brd_sections') # This would be the correct target if activated
    # def test_graph_clarification_flow(self, mock_generate_brd, mock_analyze_input):
    #    # ... (rest of the commented out test) ...
    #    pass

# Separate test class for the clarification loop logic
class TestClarificationLoop(unittest.TestCase):
    def setUp(self):
        self.app = create_graph()
        self.thread_id_counter = 0
        # It's crucial that for these tests, the underlying LLM calls within agent functions
        # are mocked, as we are testing graph logic, not LLM responses.
        # We also need to ensure that the llm object in brd.agent is None so agent functions
        # that are *not* mocked will use their "llm is None" path if applicable.
        self.original_agent_llm = agent_llm
        import brd.agent
        brd.agent.llm = None


    def tearDown(self):
        import brd.agent
        brd.agent.llm = self.original_agent_llm

    def _get_config(self, test_name_suffix=""):
        # Ensures a unique thread_id for each logical test run or part of a test run
        # to maintain state isolation if tests were run in parallel or if state leaks.
        # For sequential unittest, simple increment might be okay, but good practice.
        # Using test_name_suffix helps identify threads if debugging logs.
        self.thread_id_counter +=1
        return {"configurable": {"thread_id": f"clarification-loop-{test_name_suffix}-{self.thread_id_counter}"}}

    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_no_questions_needed_straight_to_brd(self, mock_gen_brd, mock_get_questions):
        # Configure mocks
        mock_get_questions.return_value = [] # No questions needed
        mock_gen_brd.return_value = "Mocked BRD Content"

        initial_state: AgentState = {"userInput": "Perfect input", "messages": []}
        config = self._get_config("no_q_straight")

        final_state = self.app.invoke(initial_state, config=config)

        # Assertions
        mock_get_questions.assert_called_once()
        # analyze_input_node calls get_clarification_questions.
        # Check some inputs to get_clarification_questions if necessary.
        # For example, its first argument (current_project_summary) should be "Perfect input"
        # after start_node initializes current_understanding from userInput.
        args_get_questions, _ = mock_get_questions.call_args
        self.assertEqual(args_get_questions[0], "Perfect input") # current_project_summary
        self.assertEqual(args_get_questions[1], "Perfect input") # latest_user_utterance (from userInput in round 0)


        mock_gen_brd.assert_called_once_with("Perfect input") # generate_brd_node uses current_understanding

        self.assertEqual(final_state.get('current_brd_content'), "Mocked BRD Content")
        self.assertFalse(final_state.get('clarification_questions_pending_answer'))
        self.assertEqual(final_state.get('current_clarification_round'), 0) # No clarification rounds executed

        # Check messages: initial user input, and BRD generation message from AIMessage
        self.assertIn(HumanMessage(content="Perfect input"), final_state['messages'])
        found_ai_brd_message = any(
            isinstance(msg, AIMessage) and "Generated BRD (Partial):\nMocked BRD Content" in msg.content
            for msg in final_state['messages']
        )
        self.assertTrue(found_ai_brd_message)

    @patch('brd.graph.refine_project_understanding')
    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_one_round_clarification_then_brd(self, mock_gen_brd, mock_get_questions, mock_refine_understanding):
        config = self._get_config("one_round")

        # --- Turn 1: Agent asks questions ---
        mock_get_questions.return_value = ["Q1: What is the main goal?"]

        initial_state_turn1: AgentState = {"userInput": "Needs details", "messages": []}
        final_state_turn1 = self.app.invoke(initial_state_turn1, config=config)

        # Assertions for Turn 1
        mock_get_questions.assert_called_once_with(current_project_summary="Needs details", latest_user_utterance="Needs details")
        self.assertTrue(final_state_turn1.get('clarification_questions_pending_answer'))
        self.assertEqual(final_state_turn1.get('clarification_questions'), ["Q1: What is the main goal?"])
        self.assertIsInstance(final_state_turn1['messages'][-1], AIMessage)
        self.assertIn("Q1: What is the main goal?", final_state_turn1['messages'][-1].content)
        self.assertEqual(final_state_turn1.get('current_clarification_round'), 0) # Round not incremented until answers processed

        # --- Turn 2: User answers, Agent generates BRD ---
        # Prepare state for Turn 2 based on final_state_turn1
        current_state_turn2 = final_state_turn1.copy() # shallow copy is fine for dict
        current_state_turn2["messages"] = list(final_state_turn1["messages"]) # Ensure messages list is also a copy
        current_state_turn2["messages"].append(HumanMessage(content="A1: The main goal is to improve user engagement."))

        # Configure mocks for Turn 2
        mock_refine_understanding.return_value = "Refined: Needs details. Goal is user engagement."
        # analyze_input is called again after processing answers
        mock_get_questions.reset_mock() # Reset from previous call
        mock_get_questions.return_value = [] # This time, no more questions needed
        mock_gen_brd.return_value = "BRD from Refined Understanding"

        final_state_turn2 = self.app.invoke(current_state_turn2, config=config) # Re-invoke with updated state

        # Assertions for Turn 2
        mock_refine_understanding.assert_called_once_with(
            current_summary="Needs details", # This was current_understanding before refinement
            questions_asked=["Q1: What is the main goal?"],
            user_answers="A1: The main goal is to improve user engagement."
        )
        self.assertEqual(final_state_turn2.get('current_understanding'), "Refined: Needs details. Goal is user engagement.")
        self.assertEqual(final_state_turn2.get('current_clarification_round'), 1) # Incremented after answers

        mock_get_questions.assert_called_once_with(
            current_project_summary="Refined: Needs details. Goal is user engagement.",
            latest_user_utterance="A1: The main goal is to improve user engagement."
        )
        self.assertFalse(final_state_turn2.get('clarification_questions_pending_answer'))

        mock_gen_brd.assert_called_once_with("Refined: Needs details. Goal is user engagement.")
        self.assertEqual(final_state_turn2.get('current_brd_content'), "BRD from Refined Understanding")
        self.assertIn(HumanMessage(content="A1: The main goal is to improve user engagement."), final_state_turn2['messages'])
        found_ai_brd_message_turn2 = any(
            isinstance(msg, AIMessage) and "BRD from Refined Understanding" in msg.content
            for msg in final_state_turn2['messages']
        )
        self.assertTrue(found_ai_brd_message_turn2)

    @patch('brd.graph.refine_project_understanding')
    @patch('brd.graph.get_clarification_questions')
    @patch('brd.graph.generate_initial_brd_sections')
    def test_max_clarification_rounds_reached(self, mock_gen_brd, mock_get_questions, mock_refine_understanding):
        config = self._get_config("max_rounds")
        max_rounds = 3 # Default in AgentState initialization in graph's start_node

        # Mock get_clarification_questions to always return a question
        mock_get_questions.return_value = ["Another question?"]
        # Mock refine_project_understanding to simply append answer
        def _simple_refine(current_summary, questions_asked, user_answers):
            return f"{current_summary} Answer: {user_answers}"
        mock_refine_understanding.side_effect = _simple_refine
        mock_gen_brd.return_value = "BRD after max rounds"

        current_state: AgentState = {"userInput": "Very vague", "messages": []}

        for i in range(max_rounds + 1): # Loop one more time than max_rounds
            print(f"\n--- Test Max Rounds: Iteration {i + 1} ---")
            # Invoke to either ask question or process answer
            current_state = self.app.invoke(current_state, config=config)

            if current_state.get('clarification_questions_pending_answer'):
                self.assertTrue(i < max_rounds, f"Should not ask questions beyond max_rounds. Round {i}")
                # Simulate user providing an answer for the next iteration
                answer = f"Answer for round {i+1}"
                current_state["messages"].append(HumanMessage(content=answer))
            else: # Should happen after max_rounds is reached and processed.
                self.assertTrue(i >= max_rounds, "Should have asked questions until max_rounds.")
                break

        # Final assertions after the loop
        self.assertFalse(current_state.get('clarification_questions_pending_answer'))
        self.assertEqual(current_state.get('current_clarification_round'), max_rounds)

        # Check that get_clarification_questions was called max_rounds + 1 times:
        # 1. Initial call from userInput.
        # 2. After each of the max_rounds answers, before deciding to stop or ask again.
        self.assertEqual(mock_get_questions.call_count, max_rounds + 1)
        # refine_project_understanding is called max_rounds times (once for each answer provided)
        self.assertEqual(mock_refine_understanding.call_count, max_rounds)

        mock_gen_brd.assert_called_once() # Should be called once after limit is effectively hit
        self.assertEqual(current_state.get('current_brd_content'), "BRD after max rounds")

        # Check that the final understanding reflects all answers (simplified by our mock)
        expected_understanding_part = "Answer for round 3" # Check last answer
        self.assertIn(expected_understanding_part, current_state.get('current_understanding',""))


if __name__ == '__main__':
    unittest.main()
