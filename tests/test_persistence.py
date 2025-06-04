import unittest
import os
import json
import shutil
from datetime import datetime
from unittest.mock import patch

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, FunctionMessage, ToolMessage

# Adjust import path if brd is not directly in PYTHONPATH
# This assumes 'brd' is a package accessible from where tests are run
# or that PYTHONPATH is set up appropriately.
# If run_tests.sh runs from project root, 'brd.persistence' should be findable.
from brd.persistence import save_project, load_project, list_projects, _message_to_dict, _dict_to_message

# Define a test-specific directory for saved projects
# Using abspath to ensure it's correctly resolved relative to this test file.
TEST_DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))
TEST_PROJECTS_DIR = os.path.join(TEST_DATA_ROOT, "test_saved_projects")


class TestPersistence(unittest.TestCase):

    def setUp(self):
        """
        Set up for each test method.
        This method patches the PROJECTS_DIR in brd.persistence to use a temporary
        test directory. It also creates this directory.
        """
        # Ensure the base test_data directory exists, then our specific one
        os.makedirs(TEST_DATA_ROOT, exist_ok=True)

        # Patch brd.persistence.PROJECTS_DIR to point to our test directory
        # The patch should be applied where the object is looked up,
        # which is brd.persistence.PROJECTS_DIR
        self.mock_projects_dir_patch = patch('brd.persistence.PROJECTS_DIR', TEST_PROJECTS_DIR)
        self.mocked_projects_dir = self.mock_projects_dir_patch.start()

        # Explicitly create the test projects directory *after* patching,
        # as functions like save_project might rely on it.
        # persistence.py's top-level os.makedirs(PROJECTS_DIR, exist_ok=True) will use the patched value
        # if it runs after the patch is active (e.g. during import if tests are structured that way,
        # or if the functions themselves call it).
        # To be safe, we create it here. save_project also calls it.
        os.makedirs(self.mocked_projects_dir, exist_ok=True)


    def tearDown(self):
        """
        Clean up after each test method.
        This method stops the patch and removes the temporary test directory.
        """
        self.mock_projects_dir_patch.stop()
        # Remove the entire test_data directory structure if it's safe to do so
        # For now, just remove the specific test_saved_projects directory
        if os.path.exists(TEST_PROJECTS_DIR):
            shutil.rmtree(TEST_PROJECTS_DIR)
        # If TEST_DATA_ROOT becomes empty, it could also be removed, but be careful.

    def test_01_save_and_load_project(self):
        test_project_id = "test_save_load"
        sample_state = {
            "userInput": "Test input",
            "messages": [
                HumanMessage(content="Hello agent"),
                AIMessage(content="Hello user"),
                SystemMessage(content="System init"),
                FunctionMessage(name="get_weather_test01", content='{"location": "Paris", "unit": "celsius"}'),
                ToolMessage(tool_call_id="call_test01_abc", content="Weather is 20C.")
            ],
            "current_brd_content": "BRD content here",
            "current_understanding": "Understood",
            "clarification_questions_needed": False,
            "clarification_questions": [],
            "max_clarification_rounds": 3,
            "current_clarification_round": 1,
            "clarification_questions_pending_answer": False,
            "thread_id": "thread-123"
        }

        save_project(test_project_id, sample_state)

        # Verify file was created
        expected_file_path = os.path.join(TEST_PROJECTS_DIR, f"{test_project_id}.json")
        self.assertTrue(os.path.exists(expected_file_path))

        loaded_state = load_project(test_project_id)

        self.assertEqual(loaded_state["userInput"], sample_state["userInput"])
        self.assertEqual(loaded_state["current_brd_content"], sample_state["current_brd_content"])
        self.assertEqual(loaded_state["thread_id"], sample_state["thread_id"])
        self.assertEqual(loaded_state.get("project_id"), test_project_id)
        self.assertIsNotNone(loaded_state.get("last_modified"))
        self.assertIsInstance(loaded_state.get("last_modified"), str)

        self.assertEqual(len(loaded_state["messages"]), len(sample_state["messages"]))

        # HumanMessage
        self.assertIsInstance(loaded_state["messages"][0], HumanMessage)
        self.assertEqual(loaded_state["messages"][0].content, sample_state["messages"][0].content)
        self.assertEqual(loaded_state["messages"][0].type, "human")

        # AIMessage
        self.assertIsInstance(loaded_state["messages"][1], AIMessage)
        self.assertEqual(loaded_state["messages"][1].content, sample_state["messages"][1].content)
        self.assertEqual(loaded_state["messages"][1].type, "ai")

        # SystemMessage
        self.assertIsInstance(loaded_state["messages"][2], SystemMessage)
        self.assertEqual(loaded_state["messages"][2].content, sample_state["messages"][2].content)
        self.assertEqual(loaded_state["messages"][2].type, "system")

        # FunctionMessage
        loaded_fm = loaded_state["messages"][3]
        original_fm = sample_state["messages"][3]
        self.assertIsInstance(loaded_fm, FunctionMessage)
        self.assertEqual(loaded_fm.content, original_fm.content)
        self.assertEqual(loaded_fm.name, original_fm.name)
        self.assertEqual(loaded_fm.type, "function")

        # ToolMessage
        loaded_tm = loaded_state["messages"][4]
        original_tm = sample_state["messages"][4]
        self.assertIsInstance(loaded_tm, ToolMessage)
        self.assertEqual(loaded_tm.content, original_tm.content)
        self.assertEqual(loaded_tm.tool_call_id, original_tm.tool_call_id)
        self.assertEqual(loaded_tm.type, "tool")

    def test_02_list_projects(self):
        project_id1 = "list_test1"
        project_id2 = "list_test2"

        save_project(project_id1, {"userInput": "p1", "messages": []}) # messages is required by current load_project
        save_project(project_id2, {"userInput": "p2", "messages": []})

        projects = list_projects()

        self.assertEqual(len(projects), 2)
        self.assertIn(project_id1, projects)
        self.assertIn(project_id2, projects)

    def test_03_load_nonexistent_project(self):
        with self.assertRaises(FileNotFoundError):
            load_project("nonexistent_id")

    def test_04_save_project_creates_directory(self):
        # tearDown removes TEST_PROJECTS_DIR. setUp re-creates it.
        # To test save_project's own directory creation, we need to ensure
        # the directory *doesn't* exist right before the call.
        # The current setUp/tearDown manage TEST_PROJECTS_DIR itself.
        # save_project uses os.makedirs(PROJECTS_DIR, exist_ok=True),
        # so this test ensures that if PROJECTS_DIR (mocked to TEST_PROJECTS_DIR)
        # somehow got deleted, save_project would recreate it.

        if os.path.exists(TEST_PROJECTS_DIR):
            shutil.rmtree(TEST_PROJECTS_DIR)

        # Sanity check: directory should not exist now
        self.assertFalse(os.path.exists(TEST_PROJECTS_DIR))

        project_id = "proj_creates_dir"
        save_project(project_id, {"userInput": "test", "messages": []})

        self.assertTrue(os.path.exists(TEST_PROJECTS_DIR))
        self.assertTrue(os.path.exists(os.path.join(TEST_PROJECTS_DIR, f"{project_id}.json")))

    def test_05_message_serialization_deserialization_all_types(self):
        """Test serialization and deserialization of all supported message types."""
        messages = [
            HumanMessage(content="Human input"),
            AIMessage(content="AI response"),
            SystemMessage(content="System instruction"),
            FunctionMessage(content="Function result", name="my_function"),
            ToolMessage(content="Tool output", tool_call_id="tool_123")
        ]

        serialized_messages = [_message_to_dict(msg) for msg in messages]

        # Check basic serialization structure
        for i, ser_msg in enumerate(serialized_messages):
            self.assertEqual(ser_msg["type"], messages[i].type)
            self.assertEqual(ser_msg["content"], messages[i].content)
            if isinstance(messages[i], FunctionMessage):
                self.assertEqual(ser_msg.get("name"), messages[i].name)
            if isinstance(messages[i], ToolMessage):
                self.assertEqual(ser_msg.get("tool_call_id"), messages[i].tool_call_id)

        deserialized_messages = [_dict_to_message(s_msg) for s_msg in serialized_messages]

        for i, de_msg in enumerate(deserialized_messages):
            self.assertIsInstance(de_msg, BaseMessage)
            self.assertEqual(de_msg.type, messages[i].type)
            self.assertEqual(de_msg.content, messages[i].content)
            if isinstance(messages[i], FunctionMessage):
                self.assertEqual(de_msg.name, messages[i].name)
            if isinstance(messages[i], ToolMessage):
                self.assertEqual(de_msg.tool_call_id, messages[i].tool_call_id)

    def test_06_empty_project_list(self):
        """Test listing projects when the projects directory is empty or not present."""
        # Ensure the directory is clean or non-existent initially for this test
        if os.path.exists(TEST_PROJECTS_DIR):
            shutil.rmtree(TEST_PROJECTS_DIR)
        # list_projects should handle non-existent directory by returning []
        # as per its implementation (if not os.path.exists(PROJECTS_DIR): return [])
        self.assertEqual(list_projects(), [])

        # Now test with an empty directory
        os.makedirs(TEST_PROJECTS_DIR, exist_ok=True)
        self.assertEqual(list_projects(), [])

    def test_07_load_corrupted_json_project(self):
        """Test loading a project from a corrupted (invalid JSON) file."""
        project_id = "corrupted_json"
        file_path = os.path.join(TEST_PROJECTS_DIR, f"{project_id}.json")

        # Create a corrupted JSON file
        with open(file_path, "w") as f:
            f.write("{'name': 'test', 'messages': [") # Invalid JSON syntax

        with self.assertRaises(ValueError) as context:
            load_project(project_id)

        self.assertTrue("Failed to decode project file" in str(context.exception))
        self.assertTrue("corrupted or not valid JSON" in str(context.exception))

    @patch('builtins.print') # To capture print statements (warnings)
    def test_08_dict_to_message_unknown_type(self, mock_print):
        """Test _dict_to_message with an unknown message type."""
        unknown_message_dict = {"type": "future_message_type", "content": "Some future content"}

        message = _dict_to_message(unknown_message_dict)

        self.assertIsInstance(message, AIMessage) # Should fallback to AIMessage
        self.assertEqual(message.content, f"Unknown message type stored: {str(unknown_message_dict)}")

        # Check if the warning was printed
        mock_print.assert_any_call(f"WARNING: Unknown or missing message type 'future_message_type' in stored message: {unknown_message_dict}. Falling back to AIMessage.")

    def test_09_save_io_error(self):
        """Test save_project under an IOError condition."""
        project_id = "save_io_error_test"
        sample_state = {"userInput": "test", "messages": []}

        # Patch open to raise IOError on write
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            mock_file.side_effect = IOError("Disk full")
            with self.assertRaises(IOError) as context:
                save_project(project_id, sample_state)
            self.assertIn("Disk full", str(context.exception))

    def test_10_load_io_error(self):
        """Test load_project under an IOError condition (not FileNotFoundError)."""
        project_id = "load_io_error_test"
        # First, save a valid project so the file exists for the load attempt
        save_project(project_id, {"userInput": "data", "messages": []})

        # Patch open to raise IOError on read after the file existence check
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            mock_file.side_effect = IOError("Permission denied")
            with self.assertRaises(IOError) as context:
                load_project(project_id)
            self.assertIn("Permission denied", str(context.exception))


if __name__ == '__main__':
    unittest.main()
