# StrataBRD Pro - AI Business Requirements Architect

StrataBRD Pro is an AI agent designed to autonomously generate comprehensive, industry-standard Business Requirements Documents (BRDs) from high-level concepts or concise prompts. This initial version focuses on core functionalities using the LangGraph framework.

## Overview

The agent embodies the persona of "StrataBRD Pro," an elite AI Business Requirements Architect. It leverages a Large Language Model (LLM) to understand user input and generate structured BRD sections. The underlying architecture is built with [LangGraph](https://python.langchain.com/docs/langgraph/), allowing for a stateful, multi-step process.

**Current Capabilities (Initial Version):**
-   Accepts a high-level concept from the user via a command-line interface (CLI).
-   Generates an initial BRD draft in Markdown format, including:
    -   Executive Summary
    -   Vision & Scope
    -   Basic Functional Requirements (as user stories with acceptance criteria)
-   Follows the core principles and output standards defined in its persona.
-   **Project Persistence**: Automatically saves your work and allows you to load and continue existing projects. Project data is stored locally in the `brd/saved_projects/` directory.

## Project Structure

-   `brd/`: Main package for the agent.
    -   `prompts.py`: Contains the detailed persona and system prompts for the LLM.
    -   `agent.py`: Core logic for BRD generation, including LLM interaction.
    -   `graph.py`: Defines the agent's workflow using LangGraph (state, nodes, edges).
-   `main.py`: CLI entry point to interact with the agent.
-   `tests/`: Unit tests for various components.
-   `requirements.txt`: Python dependencies.
-   `run_tests.sh`: Script to execute unit tests.

## Setup

1.  **Clone the repository (if applicable).**

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # venv\Scripts\activate    # On Windows
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up OpenAI API Key:**
    The agent uses OpenAI's GPT models. You need to provide your API key.
    -   Create a file named `.env` in the project root directory (next to `main.py`).
    -   Add your API key to the `.env` file like this:
        ```
        OPENAI_API_KEY='your_actual_openai_api_key_here'
        ```
    **Important:** Keep your API key confidential. Do not commit the `.env` file to version control if this were a shared repository.

## How to Run

1.  **Ensure you have completed the Setup steps above.**
2.  **Run the CLI:**
    ```bash
    python main.py
    ```
    The agent will initialize. If you have existing saved projects, it will list them and ask if you want to load one. Otherwise, or if you choose not to load, you'll be prompted to name a new project. Your progress is saved automatically after each interaction.

3.  **Example Interaction:**
    ```
    Enter your high-level concept or BRD idea: Develop an AI-powered chatbot for customer service that can handle product returns and answer FAQs.
    ```
    The agent will then process the request and output the generated BRD sections.

## Project Persistence

StrataBRD Pro now supports project persistence. When you start a new BRD, you'll be asked to name your project. All progress, including your inputs, the agent's generated content, and conversation history, is automatically saved to a JSON file in the `brd/saved_projects/` directory. When you run `main.py`, you'll have the option to load an existing project from this directory or start a new one.

## Running Tests

1.  **Ensure dependencies are installed (see Setup).**
2.  **Make the test script executable (if not already):**
    ```bash
    chmod +x run_tests.sh
    ```
3.  **Run the tests from the project root directory:**
    ```bash
    ./run_tests.sh
    ```
    Note: Some tests in `tests/test_agent.py` related to LLM mocking might currently be failing due Fto challenges in precisely mocking the LangChain library's behavior. Tests for prompts and graph structure should pass.

## Future Enhancements (Planned)
- Implement all 14 sections of the BRD structure.
- Add robust clarification question loops.
- Integrate a proper Retrieval Augmented Generation (RAG) system.
- Implement multi-stage validation.
- And much more as per the original issue specification...
