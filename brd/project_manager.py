# This file will contain project management functions like
# handle_load_project and handle_new_project, moved from main.py.

import os
import uuid
from typing import Tuple, Dict, Any, Optional, List # Added List

from langchain_core.messages import HumanMessage, AIMessage
from .agent_state import AgentState # Import the class-based AgentState
from .persistence import load_project, list_projects # list_projects needed here

# DISALLOWED_CHARS for project name validation
DISALLOWED_CHARS = r'/\:*?"<>|'
DISALLOWED_CHARS_DISPLAY = ", ".join(f"'{c}'" for c in DISALLOWED_CHARS)


def validate_project_name_for_cli(project_name_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Validates a project name input by the user via CLI.
    Allows blank input for auto-generation.
    Returns (error_message, None) if invalid, or (None, project_name_or_None_for_auto) if valid.
    """
    if not project_name_input: # Blank input means auto-generate
        return None, None # No error, signal auto-generation

    # Check for disallowed characters
    if any(char in project_name_input for char in DISALLOWED_CHARS):
        error_msg = f"ERROR: Project name contains disallowed characters. Please avoid: {DISALLOWED_CHARS_DISPLAY}.\nSpaces are allowed and will be replaced with underscores."
        return error_msg, None

    # Check if name is only whitespace (after already checking if it's truly empty)
    if project_name_input.strip() == "":
        error_msg = "ERROR: Project name cannot be only whitespace. Please enter a valid name or leave blank to auto-generate."
        return error_msg, None

    return None, project_name_input # Valid user-provided name (will be sanitized by caller)

def sanitize_project_name(project_name: str) -> str:
    """
    Sanitizes a project name by replacing spaces with underscores and converting to lowercase.
    Assumes project_name itself is not empty or only whitespace at this point.
    """
    return project_name.replace(" ", "_").lower()

def generate_unique_project_id() -> str:
    """
    Generates a unique project ID.
    """
    return f"project_{uuid.uuid4().hex[:8]}"


def get_available_projects_for_cli() -> Dict[str, str]:
    """
    Lists available projects for CLI, prints them, and returns a choices dictionary.
    """
    # This print statement is CLI specific, consider if it should be here or in main.py
    # For this refactoring, keeping it here to closely mirror original functionality.
    print("\n--- Project Management ---")
    available_persistence_projects = list_projects() # from .persistence
    if not available_persistence_projects:
        print("No projects available to load.")
        return {}

    print("Available projects:")
    project_choices = {} # Maps user input (e.g., "1") to project_id
    for i, name in enumerate(available_persistence_projects):
        print(f"  {i + 1}. {name}")
        project_choices[str(i + 1)] = name
    return project_choices


def load_project_core_logic(project_id: str) -> Tuple[Optional[str], Optional[AgentState]]:
    """
    Core logic for loading a project, assuming project_id is already chosen and valid.
    Handles file operations and state reconstruction.
    """
    print(f"Loading project: '{project_id}'...") # CLI feedback
    try:
        loaded_data = load_project(project_id) # from .persistence

        # Instantiate AgentState class
        # Ensure messages from loaded_data are already BaseMessage instances due to _dict_to_message in persistence.py
        current_conversation_state = AgentState(
            userInput=loaded_data.get("userInput", ""),
            messages=loaded_data.get("messages", []),
            current_brd_content=loaded_data.get("current_brd_content", ""),
            clarification_questions_needed=loaded_data.get("clarification_questions_needed", False),
            clarification_questions=loaded_data.get("clarification_questions", []),
            current_understanding=loaded_data.get("current_understanding", loaded_data.get("userInput", "")),
            max_clarification_rounds=loaded_data.get("max_clarification_rounds", 3),
            current_clarification_round=loaded_data.get("current_clarification_round", 0),
            clarification_questions_pending_answer=loaded_data.get("clarification_questions_pending_answer", False),
            route_condition=loaded_data.get("route_condition", ""),
            thread_id=loaded_data.get("thread_id") # Pass thread_id to constructor
        )

        print(f"Project '{project_id}' loaded successfully.") # CLI feedback

        if current_conversation_state.messages: # Accessing class attribute
            print("\n--- Historical Messages from Loaded Project (last 5) ---")
            for msg in current_conversation_state.messages[-5:]:
                if isinstance(msg, HumanMessage):
                    print(f"  YOU: {msg.content}")
                elif isinstance(msg, AIMessage):
                    print(f"  AGENT: {msg.content}")
                else: # Fallback for other types (System, Tool, etc.)
                    print(f"  {msg.type.upper()}: {str(msg.content if hasattr(msg, 'content') else msg)}")
            if current_conversation_state.clarification_questions_pending_answer: # Accessing class attribute
                print("AGENT: (Waiting for your answers to the questions above)")
        return project_id, current_conversation_state
    except FileNotFoundError:
        print(f"Error: Project file for '{project_id}' not found.") # CLI feedback
        return None, None
    except ValueError as ve:
        print(f"ERROR: Project file '{project_id}' seems corrupted or not in the expected format: {ve}") # CLI feedback
        return None, None
    except PermissionError:
        print(f"ERROR: Permission denied when trying to read project file for '{project_id}'. Please check file permissions.") # CLI feedback
        return None, None
    except Exception as e: # Catch any other unexpected errors from load_project
        print(f"ERROR: An unexpected issue occurred while loading project '{project_id}': {type(e).__name__} - {e}") # CLI feedback
        return None, None


def create_new_project_core_logic(
    project_id: str, # Sanitized name or generated ID
    initial_user_input: str,
    thread_id_counter: int # Managed by main.py
) -> Tuple[str, AgentState, Dict[str, Any]]:
    """
    Core logic for creating a new project state.
    Assumes project_id is finalized and initial_user_input is provided.
    """
    # thread_id_counter is passed from main to ensure it's unique across sessions if main is restarted
    # but keeps running for the same python process execution.
    new_thread_id = f"brd-cli-thread-{project_id}-{thread_id_counter}"
    config = {"configurable": {"thread_id": new_thread_id}}

    # CLI feedback, consider moving to main.py if this module should be UI agnostic
    print(f"\nStarting new project: '{project_id}' with Thread ID: {new_thread_id}")

    # Instantiate AgentState class
    current_conversation_state = AgentState(
        userInput=initial_user_input,
        thread_id=new_thread_id # Pass thread_id to constructor
        # Other fields will use defaults from AgentState __init__
    )
    return project_id, current_conversation_state, config
