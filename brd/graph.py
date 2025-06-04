from typing import TypedDict, Annotated, List
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from brd.agent import (
    generate_initial_brd_sections,
    get_clarification_questions,
    refine_project_understanding # New import
)

# --- State Definition ---
class AgentState(TypedDict):
    userInput: str
    messages: Annotated[List[BaseMessage], operator.add]
    current_brd_content: str
    clarification_questions_needed: bool
    clarification_questions: List[str]
    current_understanding: str # Accumulated understanding of the project
    max_clarification_rounds: int
    current_clarification_round: int
    clarification_questions_pending_answer: bool # Flag to indicate if graph expects answers
    route_condition: str # Holds the decision from routing nodes
    # TODO: Add 'clarification_answers: List[str]' or similar

    # Potential future fields:
    # analysis_results: dict
    # confidence_score: float # For overall confidence in the generated BRD
    # current_processing_stage: str # To track which major phase the agent is in

# --- Node Functions ---

def start_node(state: AgentState) -> AgentState:
    """
    Initializes the agent's state.
    - Captures the initial user input into the 'messages' list.
    - Initializes other relevant state fields.
    """
    print("--- Executing Start Node ---")
    if not state.get('messages'): # Initialize messages if it's not there
        state['messages'] = []

    # Ensure initial userInput is added as a HumanMessage
    if state.get('userInput'):
        # Avoid duplicating the input if the graph is re-invoked with the same initial state
        if not state['messages'] or state['messages'][-1].content != state['userInput'] or not isinstance(state['messages'][-1], HumanMessage):
            state['messages'].append(HumanMessage(content=state['userInput']))

    state['current_brd_content'] = ""
    state['clarification_questions_needed'] = False
    state['clarification_questions'] = []
    # New fields for clarification loop
    state['current_understanding'] = state.get('current_understanding', state.get('userInput', '')) # Prioritize existing understanding
    # Max clarification rounds: Use value from input state if provided, otherwise default to 3.
    state['max_clarification_rounds'] = state.get('max_clarification_rounds', 3)
    state['current_clarification_round'] = state.get('current_clarification_round', 0)
    state['clarification_questions_pending_answer'] = state.get('clarification_questions_pending_answer', False)
    state['route_condition'] = "" # Initialize routing condition for this run

    print(f"--- Start Node ---")
    print(f"  Initial userInput: '{state.get('userInput', 'N/A')[:100]}...'")
    print(f"  Initial current_understanding: '{state.get('current_understanding', 'N/A')[:100]}...'")
    print(f"  Max clarification rounds: {state['max_clarification_rounds']}")
    # print(f"  Initial messages count: {len(state.get('messages', []))}") # Less critical for node execution log
    # if state.get('messages'):
    #     for i, msg in enumerate(state['messages']):
    #         print(f"    Msg {i}: Type: {type(msg).__name__}, Content: '{str(msg.content)[:100]}...'")
    return state


def analyze_input_node(state: AgentState) -> AgentState:
    """
    Analyzes current understanding and latest user utterance to determine if clarification is needed.
    Sets 'clarification_questions_needed', 'clarification_questions', and 'route_condition'.
    """
    print(f"\n--- Executing Analyze Input Node (Round {state.get('current_clarification_round', 0)}) ---")

    current_round = state.get('current_clarification_round', 0)
    max_rounds = state.get('max_clarification_rounds', 3)

    print(f"  Current round: {current_round}, Max rounds: {max_rounds}")

    if current_round >= max_rounds:
        print(f"  INFO: Clarification round limit reached. Proceeding to generation.")
        state['clarification_questions_needed'] = False
        state['clarification_questions'] = []
        if not any("Clarification round limit reached" in msg.content for msg in state.get('messages', []) if isinstance(msg, AIMessage)):
             state['messages'].append(AIMessage(content="Clarification round limit reached. Proceeding with BRD generation based on current understanding."))
        state['route_condition'] = "proceed_to_generation"
        return state

    summary_for_questions = state.get('current_understanding', '')
    latest_utterance = ""

    if current_round == 0:
        latest_utterance = state.get('userInput', '')
        print(f"  INFO: First round. Using initial userInput for questions: '{latest_utterance[:100]}...'")
    else:
        if state.get('messages'):
            for message in reversed(state['messages']):
                if isinstance(message, HumanMessage):
                    latest_utterance = message.content
                    print(f"  INFO: Subsequent round. Using last HumanMessage (answers) for questions: '{latest_utterance[:100]}...'")
                    break
        if not latest_utterance:
             print("  WARNING: No distinct latest user utterance (HumanMessage) for clarification analysis after round 0. Using current_understanding.")
             latest_utterance = summary_for_questions

    if not summary_for_questions and not latest_utterance: # Should be rare if userInput is captured
        print("  ERROR: Both current_understanding and latest_utterance are empty. Cannot generate questions.")
        state['clarification_questions_needed'] = False
        state['clarification_questions'] = []
        state['messages'].append(AIMessage(content="INTERNAL ERROR: Missing context to formulate clarification questions."))
        state['route_condition'] = "end_due_to_error"
        return state

    print(f"  INFO: Calling agent to get clarification questions...")
    questions = get_clarification_questions(
        current_project_summary=summary_for_questions,
        latest_user_utterance=latest_utterance
    )
    print(f"  INFO: Agent returned questions: {questions}")

    if questions and any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") or q.startswith("Unparsed response") for q in questions):
        error_detail = questions[0] if questions else "Unknown agent error."
        print(f"  ERROR: Agent returned an error instead of questions: {error_detail}")
        state['messages'].append(AIMessage(content=f"Agent Error: Could not retrieve clarification questions. Details: {error_detail}"))
        state['clarification_questions_needed'] = False
        state['clarification_questions'] = []
        state['route_condition'] = "proceed_to_generation" # Proceed, BRD might reflect this error state
    elif questions:
        print(f"  INFO: Clarification questions generated: {questions}")
        state['clarification_questions_needed'] = True
        state['clarification_questions'] = questions
        state['route_condition'] = "ask_clarification"
    else:
        print("  INFO: No clarification questions needed or returned by LLM.")
        state['clarification_questions_needed'] = False
        state['clarification_questions'] = []
        state['route_condition'] = "proceed_to_generation"
    return state


def generate_brd_node(state: AgentState) -> AgentState:
    """
    Generates BRD content using the current understanding.
    Updates 'current_brd_content' and appends an AIMessage with the BRD or error.
    """
    print("\n--- Executing Generate BRD Node ---")

    user_input_for_brd = state.get('current_understanding', state.get('userInput', ''))
    if not user_input_for_brd:
        print("  WARNING: No input or understanding available for BRD generation. Using placeholder.")
        user_input_for_brd = "No specific input or understanding was available for BRD generation."

    print(f"  Input for BRD generation: '{user_input_for_brd[:100]}...'")
    brd_content = generate_initial_brd_sections(user_input_for_brd)
    state["current_brd_content"] = brd_content

    if "ERROR:" in brd_content or "Error:" in brd_content:
        print(f"  ERROR: Agent returned an error during BRD generation: {brd_content}")
        state["messages"].append(AIMessage(content=f"Could not generate BRD. Details: {brd_content}"))
    else:
        state["messages"].append(AIMessage(content=f"Generated BRD (Partial):\n{brd_content}"))
    return state


def clarification_node(state: AgentState) -> AgentState:
    """
    Presents clarification questions to the user or informs if errors occurred.
    Sets 'clarification_questions_pending_answer' to True if valid questions are asked.
    """
    print(f"\n--- Executing Clarification Node (Round {state.get('current_clarification_round', 0)}) ---")

    current_questions = state.get('clarification_questions', [])
    if not current_questions: # Should be prevented by analyze_input_node's routing
        print("  WARNING: Clarification Node called but no questions in state. Proceeding.")
        ai_message = "I was about to ask for more details, but I don't have any specific questions right now. Let's continue."
        if not any(msg.content == ai_message for msg in state.get('messages', [])): # Avoid duplicate messages
            state['messages'].append(AIMessage(content=ai_message))
        state['clarification_questions_pending_answer'] = False
        return state

    # analyze_input_node is responsible for adding agent errors to messages.
    # This node just checks if the questions are actual questions or error placeholders.
    if any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") or q.startswith("Unparsed response") for q in current_questions):
        print(f"  INFO: Clarification questions list contains error/info messages from agent: {current_questions[0]}")
        # Error message already added by analyze_input_node. Ensure we don't expect an answer.
        state['clarification_questions_pending_answer'] = False
        return state

    questions_formatted = "\n".join([f"{i+1}. {q}" for i, q in enumerate(current_questions)])
    message_to_user = (f"To ensure I create the best possible BRD for you, I have a few clarifying questions:\n"
                       f"{questions_formatted}\nPlease provide your answers.")

    print(f"  Asking valid questions:\n{questions_formatted}")
    state['messages'].append(AIMessage(content=message_to_user))
    state['clarification_questions_pending_answer'] = True
    return state


def process_clarification_answers_node(state: AgentState) -> AgentState:
    """
    Processes user's answers, refines understanding, and increments clarification round.
    Updates 'current_understanding', clears 'clarification_questions',
    and resets 'clarification_questions_pending_answer'.
    """
    print(f"\n--- Executing Process Clarification Answers Node (Round {state.get('current_clarification_round', 0)}) ---")

    user_answers_text = ""
    if state.get('messages') and isinstance(state['messages'][-1], HumanMessage):
        user_answers_text = state['messages'][-1].content
        print(f"  Found user answers: '{user_answers_text[:100]}...'")
    else:
        print("  ERROR: Last message is not HumanMessage or no messages found. Cannot process answers.")
        state['messages'].append(AIMessage(content="It seems I was expecting your answers, but I couldn't find them. This might affect the BRD quality."))
        state['current_clarification_round'] = state.get('current_clarification_round', 0) + 1 # Increment to avoid loop
        state['clarification_questions_pending_answer'] = False
        state['clarification_questions'] = []
        state['route_condition'] = "analyze"
        return state

    questions_that_were_asked = state.get('clarification_questions', [])
    if not questions_that_were_asked: # Should ideally not happen if answers are present
        print("  WARNING: No 'clarification_questions' in state to process answers against. Refining based on general input.")
        current_sum = state.get('current_understanding', state.get('userInput',''))
        new_understanding = refine_project_understanding(
            current_summary=current_sum,
            questions_asked=[], # No specific questions recorded for this refinement
            user_answers=user_answers_text
        )
    else:
        print(f"  Processing answers for questions: {questions_that_were_asked}")
        new_understanding = refine_project_understanding(
            current_summary=state['current_understanding'],
            questions_asked=questions_that_were_asked,
            user_answers=user_answers_text
        )

    if "[LLM_" in new_understanding or "[UNEXPECTED_ERROR" in new_understanding:
        print(f"  ERROR: Refinement of understanding returned an error: {new_understanding}")
        state['messages'].append(AIMessage(content=f"Agent Error: Could not refine project understanding. Details: {new_understanding}"))
        # current_understanding remains the old one in this case
    else:
        print(f"  Old understanding: '{state['current_understanding'][:100]}...'")
        state['current_understanding'] = new_understanding
        print(f"  New understanding: '{state['current_understanding'][:100]}...'")

    state['current_clarification_round'] = state.get('current_clarification_round', 0) + 1
    print(f"  Incremented clarification round to: {state['current_clarification_round']}")

    state['clarification_questions'] = []
    state['clarification_questions_needed'] = False
    state['clarification_questions_pending_answer'] = False
    state['route_condition'] = "analyze"
    return state


def route_after_start_node(state: AgentState) -> AgentState:
    """
    Determines initial routing based on whether answers are pending from a previous session.
    Updates 'route_condition' in the state: "process_answers" or "analyze".
    """
    print(f"\n--- Executing Route After Start Node ---")
    pending_answers = state.get('clarification_questions_pending_answer', False)
    # Check if the last message is Human AND there are messages.
    last_message_is_human = bool(state.get('messages') and isinstance(state['messages'][-1], HumanMessage))

    print(f"  Pending answers flag: {pending_answers}, Last message is Human: {last_message_is_human}")

    if pending_answers and last_message_is_human:
        print("  DECISION: Answers were pending, and last message is Human. Routing to 'process_answers'.")
        state['route_condition'] = "process_answers"
    elif pending_answers and not last_message_is_human:
        print("  WARNING: Answers were pending, but last message is NOT Human. Routing to 'analyze' (may re-ask or end).")
        state['route_condition'] = "analyze"
    else: # No answers pending
        print("  DECISION: No answers pending. Routing to 'analyze'.")
        state['route_condition'] = "analyze"
    return state


def should_ask_for_clarification(state: AgentState) -> str:
    """
    Determines next step after input analysis based on 'route_condition' from `analyze_input_node`.
    Possible outcomes: "ask_clarification", "proceed_to_generation", "end_due_to_error".
    """
    print(f"\n--- Conditional Edge: Evaluating 'route_condition' from analyze_input_node ---")
    route = state.get('route_condition', 'proceed_to_generation') # Default robustly
    print(f"  Route condition from state: '{route}'")

    if route == "ask_clarification":
        print("  DECISION: Routing to 'ask_clarification_questions'.")
        return "ask_clarification"
    elif route == "end_due_to_error":
        print("  DECISION: Routing to END due to error in analyze_input_node.")
        return "end_due_to_error"
    # Default to generation if condition is not explicitly 'ask_clarification' or 'end_due_to_error'
    print("  DECISION: Routing to 'generate_brd'.")
    return "proceed_to_generation"


# --- Graph Definition ---
def create_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("start", start_node)
    workflow.add_node("route_after_start", route_after_start_node) # New routing node
    workflow.add_node("analyze_input", analyze_input_node)
    workflow.add_node("ask_clarification_questions", clarification_node)
    workflow.add_node("process_clarification_answers", process_clarification_answers_node)
    workflow.add_node("generate_brd", generate_brd_node)

    # Set entry point
    workflow.set_entry_point("start")

    # Define edges
    workflow.add_edge("start", "route_after_start") # Start goes to new router

    # Conditional edges from route_after_start
    workflow.add_conditional_edges(
        "route_after_start",
        lambda x: x.get('route_condition', 'analyze'), # Use the condition set in route_after_start_node
        {
            "process_answers": "process_clarification_answers",
            "analyze": "analyze_input"
        }
    )

    # Edge from process_clarification_answers back to analyze_input for re-evaluation
    workflow.add_edge("process_clarification_answers", "analyze_input")

    # Conditional branching after input analysis (remains the same)
    workflow.add_conditional_edges(
        "analyze_input",
        should_ask_for_clarification, # This is the function that returns the key for the map
        {
            "ask_clarification": "ask_clarification_questions",
            "proceed_to_generation": "generate_brd",
            "end_due_to_error": END # New edge for error condition
        }
    )

    # End points of branches
    workflow.add_edge("generate_brd", END)
    # ask_clarification_questions now also correctly goes to END, as the main loop
    # in main.py will handle collecting input and re-invoking the graph.
    workflow.add_edge("ask_clarification_questions", END)
    # No explicit edge needed for "end_due_to_error" as it's handled by the conditional edge above.

    # Compile the graph
    app = workflow.compile()
    return app

if __name__ == '__main__':
    app = create_graph()

    # Test Case 1: Straight to BRD generation (default behavior of analyze_input_node)
    print("\n--- Test Case 1: Straight to BRD Generation ---")
    initial_state_1 = {
        "userInput": "Develop an AI chatbot for customer service that handles returns and FAQs.",
        "messages": []
    }
    # Stream events to see node execution
    for event in app.stream(initial_state_1, {"recursion_limit": 5}):
        print(f"Event: {event}")
        print("---")
    final_state_1 = app.invoke(initial_state_1)
    print(f"Final state 1: {final_state_1.get('messages', [])[-1].content if final_state_1.get('messages') else 'No messages'}")


    # Test Case 2: Conceptual test for clarification path
    # This requires modifying analyze_input_node to trigger clarification,
    # or manually preparing a state that would emerge from such a node.
    print("\n--- Test Case 2: Conceptual Clarification Path ---")
    # To truly test this, we'd mock analyze_input_node or set state like this:
    initial_state_2 = {
        "userInput": "Vague idea.",
        "messages": [HumanMessage(content="Vague idea.")], # Assuming start_node ran
        "clarification_questions_needed": True, # Manually set for testing this path
        "clarification_questions": ["What is the primary goal?", "Who are the target users?"],
        "current_brd_content": ""
    }
    # If analyze_input was the one setting these, it would be called first.
    # Since we are manually setting, we might want to start graph from after analyze_input
    # or ensure analyze_input doesn't overwrite these if called.
    # For this simple if __name__ test, we'll just invoke directly.

    # This test case needs careful setup due to how state is managed.
    # For now, we'll focus on testing max_clarification_rounds override.
    initial_state_2 = {
        "userInput": "Another vague idea.",
        "messages": [],
        "max_clarification_rounds": 1 # Override max rounds
    }
    print("\n--- Test Case 2: Override max_clarification_rounds ---")
    # Stream events to see node execution
    final_state_2 = None
    for event in app.stream(initial_state_2, {"recursion_limit": 10}): # Increased recursion limit for potential loops
        print(f"Event for Test Case 2: {event}")
        if event.get(END): # If an END event is found
            final_state_2 = event[END].get('__values__') # LangGraph structure for final state at END
        print("---")

    if final_state_2:
        print(f"Final state 2 (max_clarification_rounds=1):")
        print(f"  Messages: {[msg.content for msg in final_state_2.get('messages', [])]}")
        print(f"  BRD Content: {final_state_2.get('current_brd_content')}")
        print(f"  Clarification round: {final_state_2.get('current_clarification_round')}")
        print(f"  Max rounds in state: {final_state_2.get('max_clarification_rounds')}")
    else:
        # If END was not reached or state not captured properly (e.g. graph error before END)
        # Try invoking to get the last known state, though this might re-run things.
        # This part is more for debugging the test itself.
        print("Warning: END event not explicitly captured for final state in Test Case 2 stream. Invoking for final snapshot.")
        final_state_2_invoke = app.invoke(initial_state_2, {"recursion_limit": 10})
        if final_state_2_invoke:
             print(f"Final state 2 (invoke) (max_clarification_rounds=1):")
             print(f"  Messages: {[msg.content for msg in final_state_2_invoke.get('messages', [])]}")
             print(f"  BRD Content: {final_state_2_invoke.get('current_brd_content')}")
             print(f"  Clarification round: {final_state_2_invoke.get('current_clarification_round')}")
             print(f"  Max rounds in state: {final_state_2_invoke.get('max_clarification_rounds')}")


    # Test Case 3: Simulating an error from agent (e.g., LLM unavailable)
    print("\n--- Test Case 3: Simulate LLM Error during BRD generation ---")
    # To test this, we need to ensure `generate_initial_brd_sections` returns an error string
    # when OPENAI_API_KEY is missing. This is handled by brd.agent.py.
    # We assume the key is NOT set for this test to be meaningful for error propagation.
    initial_state_3 = {
        "userInput": "Test input for LLM error.",
        "messages": [],
        "current_understanding": "Test input for LLM error." # Ensure this is used
    }
    # Temporarily remove API key for this specific test if it's set in environment
    original_api_key = os.environ.pop("OPENAI_API_KEY", None)

    # Re-create graph with potentially no LLM in agent
    # This is a bit heavy for a unit test, ideally mock agent functions.
    # For now, we rely on the actual agent.py behavior.
    app_for_error_test = create_graph() # Re-compile to reflect no API key if llm is None

    final_state_3 = None
    print("Invoking graph, expecting error message in AIMessage if API key is indeed missing...")
    for event in app_for_error_test.stream(initial_state_3, {"recursion_limit": 5}):
        print(f"Event for Test Case 3: {event}")
        if event.get(END):
            final_state_3 = event[END].get('__values__')
        print("---")

    if final_state_3 and final_state_3.get('messages'):
        last_message = final_state_3['messages'][-1]
        print(f"Last message content from Test Case 3: {last_message.content}")
        if isinstance(last_message, AIMessage) and "ERROR: LLM NOT AVAILABLE" in last_message.content:
            print("SUCCESS: Correctly propagated LLM unavailability error as AIMessage.")
        elif isinstance(last_message, AIMessage) and "Error:" in last_message.content:
             print(f"PARTIAL SUCCESS: AIMessage contains an error, but not the expected LLM_UNAVAILABLE one. Content: {last_message.content}")
        else:
            print(f"FAILURE: Last message was not an AIMessage with the expected error. Message: {last_message}")
    else:
        print("FAILURE: No messages found in final state for Test Case 3 or END not reached.")

    # Restore API key if it was removed
    if original_api_key:
        os.environ["OPENAI_API_KEY"] = original_api_key

    # Re-compile app with original llm state
    app = create_graph()


    print("\n--- Graph Test Suite Complete ---")
