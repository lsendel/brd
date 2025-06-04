from typing import TypedDict, Annotated, List
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from brd.agent import generate_initial_brd_sections

# --- State Definition ---
class AgentState(TypedDict):
    userInput: str
    # The 'messages' field will store the conversation history.
    # operator.add makes new messages append to the list.
    messages: Annotated[List[BaseMessage], operator.add]
    current_brd_content: str # To store the BRD content as it's generated

    # Fields for clarification logic
    clarification_questions_needed: bool
    clarification_questions: List[str]
    # TODO: Add 'clarification_answers: List[str]' or similar when implementing the answer processing part of the loop.
    #       Consider 'processed_answers: dict' if answers need to be structured.

    # Potential future fields:
    # analysis_results: dict  # To store structured output from analyze_input_node
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
    print(f"Initial state after start_node: {state}")
    return state

def analyze_input_node(state: AgentState) -> AgentState:
    """
    Analyzes the initial user input (and potentially subsequent user messages).

    Future Responsibilities:
    - Use an LLM to parse the input, identify domain, estimate complexity.
    - Determine if the input is sufficient or if clarification questions are necessary.
    - If questions are needed:
        - Formulate specific, targeted questions (3-5 as per persona).
        - Set 'clarification_questions_needed' to True.
        - Populate 'clarification_questions' list.
        - Add an AIMessage to 'messages' indicating questions are being asked.
    - Store structured analysis (e.g., domain, complexity, key entities) in 'analysis_results' (future state field).
    """
    print("--- Executing Analyze Input Node (Currently Placeholder) ---")

    # Simulate analysis: For now, assume no clarification is needed.
    # To test the clarification path, this logic would need to be changed,
    # e.g., by checking if input is very short or lacks detail.
    # Example (conceptual):
    # if len(state.get('userInput', '')) < 20: # Arbitrary short length
    #     state['clarification_questions_needed'] = True
    #     state['clarification_questions'] = [
    #         "Could you please elaborate on the main objectives?",
    #         "What are the key features you envision?"
    #     ]
    #     state['messages'].append(AIMessage(content="I have a couple of questions to better understand your needs."))
    # else:
    #     state['clarification_questions_needed'] = False

    state['clarification_questions_needed'] = False # Default for current simplified version

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
    # This could be the initial 'userInput' or a refined understanding after clarifications.
    # For now, it uses the latest HumanMessage or the initial userInput.
    user_input_for_brd = state.get("userInput", "No input provided")
    if state.get("messages"):
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                user_input_for_brd = msg.content # Use the latest human input
                break

    print(f"Input for BRD generation: {user_input_for_brd[:100]}...")
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
    print(f"State after clarification_node: {state}")
    return state

# --- Conditional Edges ---
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
    workflow.add_node("analyze_input", analyze_input_node)
    workflow.add_node("ask_clarification_questions", clarification_node)
    workflow.add_node("generate_brd", generate_brd_node)
    # TODO: When implementing the full clarification loop, add 'process_clarification_answers_node'.

    # Set entry point
    workflow.set_entry_point("start")

    # Define edges
    workflow.add_edge("start", "analyze_input")

    # Conditional branching after input analysis
    workflow.add_conditional_edges(
        "analyze_input",
        should_ask_for_clarification,
        {
            "ask_clarification": "ask_clarification_questions",
            "proceed_to_generation": "generate_brd"
        }
    )

    # Current end points of branches
    workflow.add_edge("generate_brd", END)

    # For the clarification branch:
    # In the current simplified version, it also ends.
    # TODO: For a full clarification loop:
    #   1. 'ask_clarification_questions' would not necessarily go to END.
    #   2. The graph would expect a new HumanMessage with answers.
    #   3. An edge (possibly implicit or handled by re-invocation logic) would lead to
    #      a 'process_clarification_answers_node'.
    #   4. 'process_clarification_answers_node' would then likely lead back to 'generate_brd_node'
    #      or potentially 'analyze_input_node' if answers require further analysis or more questions.
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
