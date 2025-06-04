import json
import os
from datetime import datetime
from typing import List, Dict, Any
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage, FunctionMessage, ToolMessage
)

# Define the path to the directory where projects will be saved.
# This is typically a 'saved_projects' subdirectory within the 'brd' package.
PROJECTS_DIR = os.path.join(os.path.dirname(__file__), "saved_projects")

# Ensure the directory for saved projects exists
# This is done at module load time. If it fails, the module may not load correctly.
# For robustness in functions, we can re-check or try creating it again.
try:
    os.makedirs(PROJECTS_DIR, exist_ok=True)
except OSError as e:
    print(f"WARNING: Could not create projects directory at startup: {PROJECTS_DIR}. Error: {e}")
    # Depending on severity, could raise an exception or set a flag to disable persistence.

def _message_to_dict(message: BaseMessage) -> Dict[str, Any]:
    """
    Converts a LangChain BaseMessage object to a JSON-serializable dictionary.
    Includes specific fields for FunctionMessage and ToolMessage.
    """
    data: Dict[str, Any] = {"type": message.type, "content": message.content}
    if isinstance(message, FunctionMessage) and hasattr(message, 'name'):
        data["name"] = message.name
    if isinstance(message, ToolMessage) and hasattr(message, 'tool_call_id'):
        data["tool_call_id"] = message.tool_call_id
    return data

def _dict_to_message(message_dict: Dict[str, Any]) -> BaseMessage:
    """
    Converts a dictionary (from JSON) back to a LangChain BaseMessage object.
    Handles various message types and includes a fallback for unknown types.
    """
    msg_type = message_dict.get("type")
    content = message_dict.get("content", "") # Default to empty string if content is missing

    if msg_type == "human":
        return HumanMessage(content=content)
    elif msg_type == "ai":
        return AIMessage(content=content)
    elif msg_type == "system":
        return SystemMessage(content=content)
    elif msg_type == "function":
        return FunctionMessage(content=content, name=message_dict.get("name"))
    elif msg_type == "tool":
        return ToolMessage(content=content, tool_call_id=message_dict.get("tool_call_id"))
    else:
        # Fallback for unknown or missing message types
        print(f"WARNING: Unknown or missing message type '{msg_type}' in stored message: {message_dict}. Falling back to AIMessage.")
        return AIMessage(content=f"Unknown message type stored: {str(message_dict)}")

def save_project(project_id: str, agent_state: Dict[str, Any]) -> None:
    """
    Saves the agent's current state to a JSON file named after the project_id.
    The state includes metadata like project_id and last_modified timestamp.
    Messages within the agent_state are serialized from BaseMessage objects to dictionaries.

    Args:
        project_id: The unique identifier for the project.
        agent_state: A dictionary representing the agent's current state.

    Raises:
        IOError: If there's an issue writing the file (e.g. disk full during write).
        OSError: For other OS-level errors including permissions or if paths are invalid.
        Exception: For any other unexpected errors during saving.
    """
    try:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
    except OSError as e:
        # This might happen if permissions changed after module load
        print(f"ERROR: Could not create or access projects directory: {PROJECTS_DIR}. OSError: {e}")
        raise # Re-raise as this is critical for saving

    state_to_save = agent_state.copy()
    state_to_save["project_id"] = project_id
    state_to_save["last_modified"] = datetime.now().isoformat()

    if "messages" in state_to_save and isinstance(state_to_save["messages"], list):
        state_to_save["messages"] = [_message_to_dict(msg) for msg in state_to_save["messages"]]

    final_file_path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    temp_file_path = os.path.join(PROJECTS_DIR, f"{project_id}.json.tmp")

    try:
        # Write to a temporary file first
        with open(temp_file_path, "w") as f:
            json.dump(state_to_save, f, indent=4)

        # If write to temp file is successful, rename it to the final file path
        # os.replace is atomic on most systems and will overwrite the destination.
        os.replace(temp_file_path, final_file_path)
        print(f"INFO: Project '{project_id}' saved successfully to '{final_file_path}'.")

    except (IOError, OSError) as e: # Catches disk full, permission errors, etc.
        error_type = type(e).__name__
        print(f"ERROR: Failed to save project '{project_id}'. {error_type}: {e}")
        # Attempt to clean up the temporary file if it exists
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"INFO: Cleaned up temporary file '{temp_file_path}'.")
            except OSError as cleanup_e:
                print(f"ERROR: Could not clean up temporary file '{temp_file_path}'. Error: {cleanup_e}")
        raise # Re-raise the original error
    except Exception as e: # Catch any other unexpected errors (e.g., json serialization if not caught earlier)
        print(f"ERROR: An unexpected error occurred while saving project '{project_id}'. Error: {type(e).__name__} - {e}")
        # Attempt to clean up the temporary file if it exists
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"INFO: Cleaned up temporary file '{temp_file_path}'.")
            except OSError as cleanup_e:
                print(f"ERROR: Could not clean up temporary file '{temp_file_path}'. Error: {cleanup_e}")
        raise


def load_project(project_id: str) -> Dict[str, Any]:
    """
    Loads an agent's state from a JSON file.
    Deserializes messages from dictionaries back to their respective LangChain BaseMessage objects.

    Args:
        project_id: The unique identifier for the project to load.

    Returns:
        A dictionary representing the loaded agent state.

    Raises:
        FileNotFoundError: If the project file does not exist.
        ValueError: If the project file is corrupted or not valid JSON.
        IOError: If there's an issue reading the file itself (e.g. read error).
        OSError: For other OS-level errors including permissions.
        Exception: For any other unexpected errors during loading.
    """
    file_path = os.path.join(PROJECTS_DIR, f"{project_id}.json")

    # No need for explicit os.path.exists check, open() will raise FileNotFoundError.
    try:
        with open(file_path, "r") as f:
            loaded_state = json.load(f)
        print(f"INFO: Project '{project_id}' loaded successfully from '{file_path}'.")
    except FileNotFoundError:
        print(f"ERROR: Project file not found: {file_path}")
        raise # Re-raise the specific FileNotFoundError
    except json.JSONDecodeError as e:
        error_msg = (f"Error: Failed to decode project file '{file_path}'. "
                     f"The file may be corrupted or not valid JSON. Details: {e}")
        print(f"ERROR: {error_msg}")
        raise ValueError(error_msg) from e # Raise as ValueError for consistent API
    except (IOError, OSError) as e: # Catches permission errors, read errors, etc.
        error_type = type(e).__name__
        print(f"ERROR: Failed to load project '{project_id}' from '{file_path}'. {error_type}: {e}")
        raise # Re-raise the original error
    except Exception as e: # Catch any other unexpected errors
        print(f"ERROR: An unexpected error occurred while loading project '{project_id}'. Error: {type(e).__name__} - {e}")
        raise

    if "messages" in loaded_state and isinstance(loaded_state["messages"], list):
        try:
            loaded_state["messages"] = [_dict_to_message(msg_dict) for msg_dict in loaded_state["messages"]]
        except Exception as e:
            print(f"ERROR: Failed to deserialize one or more messages in project '{project_id}'. "
                  f"Error: {e}. Messages list might be incomplete or contain raw dicts.")
            # Depending on requirements, could raise here or clear messages.
            # For now, allows partial load with a warning.

    return loaded_state


def list_projects() -> List[str]:
    """Lists all saved project IDs."""
    if not os.path.isdir(PROJECTS_DIR): # Ensure it's a directory
        print(f"WARNING: Projects directory '{PROJECTS_DIR}' not found or is not a directory. Cannot list projects.")
        return []

    projects = []
    try:
        for filename in os.listdir(PROJECTS_DIR):
            if filename.endswith(".json") and not filename.endswith(".json.tmp"): # Exclude temp files
                projects.append(filename[:-5]) # Remove .json extension
    except OSError as e:
        print(f"ERROR: Could not list projects in '{PROJECTS_DIR}'. OSError: {e}")
        # Depending on policy, could raise or return empty/partial list. Returning empty for now.
        return []
    return projects
