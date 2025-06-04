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
    state['current_understanding'] = state.get('userInput', '') # Initialize with the first input
    state['max_clarification_rounds'] = 3
    state['current_clarification_round'] = 0
    state['clarification_questions_pending_answer'] = False # Initialize flag
    state['route_condition'] = "" # Initialize routing condition
    print(f"Initial state after start_node: {state}")
    return state

def analyze_input_node(state: AgentState) -> AgentState:
    """
    Analyzes the current understanding and latest user utterance to determine
    if clarification questions are needed.
    """
    print("--- Executing Analyze Input Node ---")

    current_round = state.get('current_clarification_round', 0)
    max_rounds = state.get('max_clarification_rounds', 3)

    if current_round >= max_rounds:
        print(f"Clarification round limit reached ({current_round}/{max_rounds}). Proceeding without further questions.")
        state['clarification_questions_needed'] = False
        state['clarification_questions'] = []
        # Optionally, add an AIMessage indicating this
        # state['messages'].append(AIMessage(content="Clarification round limit reached. Proceeding with BRD generation based on current understanding."))
        return state

    summary_for_questions = state.get('current_understanding', '')
    latest_utterance = ""

    if current_round == 0:
        latest_utterance = state.get('userInput', '')
    else:
        # Find the last HumanMessage for subsequent rounds
        if state.get('messages'):
            for message in reversed(state['messages']):
                if isinstance(message, HumanMessage):
                    # Avoid re-using the very first userInput if it's the only human message and round > 0
                    # This logic might need refinement based on how answers are added to messages.
                    # For now, assume any HumanMessage after round 0 is an answer.
                    if message.content != state.get('userInput') or len(state['messages']) > 1 : # ensure it's not the initial input again unless it's the only message
                        latest_utterance = message.content
                        break
        if not latest_utterance: # Fallback if no suitable human message found (should be rare)
             print("Warning: No distinct latest user utterance found for clarification analysis after round 0. Using current understanding as utterance.")
             latest_utterance = summary_for_questions


    print(f"Calling get_clarification_questions with (Round {current_round}):")
    print(f"  Summary for questions: '{summary_for_questions[:200]}...'")
    print(f"  Latest utterance: '{latest_utterance[:200]}...'")

    questions = get_clarification_questions(
        current_project_summary=summary_for_questions,
        latest_user_utterance=latest_utterance
    )

    print(f"Received questions from LLM: {questions}")

    if questions:
        state['clarification_questions_needed'] = True
        state['clarification_questions'] = questions
        # current_clarification_round is incremented by the node that processes answers or by a dedicated update node.
        # For now, if questions are asked, we assume the graph will route to ask them.
        # The actual increment should happen *after* questions are successfully asked and answers are received.
    else:
        state['clarification_questions_needed'] = False
        state['clarification_questions'] = []

    print(f"State after analyze_input_node: {state}")
    return state

def generate_brd_node(state: AgentState) -> AgentState:
    """
    Generates the BRD content using the agent's core logic.
    This node is called when the input is deemed sufficient, either initially
    or after a clarification cycle.
    """
    print("--- Executing Generate BRD Node ---")

    # Determine the most relevant input for BRD generation.
    # Prioritize 'current_understanding', then 'userInput', then a default.
    user_input_for_brd = state.get('current_understanding')
    if not user_input_for_brd: # Check if None or empty string
        user_input_for_brd = state.get('userInput')
    if not user_input_for_brd: # Check again if still None or empty
        user_input_for_brd = "Default fallback: No specific input or understanding provided for BRD generation."

    print(f"Input for BRD generation (from current_understanding or fallback): {user_input_for_brd[:100]}...")
    brd_content = generate_initial_brd_sections(user_input_for_brd)
    state["current_brd_content"] = brd_content
    state["messages"].append(AIMessage(content=f"Generated BRD (Partial):\n{brd_content}"))
    print(f"State after generate_brd_node: {state}")
    return state

def clarification_node(state: AgentState) -> AgentState:
    """
    Formats and presents clarification questions to the user.
    In a full loop, the graph would then wait for user's answers.
    """
    print("--- Executing Clarification Node ---")
    if not state.get('clarification_questions'):
        # This case should ideally not be reached if conditional logic is correct
        state['messages'].append(AIMessage(content="I need more details, but no specific questions were formulated."))
        return state

    questions_formatted = "\n".join([f"{i+1}. {q}" for i, q in enumerate(state['clarification_questions'])])
    message_to_user = f"To ensure I create the best possible BRD for you, I have a few clarifying questions:\n{questions_formatted}\nPlease provide your answers."
    state['messages'].append(AIMessage(content=message_to_user))

    # In a real clarification loop:
    # 1. The graph would effectively pause here, awaiting the next HumanMessage.
    # 2. The main.py (or calling application) would collect user's answers and reinvoke the graph
    #    with the new HumanMessage appended.
    # 3. An edge would lead from here to a new node, e.g., 'process_clarification_answers_node'.
    state['clarification_questions_pending_answer'] = True # Set flag before ending
    print(f"State after clarification_node: {state}")
    return state

def process_clarification_answers_node(state: AgentState) -> AgentState:
    """
    Processes the user's answers to clarification questions and refines
    the project understanding.
    """
    print("--- Executing Process Clarification Answers Node ---")

    user_answers_text = ""
    if state.get('messages') and isinstance(state['messages'][-1], HumanMessage):
        user_answers_text = state['messages'][-1].content
    else:
        print("Warning: Last message is not a HumanMessage or no messages found. Cannot process answers.")
        # Keep current understanding and increment round to avoid getting stuck if something is wrong.
        state['current_clarification_round'] = state.get('current_clarification_round', 0) + 1
        state['clarification_questions'] = [] # Clear old questions
        state['clarification_questions_needed'] = False # Will be re-evaluated
        return state

    questions_just_answered = state.get('clarification_questions', [])
    if not questions_just_answered:
        print("Warning: No clarification questions found in state to process answers against.")
        # This might happen if graph is entered incorrectly.
        # Increment round and clear questions.
        state['current_clarification_round'] = state.get('current_clarification_round', 0) + 1
        state['clarification_questions'] = []
        state['clarification_questions_needed'] = False
        return state

    print(f"Processing answers: '{user_answers_text[:200]}...' for questions: {questions_just_answered}")

    new_understanding = refine_project_understanding(
        current_summary=state['current_understanding'],
        questions_asked=questions_just_answered,
        user_answers=user_answers_text
    )
    print(f"Old understanding: '{state['current_understanding'][:200]}...'")
    state['current_understanding'] = new_understanding
    print(f"New understanding: '{state['current_understanding'][:200]}...'")

    state['current_clarification_round'] = state.get('current_clarification_round', 0) + 1
    state['clarification_questions'] = [] # Clear the questions that were just answered
    state['clarification_questions_needed'] = False # Will be re-evaluated by analyze_input
    state['clarification_questions_pending_answer'] = False # Reset flag

    print(f"State after process_clarification_answers_node: {state}")
    return state

# --- Routing and Conditional Edges ---

def route_after_start_node(state: AgentState) -> AgentState:
    """
    Determines the initial routing based on whether clarification answers are pending.
    This node updates 'route_condition' in the state.
    """
    print("--- Executing Route After Start Node ---")
    if state.get('clarification_questions_pending_answer', False):
        # Check if the last message is indeed a HumanMessage (i.e., an answer)
        if state.get('messages') and isinstance(state['messages'][-1], HumanMessage):
            print("Decision: Answers pending and last message is Human. Routing to 'process_answers'.")
            state['route_condition'] = "process_answers"
        else:
            # This case should ideally not happen if main.py logic is correct (sends answers as HumanMessage)
            # Or if it's the very first run after questions were asked but graph re-invoked without new human message
            print("Warning: Answers were pending, but last message is not Human. Defaulting to 'analyze'.")
            state['route_condition'] = "analyze"
    else:
        print("Decision: No answers pending. Routing to 'analyze'.")
        state['route_condition'] = "analyze"

    print(f"State after route_after_start_node: {state}")
    return state

def should_ask_for_clarification(state: AgentState) -> str:
    """
    Determines the next step after input analysis based on whether clarification is needed.
    """
    print("--- Conditional Edge: Checking if clarification is needed ---")
    if state.get('clarification_questions_needed', False) and state.get('clarification_questions'):
        print("Decision: Clarification needed. Routing to 'ask_clarification_questions'.")
        return "ask_clarification"
    else:
        print("Decision: No clarification needed. Routing to 'generate_brd'.")
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
            "proceed_to_generation": "generate_brd"
        }
    )

    # End points of branches
    workflow.add_edge("generate_brd", END)
    # ask_clarification_questions now also correctly goes to END, as the main loop
    # in main.py will handle collecting input and re-invoking the graph.
    workflow.add_edge("ask_clarification_questions", END)

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
    # The 'analyze_input' node will run and currently will reset clarification_questions_needed to False.
    # So, this test won't show the clarification path unless analyze_input_node is modified for testing.

    # To properly test this path in isolation, you might call a subgraph or specific nodes.
    # For now, this just shows the intent.
    print("Note: analyze_input_node currently overrides clarification_needed. Modify it to test this path.")
    # final_state_2 = app.invoke(initial_state_2) # This will not show clarification due to analyze_input_node's current behavior
    # print(f"Final state 2 (conceptual): {final_state_2.get('messages', [])[-1].content if final_state_2.get('messages') else 'No messages'}")

    print("\nGraph structure reviewed. Further implementation of node logic (especially analyze_input and clarification loop) is pending.")
