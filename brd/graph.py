from typing import TypedDict, Annotated, List
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from brd.agent import generate_initial_brd_sections # Added import

# --- State Definition ---
class AgentState(TypedDict):
    userInput: str
    # The 'messages' field will store the conversation history.
    # We'll use a HumanMessage for user input and AIMessage for agent responses.
    messages: Annotated[List[BaseMessage], operator.add]
    current_brd_content: str # To store the BRD content as it's generated
    clarification_questions_needed: bool
    clarification_questions: List[str]
    # Potentially add other fields later, like:
    # analysis_results: dict
    # confidence_score: float

# --- Node Functions ---
# These will be further developed in subsequent steps.
# For now, they are placeholders or simple pass-throughs.

def start_node(state: AgentState) -> AgentState:
    # This node could eventually do more, like initializing things.
    # For now, it just ensures the input is captured in messages.
    print("--- Executing Start Node ---")
    # Add the user input as a HumanMessage to the messages list
    # This assumes userInput is already populated in the initial state.
    # If not, this node would be responsible for getting it.
    if not state.get('messages'): # Initialize messages if it's not there
        state['messages'] = []

    if state.get('userInput'):
         # Check if the last message is already this userInput to avoid duplicates on re-runs
        if not state['messages'] or state['messages'][-1].content != state['userInput']:
            state['messages'].append(HumanMessage(content=state['userInput']))

    state['current_brd_content'] = "" # Initialize BRD content
    state['clarification_questions_needed'] = False # Default
    state['clarification_questions'] = []
    print(f"Initial state: {state}")
    return state

def analyze_input_node(state: AgentState) -> AgentState:
    # Placeholder for initial input analysis.
    # In the future, this node will use an LLM to:
    # 1. Parse user input, identify domain and complexity.
    # 2. Determine if clarification questions are needed.
    # For now, it will simulate this by defaulting to no clarification needed.
    print("--- Executing Analyze Input Node ---")

    # Simulate analysis: For now, assume no clarification is needed
    state['clarification_questions_needed'] = False

    # If clarification were needed, this node would set:
    # state['clarification_questions_needed'] = True
    # state['clarification_questions'] = ["Question 1?", "Question 2?"]
    # state['messages'].append(AIMessage(content="I have some clarifying questions: ..."))

    print(f"State after analysis: {state}")
    return state

# Updated generate_brd_node
def generate_brd_node(state: AgentState) -> AgentState:
    print("--- Executing Generate BRD Node (Actual Implementation) ---")
    user_input_for_brd = state.get("userInput", "No input provided")
    # If there are messages, try to get the latest human message for more context
    if state.get("messages"):
        for msg in reversed(state.get("messages", [])): # Iterate in reverse to get the latest
            if isinstance(msg, HumanMessage):
                user_input_for_brd = msg.content
                break

    brd_content = generate_initial_brd_sections(user_input_for_brd)
    state["current_brd_content"] = brd_content
    # Ensure AIMessage is imported if not already
    state["messages"].append(AIMessage(content=f"Generated BRD (Partial):\n{brd_content}"))
    print(f"State after BRD generation: {state}")
    return state

def clarification_node(state: AgentState) -> AgentState:
    print("--- Executing Clarification Node ---")
    # This node would present questions and await user feedback.
    # For this initial setup, we're not fully implementing the loop back for answers.
    # It just acknowledges that clarification would happen here.
    questions_formatted = "\n".join(state['clarification_questions'])
    message_to_user = f"I need to understand your requirements better. Please answer the following:\n{questions_formatted}"
    state['messages'].append(AIMessage(content=message_to_user))
    # In a real scenario, the graph would wait for new HumanMessage with answers.
    print(f"State after clarification node: {state}")
    return state


# --- Conditional Edges ---
def should_ask_for_clarification(state: AgentState) -> str:
    print("--- Checking if clarification is needed ---")
    if state.get('clarification_questions_needed', False) and state.get('clarification_questions'):
        print("Decision: Clarification needed.")
        return "ask_clarification"
    print("Decision: No clarification needed, proceed to generation.")
    return "proceed_to_generation"

# --- Graph Definition ---
def create_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("start", start_node)
    workflow.add_node("analyze_input", analyze_input_node)
    # workflow.add_node("clarification_needed_check", analyze_input_node) # This was re-using analyze_input, but conditional edges take a source node
    workflow.add_node("ask_clarification_questions", clarification_node)
    workflow.add_node("generate_brd", generate_brd_node)

    # Set entry point
    workflow.set_entry_point("start")

    # Add edges
    workflow.add_edge("start", "analyze_input")

    # Conditional edge after analysis
    workflow.add_conditional_edges(
        "analyze_input", # Source node for the conditional logic
        should_ask_for_clarification,
        {
            "ask_clarification": "ask_clarification_questions",
            "proceed_to_generation": "generate_brd"
        }
    )
    # For now, clarification node leads to END. Later, it would loop back for user input.
    workflow.add_edge("ask_clarification_questions", END)
    workflow.add_edge("generate_brd", END) # End after generation

    # Compile the graph
    app = workflow.compile()
    return app

if __name__ == '__main__':
    # This is for basic testing of the graph structure.
    # More comprehensive interaction will be in main.py.
    app = create_graph()

    # Example of how to run it
    initial_state = {"userInput": "Develop an AI chatbot for customer service.", "messages": []}

    print("Testing graph execution...")
    # Note: LangGraph's `stream` method returns an iterator.
    # We need to consume it to see the execution.
    for event in app.stream(initial_state):
        # Each `event` is a dictionary where keys are node names
        # and values are the output of that node.
        print(f"Event: {event}")
        print("---")

    final_state = app.invoke(initial_state)
    print(f"Final state: {final_state}")

    print("\nGraph structure defined. Further implementation of node logic is pending.")
