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
        print("No .env file found or it is empty.")
except ImportError:
    print("python-dotenv not installed, .env file will not be loaded. Ensure OPENAI_API_KEY is set globally if needed.")

def main():
    # Check for OpenAI API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("\nWARNING: OPENAI_API_KEY environment variable not found.")
        print("The agent will likely fail when trying to communicate with the OpenAI API.")
        print("Please set it up, for example, by creating a '.env' file in the project root with:")
        print("OPENAI_API_KEY='your_actual_api_key'\n")
        # Decide if you want to exit or let the user try anyway
        # For now, let's allow them to try, as some graph parts might work without LLM.
        # return

    print("Initializing StrataBRD Pro Agent...")
    try:
        app = create_graph()
        print("StrataBRD Pro Agent initialized.")
        print("Type 'exit' or 'quit' to end the session at any prompt.")
    except Exception as e:
        print(f"Error initializing the agent graph: {e}")
        return

    current_conversation_state: AgentState | None = None
    current_project_id: str | None = None # To store the active project ID
    thread_id_counter = 0 # Keep this for new projects if no ID provided
    config = {} # Will be set per new conversation

    print("\n--- Project Management ---")
    available_projects = list_projects()
    if available_projects:
        print("Available projects:")
        for i, name in enumerate(available_projects):
            print(f"  {i+1}. {name}")
        load_choice = input("Load an existing project? (Enter number or N/no): ").strip().lower()
        if load_choice not in ['n', 'no', '']:
            try:
                project_idx = int(load_choice) - 1
                if 0 <= project_idx < len(available_projects):
                    current_project_id = available_projects[project_idx]
                    print(f"Loading project: {current_project_id}...")
                    loaded_data = load_project(current_project_id)
                    # Ensure all necessary keys for AgentState are present,
                    # providing defaults if they were not saved previously.
                    current_conversation_state = {
                        "userInput": loaded_data.get("userInput", ""),
                        "messages": loaded_data.get("messages", []),
                        "current_brd_content": loaded_data.get("current_brd_content", ""),
                        "clarification_questions_needed": loaded_data.get("clarification_questions_needed", False),
                        "clarification_questions": loaded_data.get("clarification_questions", []),
                        "current_understanding": loaded_data.get("current_understanding", loaded_data.get("userInput", "")), # Default to userInput if not found
                        "max_clarification_rounds": loaded_data.get("max_clarification_rounds", 3),
                        "current_clarification_round": loaded_data.get("current_clarification_round", 0),
                        "clarification_questions_pending_answer": loaded_data.get("clarification_questions_pending_answer", False),
                        "route_condition": loaded_data.get("route_condition", ""), # May not be critical to restore
                    }
                    # Restore thread_id for config if saved, else generate new
                    saved_thread_id = loaded_data.get("thread_id")
                    if saved_thread_id:
                         config = {"configurable": {"thread_id": saved_thread_id}}
                         print(f"Using existing Thread ID: {saved_thread_id}")
                    else:
                        # Generate a new thread_id if not found in loaded data
                        thread_id_counter +=1 # use global counter
                        new_thread_id = f"brd-cli-thread-{current_project_id}-{thread_id_counter}"
                        config = {"configurable": {"thread_id": new_thread_id}}
                        print(f"Generated new Thread ID for loaded project: {new_thread_id}")

                    print(f"Project '{current_project_id}' loaded successfully.")
                    # Display last few messages to give context
                    if current_conversation_state['messages']:
                        print("\n--- Last few messages ---")
                        for msg in current_conversation_state['messages'][-3:]: # Show last 3 messages
                            if isinstance(msg, HumanMessage): print(f"  YOU: {msg.content}")
                            elif isinstance(msg, AIMessage): print(f"  AGENT: {msg.content}")
                            else: print(f"  MESSAGE: {msg.content}") # Fallback for other types
                        if current_conversation_state.get('clarification_questions_pending_answer'):
                            print("AGENT: (Waiting for your answers to the questions above)")
                else:
                    print("Invalid project number.")
            except ValueError:
                print("Invalid input for project selection.")
            except FileNotFoundError:
                print(f"Error: Project file for '{current_project_id}' not found.")
                current_project_id = None # Reset
                current_conversation_state = None
            except Exception as e:
                print(f"Error loading project: {e}")
                current_project_id = None # Reset
                current_conversation_state = None
    print("------------------------\n")

    while True:
        if current_conversation_state is None: # Start of a new BRD idea or continuing a loaded one that needs input
            if not current_project_id: # No project loaded, start a new one
                project_input_name = input("Enter a name for your new project (leave blank to auto-generate): ").strip()
                if not project_input_name:
                    current_project_id = f"project_{uuid.uuid4().hex[:8]}"
                    print(f"Generated project ID: {current_project_id}")
                else:
                    current_project_id = project_input_name.replace(" ", "_").lower()

                user_input = input(f"Project '{current_project_id}'. Enter your high-level concept or BRD idea: ")
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting StrataBRD Pro Agent.")
                    break
                if not user_input.strip():
                    print("Please provide some input.")
                    current_project_id = None # Reset if no input
                    continue

                thread_id_counter += 1
                config = {"configurable": {"thread_id": f"brd-cli-thread-{current_project_id}-{thread_id_counter}"}}
                print(f"\nStarting new conversation for project '{current_project_id}' with Thread ID: {config['configurable']['thread_id']}")
                current_conversation_state = { "userInput": user_input, "messages": [] }
            else: # Project was loaded, but might be waiting for initial input if messages is empty and not pending questions
                if not current_conversation_state.get("messages") and not current_conversation_state.get("clarification_questions_pending_answer"):
                     user_input = input(f"Project '{current_project_id}'. Enter your high-level concept or BRD idea (or type 'exit'): ")
                     if user_input.lower() in ["exit", "quit"]:
                         print("Exiting StrataBRD Pro Agent.")
                         break
                     if not user_input.strip():
                         print("Please provide some input.")
                         # Potentially loop or handle as error, for now, let graph handle empty input if it can
                     current_conversation_state["userInput"] = user_input
                     # messages list is already part of loaded state, start_node will add this as HumanMessage
                else:
                    # This path is taken if a project was loaded and it's in a state
                    # where it's expecting answers (clarification_questions_pending_answer is true)
                    # or has existing messages. The next block handles the 'answers_input'.
                    pass # Proceed to the clarification check


        # The existing 'else' for collecting answers for clarification:
        if current_conversation_state and current_conversation_state.get('clarification_questions_pending_answer'):
            answers_input = input("\nPlease provide answers to the above questions (or type 'exit' to quit): ")
            if answers_input.lower() in ["exit", "quit"]:
                print("Exiting StrataBRD Pro Agent.")
                break
            if not answers_input.strip():
                print("No answers provided. Responding with empty content.")
                # Potentially allow empty answers, or re-prompt. For now, send as is.
            current_conversation_state["messages"].append(HumanMessage(content=answers_input))
            current_conversation_state["clarification_questions_pending_answer"] = False # Assume answers address them for now
            print("\nProcessing your answers...")
        elif current_conversation_state and not current_conversation_state.get("messages") and current_conversation_state.get("userInput"):
            # This handles the case where a new project was created, userInput is set,
            # but it hasn't been added to messages yet. Or a loaded project that had only userInput.
            # The graph's start_node is expected to add the userInput as a HumanMessage.
            # No additional input needed here, proceed to invoke.
            pass
        elif current_conversation_state and not current_conversation_state.get("userInput") and not current_conversation_state.get("messages") and not current_conversation_state.get("clarification_questions_pending_answer"):
            # This case implies a loaded project that is essentially empty and not asking questions.
            # Or a new project that somehow skipped the initial input.
             user_input = input(f"Project '{current_project_id}'. Enter your high-level concept or BRD idea: ")
             if user_input.lower() in ["exit", "quit"]:
                 print("Exiting StrataBRD Pro Agent.")
                 break
             if not user_input.strip():
                 print("Please provide some input.")
                 continue # restart loop
             current_conversation_state["userInput"] = user_input
             # messages list is already part of current_conversation_state (empty or loaded)


        try:
            # Invoke the graph with the current state (either initial or with appended answers)
            final_state = app.invoke(current_conversation_state, config=config)
            current_conversation_state = final_state # Persist state for the next iteration

            if current_project_id and current_conversation_state:
                # Add thread_id to state before saving
                if config.get("configurable", {}).get("thread_id"):
                    current_conversation_state["thread_id"] = config["configurable"]["thread_id"]
                save_project(current_project_id, current_conversation_state)
                print(f"Project '{current_project_id}' saved.")

            # Display all messages from this turn's processing
            # This will include any new AI messages (like questions or the final BRD)
            # and will re-print previous messages if they are part of the state.
            # For a cleaner display, one might only print new messages since last turn.
            # However, printing all helps see the full context if the graph modifies message history.

            print("\n--- Conversation Update ---")
            if final_state and final_state.get('messages'):
                # Determine how many messages were present before this invoke call to print only new ones.
                # This is a bit tricky as current_conversation_state was passed in and mutated.
                # A simpler approach for now is to print all messages in final_state.
                # For a more refined CLI, you'd manage "new" messages more carefully.

                # Let's try to print only the last set of exchanges if possible,
                # by finding the last AIMessage that might have been questions.
                # This is still imperfect. A robust solution needs careful message tracking.

                # Simple print all for now:
                for msg in final_state['messages']:
                    if isinstance(msg, HumanMessage):
                        print(f"  YOU: {msg.content}")
                    else: # Typically AIMessage
                        print(f"  AGENT: {msg.content}")
            else:
                print("No messages in the current state to display.")

            # Check if the agent is waiting for more answers
            if final_state.get('clarification_questions_pending_answer', False):
                # Questions were asked by the agent (and printed above).
                # The loop will continue, prompting for answers.
                pass # Loop continues
            else:
                # Clarification loop is done (or was never needed)
                print("\n--- Agent Interaction Complete for this BRD ---")
                if final_state.get('current_brd_content'):
                    print("\n--- Generated BRD Content (from current_brd_content) ---")
                    print(final_state['current_brd_content'])
                else:
                    print("\nNo final BRD content was generated for this interaction.")

                current_conversation_state = None # Reset for a new BRD idea
                current_project_id = None # Reset project ID for next loop

        except Exception as e:
            print(f"Error during agent execution: {e}")
            print("This might include errors from the LLM if the API key is missing/invalid.")
            print("Please ensure your OPENAI_API_KEY is correctly set if this is an API error.")
            print("Resetting conversation.")
            current_conversation_state = None # Reset on error to start fresh
            current_project_id = None # Also reset project ID

if __name__ == "__main__":
    main()
