import unittest
from unittest.mock import patch, MagicMock
import os

# Set a dummy API key for tests.
os.environ["OPENAI_API_KEY"] = "test_key_for_graph"

from brd.graph import create_graph, AgentState # AgentState is imported for type hinting if needed
# HumanMessage and AIMessage are used for verifying final_state['messages']
from langchain_core.messages import HumanMessage, AIMessage

class TestGraph(unittest.TestCase):

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

if __name__ == '__main__':
    unittest.main()
