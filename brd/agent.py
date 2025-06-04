import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from brd.prompts import STRATA_BRD_PRO_PERSONA

# Initialize the LLM
# Ensure OPENAI_API_KEY is set in the environment
# For local development, you can use a .env file and load it with python-dotenv
# import dotenv
# dotenv.load_dotenv()

# Check if API key is available
if not os.getenv("OPENAI_API_KEY"):
    print("Warning: OPENAI_API_KEY not found in environment. LLM calls will fail.")
    # You might want to raise an error or handle this more gracefully
    # For now, we'll let it proceed and potentially fail at LLM call time if not set.

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
# Using gpt-3.5-turbo for now as it's faster and cheaper for development.
# Can be upgraded to gpt-4 or others as specified in persona for production.

def generate_initial_brd_sections(user_input: str) -> str:
    """
    Generates a subset of BRD sections based on user input and the StrataBRD Pro persona.
    Focuses on: Executive Summary, Vision & Scope, and a basic Functional Requirements structure.
    """
    print(f"--- Calling LLM for BRD Generation with input: {user_input[:100]}... ---")

    # Construct the prompt for the LLM
    # We are combining the system persona with a specific task for the user input.

    generation_prompt_text = f"""
{STRATA_BRD_PRO_PERSONA}

--------------------------------------------------
USER'S INITIAL CONCEPT:
{user_input}
--------------------------------------------------

TASK:
Based on the user's initial concept, please generate the following sections for a Business Requirements Document (BRD).
Ensure you adhere to the OUTPUT STANDARDS defined in your persona, especially:
- Use Markdown with proper heading hierarchy.
- Number all requirements uniquely (e.g., FR-001 for Functional Requirements).
- For Functional Requirements, provide a basic structure or a few examples if possible, based on the input.

SECTIONS TO GENERATE:
1.  **Executive Summary**
    *   Business opportunity/problem (derived from input)
    *   Proposed solution overview (derived from input)
    *   Expected benefits (high-level, if inferable)

2.  **Vision & Scope**
    *   Product vision statement (derived from input)
    *   In-scope features (high-level list based on input)
    *   Out-of-scope items (make reasonable assumptions or state if unclear)

3.  **Functional Requirements** (Provide a basic list of 2-3 user stories with acceptance criteria if the input allows, otherwise a placeholder structure)
    *   Example:
        *   **FR-001: [User Story Title]**
            *   As a [type of user], I want [an action] so that [a benefit/value].
            *   **Acceptance Criteria:**
                *   Criterion 1.
                *   Criterion 2.

Remember to show your reasoning process transparently if assumptions are made.
Output only the requested BRD sections in Markdown format.
"""

    try:
        # Using ChatPromptTemplate for more structured message handling
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", f"""USER'S INITIAL CONCEPT:
{user_input}

TASK:
Based on the user's initial concept, please generate the following sections for a Business Requirements Document (BRD).
Ensure you adhere to the OUTPUT STANDARDS defined in your persona, especially:
- Use Markdown with proper heading hierarchy.
- Number all requirements uniquely (e.g., FR-001 for Functional Requirements).
- For Functional Requirements, provide a basic structure or a few examples if possible, based on the input.

SECTIONS TO GENERATE:
1.  **Executive Summary**
    *   Business opportunity/problem (derived from input)
    *   Proposed solution overview (derived from input)
    *   Expected benefits (high-level, if inferable)

2.  **Vision & Scope**
    *   Product vision statement (derived from input)
    *   In-scope features (high-level list based on input)
    *   Out-of-scope items (make reasonable assumptions or state if unclear)

3.  **Functional Requirements** (Provide a basic list of 2-3 user stories with acceptance criteria if the input allows, otherwise a placeholder structure)
    *   Example:
        *   **FR-001: [User Story Title]**
            *   As a [type of user], I want [an action] so that [a benefit/value].
            *   **Acceptance Criteria:**
                *   Criterion 1.
                *   Criterion 2.

Remember to show your reasoning process transparently if assumptions are made.
Output only the requested BRD sections in Markdown format.
""")
        ])

        chain = prompt_template | llm
        response = chain.invoke({"user_input": user_input}) # Pass user_input if template uses it

        generated_content = response.content
        print("--- LLM Response Received ---")
        return generated_content
    except Exception as e:
        print(f"Error during LLM call: {e}")
        return "Error: Could not generate BRD content due to an LLM error."

if __name__ == '__main__':
    # This is for basic testing of the BRD generation function.
    # Ensure OPENAI_API_KEY is set in your environment.
    # Example: export OPENAI_API_KEY='your_key_here'
    print("Testing BRD generation function...")
    # Load .env file if it exists, for local testing
    try:
        import dotenv
        dotenv.load_dotenv()
        if os.getenv("OPENAI_API_KEY"):
            print("OpenAI API Key loaded from .env file.")
        else:
            print("Attempted to load .env, but OPENAI_API_KEY is still not set.")
    except ImportError:
        print(".env file not used as python-dotenv is not installed or import failed.")

    if not os.getenv("OPENAI_API_KEY"):
        print("Skipping BRD generation test as OPENAI_API_KEY is not set.")
    else:
        sample_input = "Develop an AI-powered chatbot for customer service that can handle product returns and answer FAQs."
        brd_output = generate_initial_brd_sections(sample_input)
        print("\n--- Generated BRD Output ---")
        print(brd_output)
        print("--- End of Test ---")
