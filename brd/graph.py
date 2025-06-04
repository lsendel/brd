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
class AgentState:
    def __init__(
        self,
        userInput: str,
        messages: Optional[List[BaseMessage]] = None,
        current_brd_content: str = "",
        clarification_questions_needed: bool = False,
        clarification_questions: Optional[List[str]] = None,
        current_understanding: str = "",
        max_clarification_rounds: int = 3,
        current_clarification_round: int = 0,
        clarification_questions_pending_answer: bool = False,
        route_condition: str = "",
        thread_id: Optional[str] = None  # Added thread_id
    ):
        self.userInput: str = userInput
        self.messages: List[BaseMessage] = messages if messages is not None else []
        self.current_brd_content: str = current_brd_content
        self.clarification_questions_needed: bool = clarification_questions_needed
        self.clarification_questions: List[str] = clarification_questions if clarification_questions is not None else []
        self.current_understanding: str = current_understanding if current_understanding else userInput
        self.max_clarification_rounds: int = max_clarification_rounds
        self.current_clarification_round: int = current_clarification_round
        self.clarification_questions_pending_answer: bool = clarification_questions_pending_answer
        self.route_condition: str = route_condition
        self.thread_id: Optional[str] = thread_id # Added thread_id

        # operator.add behavior for messages will be handled by add_message method
        # The graph's state mechanism will use this method if we define 'messages'
        # in a way that Annotated[List[BaseMessage], operator.add] would have worked.
        # For LangGraph to use operator.add, 'messages' needs to be accessible for it to work on.
        # We will ensure our add_message method is what LangGraph calls.
        # For direct use with StateGraph, the annotation on the class itself is not standard.
        # Instead, the `operator.add` is usually for specific fields when used with `with_types`.
        # For now, we manage messages via methods. LangGraph's `StatefulGraph`
        # can be configured to handle updates to fields like `messages` via `operator.add`
        # if the field itself is directly exposed and mutated, or if we use tools/functions
        # that return a partial state to be merged. With a class, direct attribute updates
        # and method calls are more common.

    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)

    def set_route_condition(self, condition: str) -> None:
        self.route_condition = condition

    def set_brd_content(self, content: str) -> None:
        self.current_brd_content = content

    def set_clarification_needed(self, needed: bool) -> None:
        self.clarification_questions_needed = needed

    def set_clarification_questions(self, questions: List[str]) -> None:
        self.clarification_questions = questions

    def set_answers_pending(self, pending: bool) -> None:
        self.clarification_questions_pending_answer = pending

    def increment_clarification_round(self) -> None:
        self.current_clarification_round += 1

    def reset_clarification_round(self) -> None: # Added for completeness
        self.current_clarification_round = 0

    def update_understanding(self, understanding: str) -> None:
        self.current_understanding = understanding

    def get_last_message_content(self) -> Optional[str]: # Example helper
        if not self.messages:
            return None
        return self.messages[-1].content

    def to_dict(self) -> Dict[str, Any]:
        """Converts the AgentState instance to a dictionary for persistence."""
        # Need to handle messages serialization if persistence expects dicts for messages.
        # Assuming persistence layer's _message_to_dict will be used by save_project *after* this.
        # This to_dict is primarily for the top-level AgentState attributes.
        # However, save_project in persistence.py expects BaseMessage objects in the 'messages' list
        # and then serializes them itself. So, self.messages can remain as list of BaseMessage objects.
        return {
            "userInput": self.userInput,
            "messages": self.messages, # Keep as BaseMessage objects
            "current_brd_content": self.current_brd_content,
            "clarification_questions_needed": self.clarification_questions_needed,
            "clarification_questions": self.clarification_questions,
            "current_understanding": self.current_understanding,
            "max_clarification_rounds": self.max_clarification_rounds,
            "current_clarification_round": self.current_clarification_round,
            "clarification_questions_pending_answer": self.clarification_questions_pending_answer,
            "route_condition": self.route_condition,
            "thread_id": self.thread_id,
        }

    # The Annotated[List[BaseMessage], operator.add] part from TypedDict
    # suggests that 'messages' field is intended to be extendable by LangGraph.
    # To achieve this with a class, LangGraph needs to know how to update 'messages'.
    # This is typically done by returning a new AgentState or a dict that updates 'messages'.
    # If using StateGraph(AgentState) where AgentState is a class, updates can be done by
    # returning a dict from nodes: e.g. `return {"messages": new_messages_list}`.
    # LangGraph then merges this. If `operator.add` is desired for a field,
    # the graph must be defined such that it can apply this operator, usually when the
    # state itself (or at least the field) is a dictionary or compatible structure.
    # For a class, we'd typically return new instances or mutated instances.
    # For now, the add_message method is for direct use. LangGraph's merging
    # will handle list extension if nodes return `{"messages": [new_message]}` and the
    # graph is set up to use `operator.add` for the `messages` key.
    # Let's assume for now that nodes will return full or partial state dicts,
    # and LangGraph's default merging strategy (or explicit field-level mergers) apply.
    # If `Annotated` with `operator.add` is critical for graph compilation with a class,
    # this might need specific handling in graph setup or node return values.
    # For now, the class methods are for our use, and graph updates will be standard.


# --- Node Functions ---

def start_node(state: AgentState) -> AgentState:
    """
    Initializes the agent's state.
    - Captures the initial user input into the 'messages' list.
    - Initializes other relevant state fields.
    """
    # Note: The `state` argument in node functions will be an instance of AgentState class.
    # LangGraph will instantiate it based on the input dictionary for the first node,
    # and subsequent nodes will receive the instance passed from the previous node.
    # Modifications should be done using instance attributes and methods.
    # Node functions should return a dictionary of the fields they've changed,
    # or the modified state instance if LangGraph is configured for that (less common for StateGraph).
    # For StateGraph, returning a dict of changed fields is standard, and LangGraph merges it.

    print("--- Executing Start Node ---")
    # If messages is None (e.g. first time state is created from a dict without it),
    # __init__ already ensures it's an empty list.

    # Ensure initial userInput is added as a HumanMessage
    if state.userInput:
        if not state.messages or state.messages[-1].content != state.userInput or not isinstance(state.messages[-1], HumanMessage):
            state.add_message(HumanMessage(content=state.userInput))

    state.set_brd_content("")
    state.set_clarification_needed(False)
    state.set_clarification_questions([])
    # current_understanding is set in __init__ based on userInput if not provided.
    # max_clarification_rounds and current_clarification_round are set by __init__ defaults if not in input.
    # clarification_questions_pending_answer is set by __init__ default.
    state.set_route_condition("") # Initialize routing condition for this run

    print(f"--- Start Node Initialized ---")
    print(f"  Initial userInput: '{state.userInput[:100]}...'")
    print(f"  Initial current_understanding: '{state.current_understanding[:100]}...'")
    print(f"  Max clarification rounds: {state.max_clarification_rounds}")
    # Return a dictionary of changed fields for LangGraph to merge
    # However, since we are modifying the state instance directly,
    # and if LangGraph passes this instance around, returning the instance might be okay.
    # Standard practice with StateGraph is to return a dictionary of updates.
    # For this refactoring, we'll assume direct state modification is visible to next node if not returning dict.
    # Let's try returning the mutated state directly. LangGraph should handle it.
    return state


def analyze_input_node(state: AgentState) -> AgentState:
    """
    Analyzes current understanding and latest user utterance to determine if clarification is needed.
    Updates state attributes like clarification_questions_needed, clarification_questions, and route_condition.
    """
    print(f"\n--- Executing Analyze Input Node (Round {state.current_clarification_round}) ---")

    print(f"  Current round: {state.current_clarification_round}, Max rounds: {state.max_clarification_rounds}")

    if state.current_clarification_round >= state.max_clarification_rounds:
        print(f"  INFO: Clarification round limit reached. Proceeding to generation.")
        state.set_clarification_needed(False)
        state.set_clarification_questions([])
        if not any("Clarification round limit reached" in msg.content for msg in state.messages if isinstance(msg, AIMessage)):
             state.add_message(AIMessage(content="Clarification round limit reached. Proceeding with BRD generation based on current understanding."))
        state.set_route_condition("proceed_to_generation")
        return state

    summary_for_questions = state.current_understanding
    latest_utterance = ""

    if state.current_clarification_round == 0:
        latest_utterance = state.userInput
        print(f"  INFO: First round. Using initial userInput for questions: '{latest_utterance[:100]}...'")
    else:
        if state.messages:
            for message in reversed(state.messages):
                if isinstance(message, HumanMessage):
                    latest_utterance = message.content
                    print(f"  INFO: Subsequent round. Using last HumanMessage (answers) for questions: '{latest_utterance[:100]}...'")
                    break
        if not latest_utterance:
             print("  WARNING: No distinct latest user utterance (HumanMessage) for clarification analysis after round 0. Using current_understanding.")
             latest_utterance = summary_for_questions

    if not summary_for_questions and not latest_utterance:
        print("  ERROR: Both current_understanding and latest_utterance are empty. Cannot generate questions.")
        state.set_clarification_needed(False)
        state.set_clarification_questions([])
        state.add_message(AIMessage(content="INTERNAL ERROR: Missing context to formulate clarification questions."))
        state.set_route_condition("end_due_to_error")
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
        state.add_message(AIMessage(content=f"Agent Error: Could not retrieve clarification questions. Details: {error_detail}"))
        state.set_clarification_needed(False)
        state.set_clarification_questions([])
        state.set_route_condition("proceed_to_generation") # Proceed, BRD might reflect this error state
    elif questions:
        print(f"  INFO: Clarification questions generated: {questions}")
        state.set_clarification_needed(True)
        state.set_clarification_questions(questions)
        state.set_route_condition("ask_clarification")
    else:
        print("  INFO: No clarification questions needed or returned by LLM.")
        state.set_clarification_needed(False)
        state.set_clarification_questions([])
        state.set_route_condition("proceed_to_generation")
    return state


def generate_brd_node(state: AgentState) -> AgentState:
    """
    Generates BRD content using the current understanding.
    Updates 'current_brd_content' and appends an AIMessage with the BRD or error.
    """
    print("\n--- Executing Generate BRD Node ---")

    user_input_for_brd = state.current_understanding if state.current_understanding else state.userInput
    if not user_input_for_brd:
        print("  WARNING: No input or understanding available for BRD generation. Using placeholder.")
        user_input_for_brd = "No specific input or understanding was available for BRD generation."

    print(f"  Input for BRD generation: '{user_input_for_brd[:100]}...'")
    brd_content = generate_initial_brd_sections(user_input_for_brd)
    state.set_brd_content(brd_content)

    if "ERROR:" in brd_content or "Error:" in brd_content:
        print(f"  ERROR: Agent returned an error during BRD generation: {brd_content}")
        state.add_message(AIMessage(content=f"Could not generate BRD. Details: {brd_content}"))
    else:
        state.add_message(AIMessage(content=f"Generated BRD (Partial):\n{brd_content}"))
    return state


def clarification_node(state: AgentState) -> AgentState:
    """
    Presents clarification questions to the user or informs if errors occurred.
    Sets 'clarification_questions_pending_answer' to True if valid questions are asked.
    """
    print(f"\n--- Executing Clarification Node (Round {state.current_clarification_round}) ---")

    current_questions = state.clarification_questions
    if not current_questions:
        print("  WARNING: Clarification Node called but no questions in state. Proceeding.")
        ai_message = "I was about to ask for more details, but I don't have any specific questions right now. Let's continue."
        if not any(msg.content == ai_message for msg in state.messages):
            state.add_message(AIMessage(content=ai_message))
        state.set_answers_pending(False)
        return state

    if any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") or q.startswith("Unparsed response") for q in current_questions):
        print(f"  INFO: Clarification questions list contains error/info messages from agent: {current_questions[0]}")
        state.set_answers_pending(False)
        return state

    questions_formatted = "\n".join([f"{i+1}. {q}" for i, q in enumerate(current_questions)])
    message_to_user = (f"To ensure I create the best possible BRD for you, I have a few clarifying questions:\n"
                       f"{questions_formatted}\nPlease provide your answers.")

    print(f"  Asking valid questions:\n{questions_formatted}")
    state.add_message(AIMessage(content=message_to_user))
    state.set_answers_pending(True)
    return state


def process_clarification_answers_node(state: AgentState) -> AgentState:
    """
    Processes user's answers, refines understanding, and increments clarification round.
    Updates 'current_understanding', clears 'clarification_questions',
    and resets 'clarification_questions_pending_answer'.
    """
    print(f"\n--- Executing Process Clarification Answers Node (Round {state.current_clarification_round}) ---")

    user_answers_text = ""
    if state.messages and isinstance(state.messages[-1], HumanMessage):
        user_answers_text = state.messages[-1].content
        print(f"  Found user answers: '{user_answers_text[:100]}...'")
    else:
        print("  ERROR: Last message is not HumanMessage or no messages found. Cannot process answers.")
        state.add_message(AIMessage(content="It seems I was expecting your answers, but I couldn't find them. This might affect the BRD quality."))
        state.increment_clarification_round() # Increment to avoid loop
        state.set_answers_pending(False)
        state.set_clarification_questions([])
        state.set_route_condition("analyze")
        return state

    questions_that_were_asked = state.clarification_questions # These should have been cleared before answers, but as fallback

    current_summary_for_refinement = state.current_understanding if state.current_understanding else state.userInput

    print(f"  Processing answers for questions: {questions_that_were_asked if questions_that_were_asked else 'N/A (should have been cleared)'}")
    new_understanding = refine_project_understanding(
        current_summary=current_summary_for_refinement,
        questions_asked=questions_that_were_asked, # Pass the questions that were asked
        user_answers=user_answers_text
    )

    if "[LLM_" in new_understanding or "[UNEXPECTED_ERROR" in new_understanding:
        print(f"  ERROR: Refinement of understanding returned an error: {new_understanding}")
        state.add_message(AIMessage(content=f"Agent Error: Could not refine project understanding. Details: {new_understanding}"))
    else:
        print(f"  Old understanding: '{state.current_understanding[:100]}...'")
        state.update_understanding(new_understanding)
        print(f"  New understanding: '{state.current_understanding[:100]}...'")

    state.increment_clarification_round()
    print(f"  Incremented clarification round to: {state.current_clarification_round}")

    state.set_clarification_questions([]) # Clear questions after processing
    state.set_clarification_needed(False)
    state.set_answers_pending(False)
    state.set_route_condition("analyze")
    return state


def route_after_start_node(state: AgentState) -> AgentState:
    """
    Determines initial routing based on whether answers are pending from a previous session.
    Updates 'route_condition' in the state: "process_answers" or "analyze".
    """
    print(f"\n--- Executing Route After Start Node ---")
    pending_answers = state.clarification_questions_pending_answer
    last_message_is_human = bool(state.messages and isinstance(state.messages[-1], HumanMessage))

    print(f"  Pending answers flag: {pending_answers}, Last message is Human: {last_message_is_human}")

    if pending_answers and last_message_is_human:
        print("  DECISION: Answers were pending, and last message is Human. Routing to 'process_answers'.")
        state.set_route_condition("process_answers")
    elif pending_answers and not last_message_is_human:
        print("  WARNING: Answers were pending, but last message is NOT Human. Routing to 'analyze' (may re-ask or end).")
        state.set_route_condition("analyze")
    else: # No answers pending
        print("  DECISION: No answers pending. Routing to 'analyze'.")
        state.set_route_condition("analyze")
    return state


def should_ask_for_clarification(state: AgentState) -> str:
    """
    Determines next step after input analysis based on 'route_condition' from `analyze_input_node`.
    Possible outcomes: "ask_clarification", "proceed_to_generation", "end_due_to_error".
    """
    print(f"\n--- Conditional Edge: Evaluating 'route_condition' from analyze_input_node ---")
    route = state.route_condition
    print(f"  Route condition from state: '{route}'")

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
