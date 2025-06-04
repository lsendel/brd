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
-   **Interactive Clarification Loop**: If initial input is insufficient, the agent can ask clarifying questions to refine its understanding before generating the BRD. This loop is configurable (e.g., max rounds).
-   **Project Persistence**: Automatically saves your work (including conversation history and current understanding) and allows you to load and continue existing projects. Project data is stored locally in the `brd/saved_projects/` directory.

## Project Structure

-   `brd/`: Main package for the agent.
    -   `prompts.py`: Contains the detailed persona and system prompts for the LLM.
    -   `agent.py`: Core logic for BRD generation and clarification, including LLM interaction.
    -   `graph.py`: Defines the agent's stateful workflow using LangGraph (state, nodes, edges), managing the clarification and generation process.
    -   `persistence.py`: Handles saving and loading project states to/from JSON files.
-   `main.py`: CLI entry point to interact with the agent, managing project creation, loading, and user interaction with the graph.
-   `tests/`: Unit tests for various components (agent logic, graph flow, persistence).
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

## Configuration

Beyond the API key, you can configure the LLM behavior using environment variables (also in the `.env` file or set globally):

-   `OPENAI_API_KEY` (Required): Your OpenAI API key.
-   `OPENAI_MODEL_NAME` (Optional): Specifies the OpenAI model to use.
    -   Default: `"gpt-3.5-turbo"`
    -   Example: `OPENAI_MODEL_NAME="gpt-4-turbo-preview"`
-   `OPENAI_TEMPERATURE` (Optional): Controls the creativity of the LLM's responses. It's a float value.
    -   Default: `0.7`
    -   Example: `OPENAI_TEMPERATURE="0.5"`

The agent's clarification question mechanism is designed to receive questions from the LLM in a JSON-formatted list of strings. This is primarily an internal detail relevant for prompt engineering or contributions.

## How to Run

1.  **Ensure you have completed the Setup and Configuration steps above (especially setting `OPENAI_API_KEY`).**
2.  **Run the CLI from the project root directory:**
    ```bash
    python main.py
    ```
3.  **CLI Interaction:**
    *   The agent will initialize and display a welcome message.
    *   You will be presented with a **Main Menu**:
        *   **(N) New Project**: Start a new BRD. You'll be asked for a project name and then your initial concept.
        *   **(L) Load Project**: Load a previously saved project. A list of available projects will be shown for you to choose from.
        *   **(E) Exit**: Quit the application.
    *   If you load a project that was previously waiting for your answers to clarification questions, these questions will be re-displayed.
    *   After the agent processes your input (either generating a BRD or asking clarification questions), your project state is automatically saved.
    *   If a BRD or set of questions is generated, you'll be asked if you want to continue with the current project (e.g., provide answers, refine further), start a new one, load another, or exit.

## Project Persistence

StrataBRD Pro supports project persistence. When you start a new BRD, you'll be asked to name your project (or one will be auto-generated if you leave it blank). All progress, including your inputs, the agent's generated content, conversation history, and current understanding, is automatically saved to a JSON file in the `brd/saved_projects/` directory. When you run `main.py`, the main menu allows you to load an existing project or start a new one.

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
    The test suite covers agent logic, graph workflow, and persistence mechanisms. Mocks are used to prevent actual LLM API calls during tests.

## Future Enhancements (Planned)
- Implement all 14 sections of the BRD structure (currently focuses on initial key sections).
- Integrate a proper Retrieval Augmented Generation (RAG) system for domain-specific knowledge.
- Implement multi-stage validation.
- And much more as per the original issue specification...
