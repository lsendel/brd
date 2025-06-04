import os
from brd.graph import create_graph, AgentState # Assuming AgentState is useful for constructing initial input
from langchain_core.messages import HumanMessage, AIMessage # Added AIMessage for type checking in load
from brd.persistence import save_project, load_project, list_projects
import uuid # For generating unique project IDs if needed

# Attempt to load .env file for local development
try:
    import dotenv
    if dotenv.load_dotenv():
        print("Loaded environment variables from .env file.")
    else:
        print("INFO: No .env file found or it is empty.") # Changed to INFO for consistency
except ImportError:
    print("INFO: python-dotenv not installed, .env file will not be loaded. Ensure OPENAI_API_KEY is set globally if needed.")


def get_user_choice(prompt_message: str, valid_choices: list | None = None) -> str:
    """
    Handles generic user input, exit conditions, and basic validation.
    Returns the user's choice or "exit".
    """
    while True:
        user_input = input(prompt_message).strip().lower()
        if user_input in ["exit", "quit"]:
            return "exit"
        if valid_choices:
            if user_input in valid_choices:
                return user_input
            else:
                print(f"Invalid choice. Please select from {', '.join(valid_choices)} or type 'exit'/'quit'.")
        else: # No specific choices, any non-empty input is fine (after exit check)
            if user_input:
                return user_input
            else:
                print("Input cannot be empty. Please try again or type 'exit'/'quit'.")

def handle_load_project():
    """
    Handles the project loading logic.
    Returns current_project_id, current_conversation_state, or None, None.
    """
    print("\n--- Project Management ---")
    available_projects = list_projects()
    if not available_projects:
        print("No projects available to load.")
        return None, None

    print("Available projects:")
    project_choices = {} # Maps user input (e.g., "1") to project_id
    for i, name in enumerate(available_projects):
        print(f"  {i + 1}. {name}")
        project_choices[str(i + 1)] = name

    prompt_msg = "Load an existing project? (Enter number, N/no to skip, or 'exit'/'quit'): "
    valid_input_choices = list(project_choices.keys()) + ['n', 'no']
    load_choice = get_user_choice(prompt_msg, valid_input_choices)

    if load_choice in ["exit", "quit", "n", "no"]:
        if load_choice in ["n", "no"]:
            print("Skipping project loading.")
        return None, None # User chose to exit or skip

    current_project_id = project_choices.get(load_choice)
    # This check should ideally be redundant if get_user_choice and valid_input_choices work.
    if not current_project_id:
        print("Error: Invalid project selection logic. Please report this bug.")
        return None, None

    print(f"Loading project: '{current_project_id}'...")
    try:
        loaded_data = load_project(current_project_id)
        # Reconstruct AgentState from loaded_data
        current_conversation_state: AgentState = {
            "userInput": loaded_data.get("userInput", ""),
            "messages": loaded_data.get("messages", []), # load_project should handle deserialization
            "current_brd_content": loaded_data.get("current_brd_content", ""),
            "clarification_questions_needed": loaded_data.get("clarification_questions_needed", False),
            "clarification_questions": loaded_data.get("clarification_questions", []),
            "current_understanding": loaded_data.get("current_understanding", loaded_data.get("userInput", "")),
            "max_clarification_rounds": loaded_data.get("max_clarification_rounds", 3), # Default if not in saved
            "current_clarification_round": loaded_data.get("current_clarification_round", 0),
            "clarification_questions_pending_answer": loaded_data.get("clarification_questions_pending_answer", False),
            "route_condition": loaded_data.get("route_condition", ""), # May not be critical to restore
            "thread_id": loaded_data.get("thread_id")
        }
        print(f"Project '{current_project_id}' loaded successfully.")

        if current_conversation_state.get('messages'):
            print("\n--- Historical Messages from Loaded Project (last 5) ---")
            for msg in current_conversation_state['messages'][-5:]:
                if isinstance(msg, HumanMessage):
                    print(f"  YOU: {msg.content}")
                elif isinstance(msg, AIMessage):
                    print(f"  AGENT: {msg.content}")
                else: # Fallback for other types (System, Tool, etc.)
                    print(f"  {msg.type.upper()}: {str(msg.content if hasattr(msg, 'content') else msg)}")
            if current_conversation_state.get('clarification_questions_pending_answer'):
                print("AGENT: (Waiting for your answers to the questions above)")
        return current_project_id, current_conversation_state
    except FileNotFoundError: # Raised by load_project
        print(f"Error: Project file for '{current_project_id}' not found.")
        return None, None
    except ValueError as ve: # Raised by load_project for JSON decode errors
        print(f"Error loading project '{current_project_id}': {ve}")
        return None, None
    except Exception as e: # Catch any other unexpected errors from load_project
        print(f"An unexpected error occurred while loading project '{current_project_id}': {e}")
        return None, None


def handle_new_project(thread_id_counter: int) -> tuple[str | None, AgentState | None, dict | None, int]:
    """
    Handles the new project creation logic.
    Returns current_project_id, current_conversation_state, config, and updated thread_id_counter.
    Returns None, None, None, thread_id_counter if user exits.
    """
    project_input_name = get_user_choice(
        "Enter a name for your new project (leave blank to auto-generate, or 'exit'/'quit'): "
    )
    if project_input_name == "exit":
        return None, None, None, thread_id_counter

    if not project_input_name: # User left it blank
        current_project_id = f"project_{uuid.uuid4().hex[:8]}"
        print(f"Generated project ID: {current_project_id}")
    else:
        # Sanitize the name for use as a filename/ID
        current_project_id = project_input_name.replace(" ", "_").replace("/", "-").lower()

    user_input_prompt = (
        f"Project '{current_project_id}'. Enter your high-level concept or BRD idea (or 'exit'/'quit'): "
    )
    user_input = get_user_choice(user_input_prompt)

    if user_input == "exit":
        print("Exiting new project creation.")
        return None, None, None, thread_id_counter

    thread_id_counter += 1
    new_thread_id = f"brd-cli-thread-{current_project_id}-{thread_id_counter}"
    config = {"configurable": {"thread_id": new_thread_id}}

    print(f"\nStarting new project: '{current_project_id}' with Thread ID: {new_thread_id}")

    current_conversation_state: AgentState = {
        "userInput": user_input,
        "messages": [],
        # Initialize other AgentState fields to defaults for a new project
        "current_brd_content": "",
        "clarification_questions_needed": False,
        "clarification_questions": [],
        "current_understanding": user_input, # Initial understanding is the first input
        "max_clarification_rounds": 3, # Default, can be overridden if passed to graph
        "current_clarification_round": 0,
        "clarification_questions_pending_answer": False,
        "route_condition": "",
        "thread_id": new_thread_id # Store thread_id in state as well
    }
    return current_project_id, current_conversation_state, config, thread_id_counter


def main():
    # Enhanced .env loading message
    if os.path.exists(".env"):
        if dotenv.load_dotenv():
            print("INFO: Loaded environment variables from .env file.")
        else:
            print("INFO: .env file found but it is empty or contains no relevant variables.")
    else:
        print("INFO: No .env file found. Relying on globally set environment variables.")

    # Prominent API Key Check
    if not os.getenv("OPENAI_API_KEY"):
        print("\n" + "=" * 60)
        print("CRITICAL WARNING: OPENAI_API_KEY environment variable not found!")
        print("The agent will NOT be able to communicate with the OpenAI API.")
        print("Please set it up immediately. You can create a '.env' file in the")
        print("project root with the following content (replace with your actual key):")
        print("OPENAI_API_KEY='your_actual_api_key'")
        print("=" * 60 + "\n")

        user_choice_continue = get_user_choice(
            "Proceed without API key? This will likely cause errors. (Y/N): ", ['y', 'n']
        )
        if user_choice_continue == 'n' or user_choice_continue == 'exit':
            print("Exiting. Please configure the OPENAI_API_KEY.")
            return
        print("WARNING: Continuing without API key. Expect errors related to OpenAI API calls.")

    print("\nInitializing StrataBRD Pro Agent...")
    try:
        app = create_graph()
        print("StrataBRD Pro Agent initialized successfully.")
        print("Welcome! Type 'exit' or 'quit' at any prompt to end the session.")
    except Exception as e:
        print(f"FATAL: Error initializing the agent graph: {e}")
        print("Please check your setup and dependencies. Exiting.")
        return

    current_project_id: str | None = None
    current_conversation_state: AgentState | None = None
    config: dict = {} # Ensure config is always a dict
    thread_id_counter: int = 0

    while True:
        if not current_project_id: # No active project, show main menu
            print("\n" + "=" * 30)
            print("Main Menu")
            print("=" * 30)
            choice = get_user_choice(
                "What would you like to do? (N: New Project, L: Load Project, E: Exit): ",
                ['n', 'l', 'e']
            )

            if choice == "e": # "exit" is handled by get_user_choice
                print("Exiting StrataBRD Pro Agent. Goodbye!")
                break

            if choice == 'l':
                project_id_to_load, loaded_state = handle_load_project()
                if project_id_to_load and loaded_state:
                    current_project_id = project_id_to_load
                    current_conversation_state = loaded_state

                    loaded_thread_id = current_conversation_state.get("thread_id")
                    if loaded_thread_id:
                        config = {"configurable": {"thread_id": loaded_thread_id}}
                        print(f"INFO: Using existing Thread ID from loaded project: {loaded_thread_id}")
                    else:
                        thread_id_counter += 1
                        new_thread_id = f"brd-cli-thread-{current_project_id}-{thread_id_counter}"
                        config = {"configurable": {"thread_id": new_thread_id}}
                        current_conversation_state["thread_id"] = new_thread_id # Save to state
                        print(f"WARNING: No Thread ID found in loaded project. Generated new one: {new_thread_id}")

                    if not current_conversation_state.get("messages") and \
                       not current_conversation_state.get("clarification_questions_pending_answer"):
                        print(f"\nProject '{current_project_id}' is loaded. It seems to be at an initial state or requires new input.")
                        user_input = get_user_choice(
                            f"Enter your next query or concept for '{current_project_id}' (or 'exit' to return to menu): "
                        )
                        if user_input == "exit":
                            current_project_id, current_conversation_state, config = None, None, {}
                            continue
                        current_conversation_state["userInput"] = user_input
                else:
                    # Loading was skipped by user ("n", "no") or failed (error message already printed by handle_load_project)
                    print("Returning to main menu.")
                    current_project_id, current_conversation_state, config = None, None, {}
                    continue # Loop back to show main menu

            elif choice == 'n':
                proj_id, conv_state, new_config, thread_id_counter = handle_new_project(thread_id_counter)
                if proj_id: # Project creation successful
                    current_project_id = proj_id
                    current_conversation_state = conv_state
                    config = new_config
                else: # User chose to exit during new project creation
                    print("Exiting StrataBRD Pro Agent. Goodbye!")
                    break

        # --- Interaction with the Agent Graph ---
        if current_project_id and current_conversation_state:
            # Determine if we need to prompt for answers or new input
            if current_conversation_state.get('clarification_questions_pending_answer'):
                prompt_msg = "\nPlease provide answers to the agent's questions (or type 'exit' to quit project and return to menu): "
                answers_input = get_user_choice(prompt_msg)
                if answers_input == "exit":
                    print(f"Exiting project '{current_project_id}'. Returning to main menu.")
                    current_project_id, current_conversation_state, config = None, None, {}
                    continue

                current_conversation_state["messages"].append(HumanMessage(content=answers_input))
                current_conversation_state["clarification_questions_pending_answer"] = False # Answers provided
                print("\nProcessing your answers...")
            elif not current_conversation_state.get("messages") and current_conversation_state.get("userInput"):
                # First turn of a new project or loaded project that needs initial processing
                print(f"\nProcessing initial concept for '{current_project_id}'...")
            elif not current_conversation_state.get("userInput") and \
                 not current_conversation_state.get("messages") and \
                 not current_conversation_state.get("clarification_questions_pending_answer"):
                # Loaded an empty or minimal project state, needs initial concept.
                user_input = get_user_choice(
                    f"Project '{current_project_id}' is empty. Enter your high-level concept or BRD idea (or 'exit' to return to menu): "
                )
                if user_input == "exit":
                    print(f"Exiting project '{current_project_id}'. Returning to main menu.")
                    current_project_id, current_conversation_state, config = None, None, {}
                    continue
                current_conversation_state["userInput"] = user_input
                print(f"\nProcessing initial concept for '{current_project_id}'...")
            # Else: graph has messages and is not pending questions, it might be continuing a completed task.
            # The user will be prompted *after* this graph.invoke if no questions are asked.

            try:
                # Invoke the graph with the current state
                final_state = app.invoke(current_conversation_state, config=config)
                current_conversation_state = final_state # Persist state for the next iteration

                if current_project_id and current_conversation_state:
                    # Ensure thread_id from config is saved back to state (if it was newly generated for loaded project)
                    if config.get("configurable", {}).get("thread_id"):
                         current_conversation_state["thread_id"] = config["configurable"]["thread_id"]
                    save_project(current_project_id, current_conversation_state)
                    print(f"Project '{current_project_id}' saved successfully.")

                print("\n--- Conversation Update ---")
                if final_state and final_state.get('messages'):
                    # Print only new messages since last user input could be complex here.
                    # For now, printing all messages in final_state for simplicity.
                    # User can see the context.
                    for msg in final_state['messages']:
                        if isinstance(msg, HumanMessage): print(f"  YOU: {msg.content}")
                        elif isinstance(msg, AIMessage): print(f"  AGENT: {msg.content}")
                        else: print(f"  {msg.type.upper()}: {str(msg.content if hasattr(msg, 'content') else msg)}")
                else:
                    print("No messages in the current state to display.")

                if final_state.get('clarification_questions_pending_answer', False):
                    # Agent asked questions (printed above). Loop will prompt for answers.
                    pass
                else: # Agent phase complete (BRD generated or error occurred and handled by agent)
                    print("\n--- Agent Interaction Complete for this phase ---")
                    if final_state.get('current_brd_content') and not ("ERROR:" in final_state.get('current_brd_content') or "Error:" in final_state.get('current_brd_content')):
                        print("\n--- Generated BRD Content (from current_brd_content) ---")
                        print(final_state['current_brd_content'])
                        print("--- End of BRD Content ---")
                    elif final_state.get('current_brd_content'): # BRD content might be an error message from agent
                        print(f"\n--- Notice (from current_brd_content) ---")
                        print(final_state['current_brd_content'])
                        print("--- End of Notice ---")
                    else: # No BRD content and no pending questions
                        print("No final BRD content was generated in this phase, and no further questions were asked.")

                    next_action_prompt = (
                        f"Project '{current_project_id}'. Continue with this project (e.g., refine, add details), "
                        "start a New one, Load another, or Exit? (C: Continue, N: New, L: Load, E: Exit): "
                    )
                    next_action = get_user_choice(next_action_prompt, ['c', 'n', 'l', 'e'])

                    if next_action == 'c':
                        user_input_prompt = (
                            f"Enter your next query, refinement, or additional concept for '{current_project_id}' "
                            "(or type 'exit' to return to main menu): "
                        )
                        user_input = get_user_choice(user_input_prompt)
                        if user_input == "exit":
                            print(f"Finished with project '{current_project_id}'. Returning to main menu.")
                            current_project_id, current_conversation_state, config = None, None, {}
                            continue # To main menu
                        current_conversation_state["userInput"] = user_input
                        # Clear old BRD content if user is providing new input to refine/change it
                        current_conversation_state["current_brd_content"] = ""
                        if "messages" not in current_conversation_state: # Should always be there
                            current_conversation_state["messages"] = []
                        # The graph's start_node will add this userInput as a new HumanMessage
                    elif next_action == 'n' or next_action == 'l': # Reset for New or Load
                        current_project_id, current_conversation_state, config = None, None, {}
                    elif next_action == 'e': # Exit
                        print("Exiting StrataBRD Pro Agent. Goodbye!")
                        break

            except Exception as e:
                print(f"\nERROR: An unexpected error occurred during agent execution: {type(e).__name__} - {e}")
                # Consider logging full traceback for debugging: import traceback; traceback.print_exc()
                print("This could be due to API issues (key, rate limits), network problems, or internal errors.")
                print(f"Resetting project '{current_project_id}' and returning to main menu.")
                current_project_id, current_conversation_state, config = None, None, {}
                # Loop back to main menu

if __name__ == "__main__":
    main()
