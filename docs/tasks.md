# Actionable Improvement Tasks for StrataBRD Pro

This document lists actionable tasks to improve the StrataBRD Pro codebase, covering architectural, code-level, and user experience aspects.

## Error Handling & Robustness

- [x] **Enhance LLM Error Handling:** Implement more comprehensive error handling for LLM API calls in `brd/agent.py` (e.g., implement retry mechanisms with exponential backoff for transient errors like `RateLimitError`, `APITimeoutError`, `APIConnectionError`).
- [x] **User-Facing Error Messages:** Provide more specific and user-friendly error messages in the CLI when LLM calls fail or other critical errors occur.
- [x] **Input Validation (`main.py`):** Strengthen input validation in `main.py`, particularly for project names (e.g., disallow special characters that might cause issues with filenames, check for empty names more explicitly).
- [x] **Persistence Edge Cases:** Investigate and handle potential edge cases in `brd/persistence.py` (e.g., disk full scenarios, permissions issues during file I/O).
- [x] **Graceful Degradation:** If the LLM is unavailable (e.g., API key missing, network issues), ensure the application degrades gracefully, perhaps offering to work in an offline mode if feasible for certain features, or providing very clear guidance.

## Code Structure & Maintainability

- [x] **Refactor `main.py`:** Move project management functions (`handle_load_project`, `handle_new_project`) from `main.py` into a new module, e.g., `brd/project_manager.py`, to reduce `main.py`'s length and improve separation of concerns.
- [x] **`AgentState` as Class:** Consider converting the `AgentState` TypedDict in `brd/graph.py` into a class. This class could encapsulate state modification logic, potentially simplifying node functions and ensuring more controlled state transitions.
- [ ] **LLM Dependency Injection:** Refactor `brd/agent.py` to allow the LLM instance to be injected as a dependency. This would simplify testing (easier mocking) and improve flexibility if different LLM configurations are needed.
- [ ] **Separate Test Logic:** Ensure all test-related logic and helper functions currently in `if __name__ == '__main__':` blocks within the main library code (e.g., `brd/agent.py`, `brd/graph.py`) are moved to the `tests/` directory.
- [ ] **Prompt Management:** As the number of prompts in `brd/prompts.py` grows (especially with the 14 BRD sections), devise a more structured way to manage and select prompts, potentially using a prompt registry or template manager.
- [ ] **Configuration Management:** Centralize configuration settings (e.g., `max_clarification_rounds`, default LLM model, temperature) into a dedicated configuration module or class, loaded from environment variables or a config file.

## User Experience (CLI)

- [ ] **Clearer CLI State Reporting:** Enhance `main.py` to provide clearer, real-time feedback to the user about the agent's current state (e.g., "Analyzing your input...", "Asking clarification questions...", "Generating BRD draft...").
- [ ] **Improved Input Handling:** Make CLI input handling more robust and user-friendly (e.g., case-insensitive commands, clearer error messages for invalid choices).
- [ ] **Progress Indicators:** For potentially long-running operations like LLM calls, consider adding simple text-based progress indicators or "working..." messages.
- [ ] **Help Command:** Implement a `help` command in the CLI to explain available actions and how to use the agent.

## Modularity & Reusability

- [ ] **BRD Section Generation:** Refactor `generate_initial_brd_sections` in `brd/agent.py`. As the agent expands to generate all 14 BRD sections, break this function into smaller, more manageable functions, each responsible for a specific section or group of related sections.
- [ ] **Message Serialization/Deserialization:** Review `_message_to_dict` and `_dict_to_message` in `brd/persistence.py` to ensure they robustly handle all current and future `BaseMessage` types used by LangChain.
- [ ] **Core Logic Abstraction:** Identify core business logic within UI-specific code (`main.py`) and consider abstracting it into the `brd` package for better separation and potential reuse if the interface changes (e.g., web UI).

## Testing

- [ ] **Increase Test Coverage:** Review current test coverage (e.g., using `coverage.py`) and add more unit tests for critical components, especially for `brd/agent.py` logic, `brd/graph.py` state transitions, and complex conditions in `main.py`.
- [ ] **Edge Case Testing:** Add tests for edge cases, such as empty inputs, invalid project IDs, corrupted project files, and LLM error responses.
- [ ] **Integration Tests:** Develop integration tests that cover the end-to-end flow from `main.py` through the LangGraph agent and back, mocking LLM calls.
- [ ] **Test `run_tests.sh`:** Ensure `run_tests.sh` is robust and correctly discovers and runs all tests, reporting results clearly.

## Configuration

- [ ] **Configurable `max_clarification_rounds`:** Allow `max_clarification_rounds` to be configured via an environment variable or a configuration file, rather than just being a default in code.
- [ ] **LLM Parameter Configuration:** Expose more LLM parameters (e.g., `top_p`, `presence_penalty`) for configuration if advanced users need to fine-tune LLM behavior.

## Documentation & Comments

- [ ] **Comprehensive Docstrings:** Add comprehensive docstrings (e.g., Google Python Style) to all modules, classes, and functions, detailing purpose, arguments, return values, and any exceptions raised.
- [ ] **README Updates:** Keep `README.md` updated with any changes to setup, configuration, or CLI usage resulting from these tasks.
- [ ] **In-Code Comments:** Review and enhance in-code comments for complex logic sections to ensure clarity for future maintainers.
- [ ] **Architectural Overview:** Consider adding a brief architectural overview document in `docs/` explaining the main components and data flow.

## Feature Enhancements (from README & Persona)

- [ ] **Implement All 14 BRD Sections:** Systematically implement the generation logic for all 14 BRD sections outlined in `STRATA_BRD_PRO_PERSONA` and `brd/prompts.py`. This will likely be a major epic involving multiple sub-tasks related to prompt engineering and agent logic.
- [ ] **Retrieval Augmented Generation (RAG):** Design and implement a RAG system to provide domain-specific knowledge to the LLM, enhancing the quality and relevance of generated BRD content.
- [ ] **Multi-Stage Validation:** Develop and integrate a multi-stage validation process for generated BRD content, potentially involving LLM-based self-critique or rule-based checks against the persona's quality standards.
- [ ] **Advanced Elicitation Techniques:** Incorporate the advanced elicitation techniques mentioned in `STRATA_BRD_PRO_PERSONA` (e.g., "5 Whys", "Jobs to be Done") into the agent's clarification and analysis capabilities.
- [ ] **Diagram Generation (Mermaid):** Implement the capability for the agent to generate diagrams using Mermaid syntax as specified in the persona's output standards.

## Code-Specific Refinements

- [ ] **`AgentState` Initialization in `main.py`:** Refactor how `AgentState` is initialized or reconstructed in `main.py` for new and loaded projects. Consider using dedicated factory functions or methods (perhaps in `AgentState` if it becomes a class, or in `brd.graph`) to handle this, reducing direct dictionary manipulation in `main.py`.
- [ ] **Routing Conditions in `brd/graph.py`:** Review the string-based `route_condition` values in `AgentState`. For complex routing, consider using enums or a more structured approach to define and manage these conditions to prevent typos and improve clarity.
- [ ] **Error Message Constants:** For error messages returned by agent functions (e.g., "LLM_UNAVAILABLE..."), define these as constants in `brd/agent.py` or a shared constants module to avoid string literals scattered in the code and ensure consistency.
