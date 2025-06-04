import os
from brd.graph import create_graph, AgentState # Assuming AgentState is useful for constructing initial input
from langchain_core.messages import HumanMessage

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
    thread_id_counter = 0
    config = {} # Will be set per new conversation

    while True:
        if current_conversation_state is None:
            # Start of a new BRD idea
            user_input = input("\nEnter your high-level concept or BRD idea: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting StrataBRD Pro Agent.")
                break
            if not user_input.strip():
                print("Please provide some input.")
                continue

            thread_id_counter += 1
            config = {"configurable": {"thread_id": f"brd-cli-thread-{thread_id_counter}"}}
            print(f"\nStarting new conversation with Thread ID: {config['configurable']['thread_id']}")

            current_conversation_state = {
                "userInput": user_input,
                "messages": []
                # Graph's start_node will initialize other fields:
                # current_understanding, max_clarification_rounds, current_clarification_round,
                # clarification_questions_pending_answer, etc.
            }
        else:
            # We are in a clarification cycle, AI has asked questions.
            # The questions would have been printed by the message display logic below in the previous iteration.
            answers_input = input("\nPlease provide answers to the above questions (or type 'exit' to quit): ")
            if answers_input.lower() in ["exit", "quit"]:
                print("Exiting StrataBRD Pro Agent.")
                break

            # Append user's answers as a HumanMessage to the existing state's messages
            current_conversation_state["messages"].append(HumanMessage(content=answers_input))
            print("\nProcessing your answers...")


        try:
            # Invoke the graph with the current state (either initial or with appended answers)
            final_state = app.invoke(current_conversation_state, config=config)
            current_conversation_state = final_state # Persist state for the next iteration

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

        except Exception as e:
            print(f"Error during agent execution: {e}")
            print("This might include errors from the LLM if the API key is missing/invalid.")
            print("Please ensure your OPENAI_API_KEY is correctly set if this is an API error.")
            print("Resetting conversation.")
            current_conversation_state = None # Reset on error to start fresh

if __name__ == "__main__":
    main()
