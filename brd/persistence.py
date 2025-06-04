import json
import os
from datetime import datetime
from typing import List, Dict, Any, Union # Any/Union for BaseMessage parts
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, FunctionMessage, ToolMessage # Add other relevant types if necessary

# Define the path to the directory where projects will be saved
PROJECTS_DIR = os.path.join(os.path.dirname(__file__), "saved_projects")

# Ensure the directory for saved projects exists
os.makedirs(PROJECTS_DIR, exist_ok=True)

def _message_to_dict(message: BaseMessage) -> Dict[str, Any]:
    """Converts a LangChain message object to a serializable dictionary."""
    data = {"type": message.type, "content": message.content}
    if isinstance(message, FunctionMessage):
        data["name"] = message.name
    if isinstance(message, ToolMessage):
        data["tool_call_id"] = message.tool_call_id
    return data

def _dict_to_message(message_dict: Dict[str, Any]) -> BaseMessage:
    """Converts a dictionary back to a LangChain message object."""
    msg_type = message_dict.get("type")
    content = message_dict.get("content", "")
    if msg_type == "human":
        return HumanMessage(content=content)
    elif msg_type == "ai":
        return AIMessage(content=content)
    elif msg_type == "system":
        return SystemMessage(content=content)
    elif msg_type == "function":
        # Note: FunctionMessage might need 'name' and 'id' depending on usage
        return FunctionMessage(content=content, name=message_dict.get("name"))
    elif msg_type == "tool":
        # Note: ToolMessage might need 'tool_call_id'
        return ToolMessage(content=content, tool_call_id=message_dict.get("tool_call_id"))
    else:
        # Fallback for unknown types or if type is missing
        # Consider logging a warning here
        return AIMessage(content=str(message_dict))

def save_project(project_id: str, agent_state: Dict[str, Any]) -> None:
    """Saves the agent state to a JSON file."""
    os.makedirs(PROJECTS_DIR, exist_ok=True)

    state_copy = agent_state.copy()
    state_copy["project_id"] = project_id
    state_copy["last_modified"] = datetime.now().isoformat()

    if "messages" in state_copy and isinstance(state_copy["messages"], list):
        state_copy["messages"] = [_message_to_dict(msg) for msg in state_copy["messages"]]

    file_path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    with open(file_path, "w") as f:
        json.dump(state_copy, f, indent=4)

def load_project(project_id: str) -> Dict[str, Any]:
    """Loads the agent state from a JSON file."""
    file_path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Project file not found: {file_path}")

    with open(file_path, "r") as f:
        agent_state = json.load(f)

    if "messages" in agent_state and isinstance(agent_state["messages"], list):
        agent_state["messages"] = [_dict_to_message(msg_dict) for msg_dict in agent_state["messages"]]

    return agent_state

def list_projects() -> List[str]:
    """Lists all saved project IDs."""
    if not os.path.exists(PROJECTS_DIR):
        return []

    projects = []
    for filename in os.listdir(PROJECTS_DIR):
        if filename.endswith(".json"):
            projects.append(filename[:-5]) # Remove .json extension
    return projects
