import os
# os import was already there # This comment is now redundant
from brd.graph import create_graph
from brd.agent_state import AgentState
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI # Added for LLM initialization
# openai exceptions for more specific error handling during LLM init
from openai import APIError, RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError
from brd.persistence import save_project # Removed load_project, list_projects as they'll be used via project_manager
# import uuid # No longer needed here, moved to project_manager

# Import new project management functions
from brd.project_manager import (
    get_available_projects_for_cli,
    load_project_core_logic,
    validate_project_name_for_cli,
    sanitize_project_name,
    generate_unique_project_id,
    create_new_project_core_logic
)

# Attempt to load .env file for local development
try:
    import dotenv
    if os.path.exists(".env"):
        dotenv.load_dotenv(override=False)  # Load environment variables from .env file
        if os.getenv("OPENAI_API_KEY"):
            print("INFO: Loaded environment variables from .env file (if present and not already set).")
        else:
            print("INFO: .env file found but contains no relevant environment variables. Relying on globally set environment variables.")
    else:
        print("INFO: No .env file found. Relying on globally set environment variables.")
except ImportError:
    print("INFO: python-dotenv not installed. .env file will not be loaded. Ensure OPENAI_API_KEY and other required variables are set globally if needed.")


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

# handle_load_project and handle_new_project functions are now moved to brd.project_manager.py
# main.py will call them after handling CLI interactions.

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
    api_key_present = bool(os.getenv("OPENAI_API_KEY"))
    if not api_key_present:
        print("\n" + "=" * 60)
        print("CRITICAL WARNING: OPENAI_API_KEY environment variable not found!")
        print("The agent will NOT be able to communicate with the OpenAI API.")
        print("Please set it up immediately. You can create a '.env' file in the")
        print("project root with the following content (replace with your actual key):")
        print("OPENAI_API_KEY='your_actual_api_key'")
        print("=" * 60 + "\n")

        user_choice_continue = get_user_choice(
            "CRITICAL WARNING: OPENAI_API_KEY environment variable not found!\n"
            "The agent will NOT be able to communicate with the OpenAI API.\n"
            "Please set it up immediately. You can create a '.env' file in the\n"
            "project root with the following content (replace with your actual key):\n"
            "OPENAI_API_KEY='your_actual_api_key'\n\n"
            "Do you want to continue without the API key? (Y/N): ",
            ['y', 'n', 'yes', 'no']  # get_user_choice ensures one of these or 'exit'
        )
        if user_choice_continue == 'n' or user_choice_continue == 'no' or user_choice_continue == 'exit':
            print("Exiting. Please configure the OPENAI_API_KEY.")
            return
        print("WARNING: Continuing without API key. Expect errors related to OpenAI API calls.")

    llm_instance: ChatOpenAI | None = None
    if api_key_present:
        print("INFO: OpenAI API Key found. Initializing LLM...")
        try:
            model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
            temperature_str = os.getenv("OPENAI_TEMPERATURE", "0.7")
            temperature = 0.7 # Default
            try:
                temperature = float(temperature_str)
            except ValueError:
                print(f"WARNING: Invalid OPENAI_TEMPERATURE value '{temperature_str}'. Defaulting to 0.7.")

            api_key = os.getenv("OPENAI_API_KEY")
            llm_instance = ChatOpenAI(model=model_name, temperature=temperature, openai_api_key=api_key)
            print(f"INFO: LLM initialized successfully with model: {model_name}, temperature: {temperature}.")
        except AuthenticationError as e:
            print(f"FATAL: OpenAI Authentication Error initializing the LLM: {e}")
            print("Please check your OPENAI_API_KEY. It might be invalid, missing, or expired.")
            print("Exiting.")
            return
        except (APITimeoutError, APIConnectionError) as e:
            error_type = type(e).__name__
            print(f"FATAL: OpenAI Network Error ({error_type}) initializing the LLM: {e}")
            print("Please check your internet connection and OpenAI's service status.")
            print("Exiting.")
            return
        except APIError as e: # Catch other OpenAI API errors during LLM initialization
            error_type = type(e).__name__
            print(f"FATAL: OpenAI API Error ({error_type}) initializing the LLM: {e}")
            print("This could be due to various issues with the API. Check OpenAI's status or your account.")
            print("Exiting.")
            return
        except Exception as e: # Catch other unexpected errors during LLM initialization
            print(f"FATAL: An unexpected error occurred while initializing the LLM: {type(e).__name__} - {e}")
            print("Exiting.")
            return
    else:
        print("INFO: LLM (StrataBRD Pro agent's core) will not be functional as OPENAI_API_KEY is missing.")

    print("\nInitializing StrataBRD Pro Agent Graph...")
    try:
        app = create_graph()
        print("INFO: StrataBRD Pro Agent Graph initialized successfully.")
        print("Welcome! Type 'exit' or 'quit' at any prompt to end the session.")
        # return # Exit after graph initialization for testing purposes
    except Exception as e: # Catch other unexpected errors during graph initialization
        print(f"FATAL: An unexpected error occurred while initializing the agent graph: {type(e).__name__} - {e}")
        print("Please check your setup and dependencies (e.g., LangChain versions).")
        print("Exiting.")
        return

    current_project_id: str | None = None
    current_conversation_state: AgentState | None = None
    # Config now needs to carry the llm_instance
    base_config: dict = {'llm': llm_instance}
    config: dict = {**base_config} # Initialize with llm_instance
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
                project_choices = get_available_projects_for_cli()
                if not project_choices:
                    # Message "No projects available to load." is printed by get_available_projects_for_cli
                    continue # To main menu

                prompt_msg = "Load an existing project? (Enter number, N/no to skip, or 'exit'/'quit'): "
                valid_input_choices = list(project_choices.keys()) + ['n', 'no']
                load_choice = get_user_choice(prompt_msg, valid_input_choices)

                if load_choice in ["exit", "quit", "n", "no"]:
                    if load_choice in ["n", "no"]: print("Skipping project loading.")
                    continue # To main menu

                chosen_project_id = project_choices.get(load_choice)
                if not chosen_project_id: # Should not happen with get_user_choice validation
                     print("Error: Invalid project selection. Returning to main menu.")
                     continue

                proj_id_loaded, conv_state_loaded = load_project_core_logic(chosen_project_id)

                if proj_id_loaded and conv_state_loaded:
                    current_project_id = proj_id_loaded
                    current_conversation_state = conv_state_loaded # This is now an AgentState instance

                    # Update config with thread_id and existing llm_instance
                    current_thread_id = current_conversation_state.thread_id
                    if not current_thread_id:
                        thread_id_counter += 1
                        current_thread_id = f"brd-cli-thread-{current_project_id}-{thread_id_counter}"
                        current_conversation_state.thread_id = current_thread_id # Set on the instance
                        print(f"WARNING: No Thread ID found in loaded project state object. Generated new one: {current_thread_id}")
                    else:
                        print(f"INFO: Using existing Thread ID from loaded project: {current_thread_id}")

                    config = {**base_config, "configurable": {"thread_id": current_thread_id}}


                    if not current_conversation_state.messages and \
                       not current_conversation_state.clarification_questions_pending_answer:
                        print(f"\nProject '{current_project_id}' is loaded. It seems to be at an initial state or requires new input.")
                        user_input_for_loaded = get_user_choice(
                            f"Enter your next query or concept for '{current_project_id}' (or 'exit' to return to menu): "
                        )
                        if user_input_for_loaded == "exit":
                            current_project_id, current_conversation_state = None, None
                            config = {**base_config} # Reset config to base (only llm)
                            continue
                        current_conversation_state.userInput = user_input_for_loaded # Set on the instance
                else:
                    # Error messages are printed by load_project_core_logic
                    print("Returning to main menu.")
                    continue # Loop back to show main menu

            elif choice == 'n':
                new_project_id_final = None
                while True: # Loop for project name input and validation
                    raw_project_input = input(
                        "Enter a name for your new project (leave blank to auto-generate, or type 'exit'/'quit'): "
                    ).strip()

                    if raw_project_input.lower() in ["exit", "quit"]:
                        # Need to break out of the outer loop if user exits here
                        choice = "e" # Signal exit for the outer loop
                        break

                    error_msg, valid_name_or_none = validate_project_name_for_cli(raw_project_input)
                    if error_msg:
                        print(error_msg)
                        continue # Ask for project name again

                    if valid_name_or_none is None: # Auto-generate
                        new_project_id_final = generate_unique_project_id()
                        print(f"INFO: Generated project ID: {new_project_id_final}")
                    else: # User provided a valid name
                        new_project_id_final = sanitize_project_name(valid_name_or_none)
                        print(f"INFO: Using project name: {new_project_id_final}")
                    break # Name validated or generated

                if choice == "e": # User chose to exit during name input
                    print("Exiting StrataBRD Pro Agent. Goodbye!")
                    break

                user_input_concept = get_user_choice(
                    f"Project '{new_project_id_final}'. Enter your initial high-level concept or BRD idea (or 'exit'/'quit'): "
                )
                if user_input_concept == "exit":
                    print("INFO: Exiting new project creation during concept input. Returning to main menu.")
                    continue # To main menu

                thread_id_counter +=1 # Increment for each new project attempt that gets this far
                proj_id_created, conv_state_created, new_config = create_new_project_core_logic(
                    new_project_id_final, user_input_concept, thread_id_counter
                )

                if proj_id_created: # Project creation successful
                    current_project_id = proj_id_created
                    current_conversation_state = conv_state_created
                    # new_config from create_new_project_core_logic already includes thread_id
                    config = {**base_config, **new_config} # Combine with base_config for LLM
                else:
                    # This case should ideally not be reached if create_new_project_core_logic is robust
                    # and main handles exits before calling it.
                    print("Error: Could not create new project. Returning to main menu.")
                    continue

        # --- Interaction with the Agent Graph ---
        if current_project_id and current_conversation_state: # current_conversation_state is AgentState object
            # Determine if we need to prompt for answers or new input
            if current_conversation_state.clarification_questions_pending_answer:
                prompt_msg = "\nPlease provide answers to the agent's questions (or type 'exit' to quit project and return to menu): "
                answers_input = get_user_choice(prompt_msg)
                if answers_input == "exit":
                    print(f"Exiting project '{current_project_id}'. Returning to main menu.")
                    current_project_id, current_conversation_state = None, None
                    config = {**base_config} # Reset config to base (only llm)
                    continue

                current_conversation_state.messages.append(HumanMessage(content=answers_input))
                current_conversation_state.clarification_questions_pending_answer = False # Answers provided
                print("\nProcessing your answers...")
            elif not current_conversation_state.messages and current_conversation_state.userInput:
                # First turn of a new project or loaded project that needs initial processing
                print(f"\nProcessing initial concept for '{current_project_id}'...")
            elif not current_conversation_state.userInput and \
                 not current_conversation_state.messages and \
                 not current_conversation_state.clarification_questions_pending_answer:
                # Loaded an empty or minimal project state, needs initial concept.
                user_input_concept = get_user_choice( # Renamed to avoid conflict
                    f"Project '{current_project_id}' is empty. Enter your high-level concept or BRD idea (or 'exit' to return to menu): "
                )
                if user_input_concept == "exit":
                    print(f"Exiting project '{current_project_id}'. Returning to main menu.")
                    current_project_id, current_conversation_state = None, None
                    config = {**base_config} # Reset config to base (only llm)
                    continue
                current_conversation_state.userInput = user_input_concept # Set on the instance
                print(f"\nProcessing initial concept for '{current_project_id}'...")
            # Else: graph has messages and is not pending questions, it might be continuing a completed task.
            # The user will be prompted *after* this graph.invoke if no questions are asked.

            try:
                # Convert AgentState object to dictionary for the graph
                state_dict = current_conversation_state.to_dict()

                # Invoke the graph with the dictionary state
                final_state_dict = app.invoke(state_dict, config=config)

                # Convert the result back to an AgentState object
                final_state_obj = AgentState(
                    userInput=final_state_dict.get("userInput", ""),
                    messages=final_state_dict.get("messages", []),
                    current_brd_content=final_state_dict.get("current_brd_content", ""),
                    clarification_questions_needed=final_state_dict.get("clarification_questions_needed", False),
                    clarification_questions=final_state_dict.get("clarification_questions", []),
                    current_understanding=final_state_dict.get("current_understanding", ""),
                    max_clarification_rounds=final_state_dict.get("max_clarification_rounds", 3),
                    current_clarification_round=final_state_dict.get("current_clarification_round", 0),
                    clarification_questions_pending_answer=final_state_dict.get("clarification_questions_pending_answer", False),
                    route_condition=final_state_dict.get("route_condition", ""),
                    thread_id=final_state_dict.get("thread_id")
                )

                current_conversation_state = final_state_obj # Persist state for the next iteration

                if current_project_id and current_conversation_state:
                    # Ensure thread_id from config is saved back to state object if it was newly generated for loaded project
                    # This should already be handled if current_conversation_state.thread_id was set.
                    # config_thread_id = config.get("configurable", {}).get("thread_id")
                    # if config_thread_id and current_conversation_state.thread_id != config_thread_id:
                    #    current_conversation_state.thread_id = config_thread_id # Ensure consistency

                    save_project(current_project_id, current_conversation_state.to_dict()) # Convert to dict for saving
                    print(f"Project '{current_project_id}' saved successfully.")

                print("\n--- Conversation Update ---")
                if final_state_obj and final_state_obj.messages:
                    for msg in final_state_obj.messages:
                        if isinstance(msg, HumanMessage): print(f"  YOU: {msg.content}")
                        elif isinstance(msg, AIMessage): print(f"  AGENT: {msg.content}")
                        else: print(f"  {msg.type.upper()}: {str(msg.content if hasattr(msg, 'content') else msg)}")
                else:
                    print("No messages in the current state to display.")

                if final_state_obj.clarification_questions_pending_answer:
                    # Agent asked questions (printed above). Loop will prompt for answers.
                    pass
                else: # Agent phase complete (BRD generated or error occurred and handled by agent)
                    print("\n--- Agent Interaction Complete for this phase ---")
                    brd_content_output = final_state_obj.current_brd_content
                    agent_messages_list = final_state_obj.messages # Renamed to avoid conflict
                    last_ai_message_content = ""
                    if agent_messages_list and isinstance(agent_messages_list[-1], AIMessage):
                        last_ai_message_content = agent_messages_list[-1].content or ""

                    critical_error_detected_in_agent_response = False
                    if "LLM_AUTH_ERROR" in brd_content_output or \
                       "AuthenticationError" in brd_content_output or \
                       "authentication failed" in brd_content_output.lower() or \
                       "LLM_UNAVAILABLE" in brd_content_output or \
                       "LLM_AUTH_ERROR" in last_ai_message_content or \
                       "AuthenticationError" in last_ai_message_content or \
                       "authentication failed" in last_ai_message_content.lower() or \
                       "LLM_UNAVAILABLE" in last_ai_message_content:
                        critical_error_detected_in_agent_response = True

                    if brd_content_output and not ("ERROR:" in brd_content_output or "Error:" in brd_content_output or critical_error_detected_in_agent_response) and not ("LLM_UNAVAILABLE" in brd_content_output) :
                        print("\n--- Generated BRD Content (from current_brd_content) ---")
                        print(brd_content_output)
                        print("--- End of BRD Content ---")
                    elif brd_content_output:
                        print(f"\n--- Notice from Agent ---")
                        print(brd_content_output)
                        print("--- End of Notice ---")
                    elif last_ai_message_content:
                         print(f"\n--- Notice from Agent ---")
                         print(last_ai_message_content)
                         print("--- End of Notice ---")
                    else:
                        print("No final BRD content or specific agent messages were generated in this phase, and no further questions were asked.")

                    if critical_error_detected_in_agent_response:
                        print("CRITICAL: A critical LLM operational error (e.g., authentication, unavailability) was reported by the agent.")
                        print("Please check your API key and LLM service status.")
                        print(f"Returning to main menu. Project '{current_project_id}' session ended.")
                        current_project_id, current_conversation_state = None, None
                        config = {**base_config} # Reset config
                        continue

                    next_action_prompt = (
                        f"Project '{current_project_id}'. Continue with this project (e.g., refine, add details), "
                        "start a New one, Load another, or Exit? (C: Continue, N: New, L: Load, E: Exit): "
                    )
                    next_action = get_user_choice(next_action_prompt, ['c', 'n', 'l', 'e'])

                    if next_action == 'c':
                        user_input_refine = get_user_choice( # Renamed
                            f"Enter your next query, refinement, or additional concept for '{current_project_id}' "
                            "(or type 'exit' to return to main menu): "
                        )
                        if user_input_refine == "exit":
                            print(f"Finished with project '{current_project_id}'. Returning to main menu.")
                            current_project_id, current_conversation_state = None, None
                            config = {**base_config} # Reset config
                            continue
                        current_conversation_state.userInput = user_input_refine
                        current_conversation_state.current_brd_content = "" # Clear old BRD
                        # messages list is handled by add_message or graph itself.
                    elif next_action == 'n' or next_action == 'l':
                        current_project_id, current_conversation_state = None, None
                        config = {**base_config} # Reset config
                    elif next_action == 'e':
                        print("Exiting StrataBRD Pro Agent. Goodbye!")
                        break

            except AuthenticationError as e: # Should ideally be caught by agent's retry, but as a fallback
                print(f"\nCRITICAL ERROR: OpenAI Authentication Failed: {e}") # This might be from LLM calls within graph if not caught by agent
                print("Your OPENAI_API_KEY seems to be invalid or has been revoked.")
                print("Please verify your API key. The current session cannot continue.")
                current_project_id, current_conversation_state = None, None
                config = {**base_config} # Reset to main menu
            except RateLimitError as e: # Should be caught by agent's retry
                print(f"\nERROR: OpenAI Rate Limit Exceeded: {e}")
                print("The agent attempted to contact OpenAI but was rate-limited. This issue might be temporary.")
                print("Please try again later or check your OpenAI account usage limits.")
                # State is preserved, user can decide to retry interaction or exit project
            except (APITimeoutError, APIConnectionError) as e: # Should be caught by agent's retry
                error_type = type(e).__name__
                print(f"\nERROR: OpenAI Network Issue ({error_type}): {e}")
                print("The agent could not connect to OpenAI. This might be a temporary network problem or an OpenAI service issue.")
                print("Please check your internet connection and OpenAI's status page.")
                # State is preserved
            except APIError as e: # General OpenAI API error, possibly not retried or retries failed
                error_type = type(e).__name__
                print(f"\nERROR: An OpenAI API error occurred ({error_type}): {e}")
                print("This may be due to an issue with the request or OpenAI's services. Retries were attempted if applicable.")
                # State is preserved
            except Exception as e:
                import traceback
                print(f"\nUNEXPECTED ERROR: An unexpected error occurred during agent execution: {type(e).__name__} - {e}")
                print("Full error traceback:")
                traceback.print_exc() # Print full traceback for unexpected errors
                print("\nThe agent's internal retry mechanisms for common API issues were active.")
                print("If this persists, it might indicate an internal application error or an unhandled API response.")
                if current_project_id:
                    print(f"Current project state for '{current_project_id}' has been saved (if possible).")
                    print(f"You might be able to resume by loading the project. Resetting to main menu.")
                else:
                    print("Resetting to main menu.")
                current_project_id, current_conversation_state = None, None
                config = {**base_config} # Reset config
                # Loop back to main menu (state is reset to avoid error loops)

if __name__ == "__main__":
    main()
