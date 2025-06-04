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
        print("Type 'exit' or 'quit' to end the session.")
    except Exception as e:
        print(f"Error initializing the agent graph: {e}")
        return

    while True:
        user_input = input("\nEnter your high-level concept or BRD idea: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting StrataBRD Pro Agent.")
            break

        if not user_input.strip():
            print("Please provide some input.")
            continue

        print("\nProcessing your request...")

        # Prepare initial state for the graph
        # The 'messages' list will be populated by the 'start_node' based on 'userInput'
        initial_state: AgentState = {
            "userInput": user_input,
            "messages": [], # Start_node will populate this from userInput
            "current_brd_content": "",
            "clarification_questions_needed": False,
            "clarification_questions": []
        }

        # It's good practice to provide a configurable map, especially for stream/invoke
        # thread_id helps LangGraph track state across multiple calls for the same "conversation"
        # For a simple CLI like this, a fixed ID or unique one per run is fine.
        config = {"configurable": {"thread_id": "brd-cli-thread"}}

        try:
            # Using invoke to get the final state in one go for this simple CLI
            # stream() could be used for more interactive, step-by-step output.
            final_state = app.invoke(initial_state, config=config)

            print("\n--- Agent Interaction Complete ---")

            # Display the conversation or the final BRD
            # The 'messages' list in AgentState should contain the history.
            # The last AI message often contains the final output or summary.

            if final_state and final_state.get('messages'):
                print("\nConversation History & Output:")
                for msg in final_state['messages']:
                    if isinstance(msg, HumanMessage):
                        print(f"  YOU: {msg.content}")
                    else: # Typically AIMessage
                        print(f"  AGENT: {msg.content}")

                # Additionally, you might want to specifically print the 'current_brd_content'
                # if it's the primary artifact.
                if final_state.get('current_brd_content'):
                    print("\n--- Generated BRD Content (from current_brd_content) ---")
                    print(final_state['current_brd_content'])
                else:
                    print("\nNo specific BRD content found in final_state.current_brd_content.")

            else:
                print("No messages found in the final state.")

        except Exception as e:
            print(f"Error during agent execution: {e}")
            # This might include errors from the LLM if the API key is missing/invalid
            # or other runtime issues in the graph nodes.
            print("Please ensure your OPENAI_API_KEY is correctly set if this is an API error.")

if __name__ == "__main__":
    main()
