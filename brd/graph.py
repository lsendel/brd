from typing import TypedDict, Annotated, List, Optional, Dict, Any # Added Optional, Dict, Any
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
    current_understanding: str
    max_clarification_rounds: int
    current_clarification_round: int
    clarification_questions_pending_answer: bool
    route_condition: str # for routing logic
    thread_id: Optional[str] # Added thread_id for persistence

import os # For OPENAI_API_KEY in __main__
from langchain_openai import ChatOpenAI # For LLM initialization in __main__

# --- Node Functions ---

def start_node(state: AgentState, config: dict | None = None) -> Dict[str, Any]:
    """
    Initializes the agent's state or processes initial input.
    """
    print("--- Executing Start Node ---")
    updated_fields: Dict[str, Any] = {}

    # Ensure initial userInput is captured in messages
    # If messages is empty or last message is not this userInput
    if state.get('userInput'):
        if not state.get('messages') or state['messages'][-1].content != state['userInput'] or not isinstance(state['messages'][-1], HumanMessage):
            updated_fields["messages"] = [HumanMessage(content=state['userInput'])]
        else: # messages already exist and last one matches userInput, preserve them
            updated_fields["messages"] = state['messages']

    # Initialize other fields if they are not present, or set to initial values
    if 'current_brd_content' not in state or state.get('current_brd_content') != "":
        updated_fields['current_brd_content'] = ""
    if 'clarification_questions_needed' not in state or state.get('clarification_questions_needed') is not False:
        updated_fields['clarification_questions_needed'] = False
    if 'clarification_questions' not in state or state.get('clarification_questions'): # if it exists and is not empty
        updated_fields['clarification_questions'] = []

    # current_understanding defaults to userInput if not already set or different
    # This logic is now primarily handled by how initial_state_dict is formed.
    # If the state comes in with current_understanding, we respect it.
    # If not, it should have been set from userInput when the TypedDict was created.
    if 'current_understanding' not in state and state.get('userInput'):
         updated_fields['current_understanding'] = state['userInput']
    elif not state.get('current_understanding') and state.get('userInput'): # if current_understanding is empty string
         updated_fields['current_understanding'] = state['userInput']


    if 'route_condition' not in state or state.get('route_condition') != "":
        updated_fields['route_condition'] = ""

    # Ensure essential fields like max_clarification_rounds and current_clarification_round have defaults
    # if not provided in the initial input to the graph.
    # TypedDict itself doesn't enforce defaults in the same way a class __init__ does.
    # The initial dictionary passed to app.stream should provide these.
    # For robustness, nodes can check and set if still missing, though it's better if graph input is complete.
    if 'max_clarification_rounds' not in state:
        updated_fields['max_clarification_rounds'] = 3 # Default
    if 'current_clarification_round' not in state:
        updated_fields['current_clarification_round'] = 0 # Default


    print(f"--- Start Node Initialized/Processed ---")
    print(f"  Initial userInput: '{state.get('userInput', '')[:100]}...'")
    print(f"  Initial current_understanding: '{state.get('current_understanding', '')[:100]}...'")
    print(f"  Max clarification rounds: {state.get('max_clarification_rounds', 3)}")
    return updated_fields


def analyze_input_node(state: AgentState, config: dict | None = None) -> Dict[str, Any]:
    """
    Analyzes current understanding and latest user utterance to determine if clarification is needed.
    """
    print(f"\n--- Executing Analyze Input Node (Round {state.get('current_clarification_round', 0)}) ---")
    updated_fields: Dict[str, Any] = {}

    current_round = state.get('current_clarification_round', 0)
    max_rounds = state.get('max_clarification_rounds', 3)

    if current_round >= max_rounds:
        print(f"  INFO: Clarification round limit reached. Proceeding to generation.")
        updated_fields['clarification_questions_needed'] = False
        updated_fields['clarification_questions'] = []
        # Add AIMessage if not already present (idempotency for retries)
        # This requires messages to be part of the state, and for operator.add to be configured for it.
        if not any("Clarification round limit reached" in msg.content for msg in state.get('messages', []) if isinstance(msg, AIMessage)):
             updated_fields['messages'] = [AIMessage(content="Clarification round limit reached. Proceeding with BRD generation based on current understanding.")]
        updated_fields['route_condition'] = "proceed_to_generation"
        return updated_fields

    summary_for_questions = state.get('current_understanding', '')
    latest_utterance = ""

    if current_round == 0:
        latest_utterance = state.get('userInput', '')
        print(f"  INFO: First round. Using initial userInput for questions: '{latest_utterance[:100]}...'")
    else:
        messages = state.get('messages', [])
        if messages:
            for message in reversed(messages):
                if isinstance(message, HumanMessage):
                    latest_utterance = message.content
                    print(f"  INFO: Subsequent round. Using last HumanMessage (answers) for questions: '{latest_utterance[:100]}...'")
                    break
        if not latest_utterance:
             print("  WARNING: No distinct latest user utterance (HumanMessage) for clarification analysis after round 0. Using current_understanding.")
             latest_utterance = summary_for_questions

    if not summary_for_questions and not latest_utterance:
        print("  ERROR: Both current_understanding and latest_utterance are empty. Cannot generate questions.")
        updated_fields['clarification_questions_needed'] = False
        updated_fields['clarification_questions'] = []
        updated_fields['messages'] = [AIMessage(content="INTERNAL ERROR: Missing context to formulate clarification questions.")]
        updated_fields['route_condition'] = "end_due_to_error"
        return updated_fields

    print(f"  INFO: Calling agent to get clarification questions...")
    llm_instance = config.get('llm') if config else None
    questions = get_clarification_questions(
        llm_instance,
        current_project_summary=summary_for_questions,
        latest_user_utterance=latest_utterance
    )
    print(f"  INFO: Agent returned questions: {questions}")

    if questions and any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") or q.startswith("Unparsed response") for q in questions):
        error_detail = questions[0] if questions else "Unknown agent error."
        print(f"  ERROR: Agent returned an error instead of questions: {error_detail}")
        updated_fields['messages'] = [AIMessage(content=f"Agent Error: Could not retrieve clarification questions. Details: {error_detail}")]
        updated_fields['clarification_questions_needed'] = False
        updated_fields['clarification_questions'] = []
        updated_fields['route_condition'] = "proceed_to_generation"
    elif questions:
        print(f"  INFO: Clarification questions generated: {questions}")
        updated_fields['clarification_questions_needed'] = True
        updated_fields['clarification_questions'] = questions
        updated_fields['route_condition'] = "ask_clarification"
    else:
        print("  INFO: No clarification questions needed or returned by LLM.")
        updated_fields['clarification_questions_needed'] = False
        updated_fields['clarification_questions'] = []
        updated_fields['route_condition'] = "proceed_to_generation"
    return updated_fields


def generate_brd_node(state: AgentState, config: dict | None = None) -> Dict[str, Any]:
    """
    Generates BRD content using the current understanding.
    """
    print("\n--- Executing Generate BRD Node ---")
    updated_fields: Dict[str, Any] = {}

    user_input_for_brd = state.get('current_understanding') if state.get('current_understanding') else state.get('userInput', '')
    if not user_input_for_brd:
        print("  WARNING: No input or understanding available for BRD generation. Using placeholder.")
        user_input_for_brd = "No specific input or understanding was available for BRD generation."

    print(f"  Input for BRD generation: '{user_input_for_brd[:100]}...'")
    llm_instance = config.get('llm') if config else None
    brd_content = generate_initial_brd_sections(llm_instance, user_input_for_brd)
    updated_fields['current_brd_content'] = brd_content

    # Add message about BRD generation result.
    messages_to_add = []
    if "ERROR:" in brd_content or "Error:" in brd_content or (not llm_instance and "LLM not available" in brd_content):
        print(f"  ERROR: Agent returned an error during BRD generation: {brd_content}")
        messages_to_add.append(AIMessage(content=f"Could not generate BRD. Details: {brd_content}"))
    else:
        messages_to_add.append(AIMessage(content=f"Generated BRD (Partial):\n{brd_content}"))
    if messages_to_add:
       updated_fields['messages'] = messages_to_add # This will extend due to Annotated operator.add

    return updated_fields


def clarification_node(state: AgentState, config: dict | None = None) -> Dict[str, Any]:
    """
    Presents clarification questions to the user or informs if errors occurred.
    """
    print(f"\n--- Executing Clarification Node (Round {state.get('current_clarification_round',0)}) ---")
    updated_fields: Dict[str, Any] = {}
    messages_to_add = []

    current_questions = state.get('clarification_questions', [])
    if not current_questions:
        print("  WARNING: Clarification Node called but no questions in state. Proceeding.")
        ai_message = "I was about to ask for more details, but I don't have any specific questions right now. Let's continue."

        last_ai_msg_content = ""
        for msg in reversed(state.get('messages', [])): # Check if last AI message is same
            if isinstance(msg, AIMessage):
                last_ai_msg_content = msg.content
                break
        if last_ai_msg_content != ai_message: # Avoid duplicate messages
            messages_to_add.append(AIMessage(content=ai_message))
        updated_fields['clarification_questions_pending_answer'] = False
        if messages_to_add: updated_fields['messages'] = messages_to_add
        return updated_fields

    if any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") or q.startswith("Unparsed response") for q in current_questions):
        print(f"  INFO: Clarification questions list contains error/info messages from agent: {current_questions[0]}")
        # This message is already from the agent (e.g. LLM error), so it's already in `clarification_questions`.
        # We don't need to add another AIMessage here.
        # The error message itself will be part of the state if clarification_questions is persisted.
        updated_fields['clarification_questions_pending_answer'] = False
        return updated_fields

    questions_formatted = "\n".join([f"{i+1}. {q}" for i, q in enumerate(current_questions)])
    message_to_user = (f"To ensure I create the best possible BRD for you, I have a few clarifying questions:\n"
                       f"{questions_formatted}\nPlease provide your answers.")

    print(f"  Asking valid questions:\n{questions_formatted}")
    messages_to_add.append(AIMessage(content=message_to_user))
    updated_fields['messages'] = messages_to_add
    updated_fields['clarification_questions_pending_answer'] = True
    return updated_fields


def process_clarification_answers_node(state: AgentState, config: dict | None = None) -> Dict[str, Any]:
    """
    Processes user's answers, refines understanding, and increments clarification round.
    """
    print(f"\n--- Executing Process Clarification Answers Node (Round {state.get('current_clarification_round',0)}) ---")
    updated_fields: Dict[str, Any] = {}
    messages_to_add = []

    user_answers_text = ""
    messages = state.get('messages', [])
    if messages and isinstance(messages[-1], HumanMessage):
        user_answers_text = messages[-1].content
        print(f"  Found user answers: '{user_answers_text[:100]}...'")
    else:
        print("  ERROR: Last message is not HumanMessage or no messages found. Cannot process answers.")
        messages_to_add.append(AIMessage(content="It seems I was expecting your answers, but I couldn't find them. This might affect the BRD quality."))
        updated_fields['current_clarification_round'] = state.get('current_clarification_round', 0) + 1
        updated_fields['clarification_questions_pending_answer'] = False
        updated_fields['clarification_questions'] = [] # Clear questions
        updated_fields['route_condition'] = "analyze" # Re-analyze after this error
        if messages_to_add: updated_fields['messages'] = messages_to_add
        return updated_fields

    questions_that_were_asked = state.get('clarification_questions', [])
    current_summary_for_refinement = state.get('current_understanding', state.get('userInput', ''))

    print(f"  Processing answers for questions: {questions_that_were_asked if questions_that_were_asked else 'N/A (should have been cleared)'}")
    llm_instance = config.get('llm') if config else None
    new_understanding = refine_project_understanding(
        llm_instance,
        current_summary=current_summary_for_refinement,
        questions_asked=questions_that_were_asked,
        user_answers=user_answers_text
    )

    if "[LLM_" in new_understanding or "[UNEXPECTED_ERROR" in new_understanding or (not llm_instance and "LLM_UNAVAILABLE" in new_understanding):
        print(f"  ERROR: Refinement of understanding returned an error: {new_understanding}")
        messages_to_add.append(AIMessage(content=f"Agent Error: Could not refine project understanding. Details: {new_understanding}"))
    else:
        print(f"  Old understanding: '{state.get('current_understanding','')[:100]}...'")
        updated_fields['current_understanding'] = new_understanding
        print(f"  New understanding: '{new_understanding[:100]}...'")

    if messages_to_add: updated_fields['messages'] = messages_to_add
    updated_fields['current_clarification_round'] = state.get('current_clarification_round', 0) + 1
    print(f"  Incremented clarification round to: {updated_fields['current_clarification_round']}")
    updated_fields['clarification_questions'] = []
    updated_fields['clarification_questions_needed'] = False
    updated_fields['clarification_questions_pending_answer'] = False
    updated_fields['route_condition'] = "analyze"
    return updated_fields


def route_after_start_node(state: AgentState, config: dict | None = None) -> Dict[str, Any]:
    """
    Determines initial routing based on whether answers are pending from a previous session.
    """
    print(f"\n--- Executing Route After Start Node ---")
    pending_answers = state.get('clarification_questions_pending_answer', False)
    messages = state.get('messages', [])
    last_message_is_human = bool(messages and isinstance(messages[-1], HumanMessage))

    print(f"  Pending answers flag: {pending_answers}, Last message is Human: {last_message_is_human}")

    new_route_condition = ""
    if pending_answers and last_message_is_human:
        print("  DECISION: Answers were pending, and last message is Human. Routing to 'process_answers'.")
        new_route_condition = "process_answers"
    elif pending_answers and not last_message_is_human:
        print("  WARNING: Answers were pending, but last message is NOT Human. Routing to 'analyze' (may re-ask or end).")
        new_route_condition = "analyze"
    else: # No answers pending
        print("  DECISION: No answers pending. Routing to 'analyze'.")
        new_route_condition = "analyze"
    return {"route_condition": new_route_condition}


def should_ask_for_clarification(state_dict: AgentState) -> str: # Parameter is AgentState (TypedDict)
    """
    Determines next step after input analysis based on 'route_condition' from `analyze_input_node`.
    Possible outcomes: "ask_clarification", "proceed_to_generation", "end_due_to_error".
    """
    print(f"\n--- Conditional Edge: Evaluating 'route_condition' from analyze_input_node ---")
    # Conditional functions receive the state dictionary directly.
    route = state_dict.get('route_condition', '')
    print(f"  Route condition from state dictionary: '{route}'")

    if route == "ask_clarification":
        print("  DECISION: Routing to 'ask_clarification_questions'.")
        return "ask_clarification"
    elif route == "end_due_to_error":
        print("  DECISION: Routing to END due to error in analyze_input_node.")
        return "end_due_to_error"

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
        # Conditional functions receive the state dictionary.
        lambda state_dict: state_dict.get('route_condition') if state_dict.get('route_condition') else 'analyze',
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
    # Initialize LLM for testing
    test_llm: ChatOpenAI | None = None
    if os.getenv("OPENAI_API_KEY"): # This check is important
        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
        temperature_str = os.getenv("OPENAI_TEMPERATURE", "0.7")
        try:
            temperature = float(temperature_str)
        except ValueError:
            print(f"WARNING: Invalid OPENAI_TEMPERATURE value '{temperature_str}'. Defaulting to 0.7 for test LLM.")
            temperature = 0.7
        try:
            test_llm = ChatOpenAI(model=model_name, temperature=temperature)
            print(f"INFO: Test LLM initialized with model: {model_name}, temperature: {temperature}.")
        except Exception as e:
            print(f"ERROR: Failed to initialize test_llm: {e}")
            test_llm = None
    else:
        print("WARNING: OPENAI_API_KEY not found. Test LLM will be None. LLM-dependent tests will show placeholder/error messages.")

    app = create_graph()
    graph_config_base = {"recursion_limit": 10}

    # Test Case 1: Straight to BRD generation
    print("\n--- Test Case 1: Straight to BRD Generation ---")
    initial_state_dict_1: AgentState = {
        "userInput": "Develop an AI chatbot for customer service that handles returns and FAQs.",
        "messages": [],
        # Fields required by TypedDict, with defaults if not logically set by this specific test case
        "current_brd_content": "",
        "clarification_questions_needed": False,
        "clarification_questions": [],
        "current_understanding": "Develop an AI chatbot for customer service that handles returns and FAQs.", # Explicitly set
        "max_clarification_rounds": 3,
        "current_clarification_round": 0,
        "clarification_questions_pending_answer": False,
        "route_condition": "",
        "thread_id": "test-thread-1"
    }

    current_graph_config = {**graph_config_base, 'llm': test_llm, "configurable": {"thread_id": "test-thread-1"}}
    print(f"Invoking with config: {current_graph_config.keys()}")


    final_state_1 = None
    # Stream events to see node execution
    for event in app.stream(initial_state_dict_1, config=current_graph_config): # Pass dict
        print(f"Event: {event}")
        if event.get(END):
            final_state_1 = event[END].get('__values__')
        print("---")

    if not final_state_1: # Fallback if END not captured
        final_state_1 = app.invoke(initial_state_dict_1, config=current_graph_config) # Pass dict

    if final_state_1 and final_state_1.get('messages'):
        # final_state_1 is a dict representation of AgentState
        print(f"Final state 1: {final_state_1['messages'][-1].content if final_state_1.get('messages') else 'No messages'}")
    else:
        print(f"Final state 1: No messages or final state not captured properly. State: {final_state_1}")


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
    initial_state_dict_2: AgentState = {
        "userInput": "Another vague idea.",
        "messages": [],
        "max_clarification_rounds": 1, # Override max rounds
        "current_brd_content": "",
        "clarification_questions_needed": False,
        "clarification_questions": [],
        "current_understanding": "Another vague idea.", # Explicitly set
        "current_clarification_round": 0,
        "clarification_questions_pending_answer": False,
        "route_condition": "",
        "thread_id": "test-thread-2"
    }

    print("\n--- Test Case 2: Override max_clarification_rounds (expect 1 round of questions if LLM available) ---")
    current_graph_config_tc2 = {**graph_config_base, 'llm': test_llm, "configurable": {"thread_id": "test-thread-2"}}
    print(f"Invoking with config: {current_graph_config_tc2.keys()}")
    final_state_2 = None
    # Stream events to see node execution
    for event in app.stream(initial_state_dict_2, config=current_graph_config_tc2): # Pass dict
        print(f"Event for Test Case 2: {event}")
        if event.get(END): # If an END event is found
            final_state_2 = event[END].get('__values__')
        print("---")

    if not final_state_2: # Fallback if END not captured
        final_state_2 = app.invoke(initial_state_dict_2, config=current_graph_config_tc2) # Pass dict

    if final_state_2:
        # final_state_2 is a dict
        print(f"Final state 2 (max_clarification_rounds=1):")
        print(f"  Messages: {[msg.content for msg in final_state_2['messages']] if final_state_2.get('messages') else 'No messages'}")
        print(f"  BRD Content: {final_state_2.get('current_brd_content')}")
        print(f"  Clarification round: {final_state_2.get('current_clarification_round')}")
        print(f"  Max rounds in state: {final_state_2.get('max_clarification_rounds')}")
        if test_llm is None:
            print("  (Test LLM was None, so expect placeholder/error messages if LLM was required)")
    else:
        print("Final state 2: Not captured.")


    # Test Case 3: Simulating an error from agent (e.g., LLM unavailable)
    print("\n--- Test Case 3: Simulate LLM Error during BRD generation (by passing LLM as None) ---")
    initial_state_dict_3: AgentState = {
        "userInput": "Test input for LLM error.",
        "messages": [],
        "current_understanding": "Test input for LLM error.", # Ensure this is used
        "current_brd_content": "",
        "clarification_questions_needed": False,
        "clarification_questions": [],
        "max_clarification_rounds": 3,
        "current_clarification_round": 0,
        "clarification_questions_pending_answer": False,
        "route_condition": "",
        "thread_id": "test-thread-3"
    }

    # Pass LLM as None in the config for this specific test
    current_graph_config_tc3 = {**graph_config_base, 'llm': None, "configurable": {"thread_id": "test-thread-3"}}
    print(f"Invoking with config: {current_graph_config_tc3.keys()} (llm explicitly None)")


    final_state_3 = None
    print("Invoking graph, expecting error message in AIMessage as LLM is None...")
    for event in app.stream(initial_state_dict_3, config=current_graph_config_tc3): # Pass dict
        print(f"Event for Test Case 3: {event}")
        if event.get(END):
            final_state_3 = event[END].get('__values__')
        print("---")

    if not final_state_3: # Fallback if END not captured
        final_state_3 = app.invoke(initial_state_dict_3, config=current_graph_config_tc3) # Pass dict

    if final_state_3 and final_state_3.get('messages'):
        # final_state_3 is a dict
        last_message = final_state_3['messages'][-1]
        print(f"Last message content from Test Case 3: {last_message.content}")
        expected_error_substring = "LLM not available" # From agent.py when LLM is None
        if isinstance(last_message, AIMessage) and expected_error_substring in last_message.content:
            print("SUCCESS: Correctly propagated LLM unavailability error as AIMessage.")
        elif isinstance(last_message, AIMessage) and ("ERROR:" in last_message.content or "Error:" in last_message.content) :
             print(f"PARTIAL SUCCESS: AIMessage contains an error, but not the exact expected '{expected_error_substring}'. Content: {last_message.content}")
        else:
            print(f"FAILURE: Last message was not an AIMessage with the expected error. Message: {last_message}")
    else:
        print("FAILURE: No messages found in final state for Test Case 3 or END not captured.")

    print("\n--- Graph Test Suite Complete ---")
