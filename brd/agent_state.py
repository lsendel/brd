from typing import List, Any, Optional
from langchain_core.messages import BaseMessage

class AgentState:
    def __init__(self,
                 userInput: str = "",
                 messages: Optional[List[BaseMessage]] = None,
                 current_brd_content: str = "",
                 clarification_questions_needed: bool = False,
                 clarification_questions: Optional[List[str]] = None,
                 current_understanding: str = "",
                 max_clarification_rounds: int = 3,
                 current_clarification_round: int = 0,
                 clarification_questions_pending_answer: bool = False,
                 route_condition: str = "",
                 thread_id: Optional[str] = None):
        self.userInput = userInput
        self.messages = messages if messages is not None else []
        self.current_brd_content = current_brd_content
        self.clarification_questions_needed = clarification_questions_needed
        self.clarification_questions = clarification_questions if clarification_questions is not None else []
        self.current_understanding = current_understanding
        self.max_clarification_rounds = max_clarification_rounds
        self.current_clarification_round = current_clarification_round
        self.clarification_questions_pending_answer = clarification_questions_pending_answer
        self.route_condition = route_condition
        self.thread_id = thread_id

    def to_dict(self) -> dict:
        return {
            "userInput": self.userInput,
            "messages": self.messages,
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

    # Optional: Add a __repr__ for easier debugging if needed
    def __repr__(self) -> str:
        return (f"AgentState(userInput='{self.userInput[:50]}...', "
                f"messages_count={len(self.messages)}, "
                f"current_brd_content_len={len(self.current_brd_content)}, "
                f"clarification_questions_pending_answer={self.clarification_questions_pending_answer}, "
                f"thread_id='{self.thread_id}')")

    def copy(self):
        """Return a shallow copy of the AgentState instance."""
        return AgentState(
            userInput=self.userInput,
            messages=list(self.messages),  # Create a new list instance for messages
            current_brd_content=self.current_brd_content,
            clarification_questions_needed=self.clarification_questions_needed,
            clarification_questions=list(self.clarification_questions) if self.clarification_questions is not None else [], # Create a new list instance
            current_understanding=self.current_understanding,
            max_clarification_rounds=self.max_clarification_rounds,
            current_clarification_round=self.current_clarification_round,
            clarification_questions_pending_answer=self.clarification_questions_pending_answer,
            route_condition=self.route_condition,
            thread_id=self.thread_id
        )
