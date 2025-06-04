import os
import json # Added for parsing JSON in get_clarification_questions
import re
from typing import List, Optional

import tenacity # Added for retries
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
# Specific OpenAI errors for more granular handling
# Note: LangChain might also have its own versions of these, e.g., langchain_core.exceptions.RateLimitError
# For now, sticking with the direct OpenAI ones as they are already imported and handled.
from openai import APIError, RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError

from brd.prompts import (
    STRATA_BRD_PRO_PERSONA, # The core persona defining the agent's behavior and standards.
    INITIAL_BRD_SECTIONS_TASK_TEMPLATE,
    CLARIFICATION_QUESTIONS_TEMPLATE,
    REFINE_UNDERSTANDING_TEMPLATE # New import
)

# Initialize the LLM
# Global LLM instance, configured from environment variables.
# It's initialized once when the module is loaded.
llm: Optional[ChatOpenAI] = None

def initialize_llm() -> Optional[ChatOpenAI]:
    """Initialize the LLM with environment variables, handling potential errors."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not found in environment. LLM calls will fail.")
        return None
# llm: ChatOpenAI | None = None

    # Check for dummy test keys
    if api_key.startswith("dummy_") or api_key == "test_key":
        print(f"WARNING: Detected dummy API key '{api_key}'. LLM will not be functional in tests.")
        return None

    model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
    temperature_str = os.getenv("OPENAI_TEMPERATURE", "0.7")
    try:
        temperature = float(temperature_str)
    except ValueError:
        print(f"WARNING: Invalid OPENAI_TEMPERATURE value '{temperature_str}'. Defaulting to 0.7.")
        temperature = 0.7

    try:
        llm_instance = ChatOpenAI(model=model_name, temperature=temperature, openai_api_key=api_key)
        print(f"INFO: LLM initialized with model: {model_name}, temperature: {temperature}.")
        return llm_instance
    except (AuthenticationError, APIError) as e:
        print(f"ERROR: Failed to initialize LLM. {type(e).__name__}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error initializing LLM. {type(e).__name__}: {e}")
        return None

# Initialize the LLM
llm = initialize_llm()
# if os.getenv("OPENAI_API_KEY"):
#     model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
#     temperature_str = os.getenv("OPENAI_TEMPERATURE", "0.7")
#     try:
#         temperature = float(temperature_str)
#     except ValueError:
#         print(f"WARNING: Invalid OPENAI_TEMPERATURE value '{temperature_str}'. Defaulting to 0.7.")
#         temperature = 0.7
#
#     llm = ChatOpenAI(model=model_name, temperature=temperature)
#     print(f"INFO: LLM initialized with model: {model_name}, temperature: {temperature}.")
# else:
#     print("WARNING: OPENAI_API_KEY not found. LLM (StrataBRD Pro agent) will not be functional.")

# Note: Consider adding retry logic (e.g., using 'tenacity') for LLM calls
#       in a production setting to handle transient network issues.

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60), # Exponential backoff starting at 2s, max 60s
    stop=stop_after_attempt(5), # Retry up to 5 times
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)), # Retry on these specific OpenAI errors
    reraise=True # Re-raise the last exception to be caught by the function's try/except
)
def generate_initial_brd_sections(llm: ChatOpenAI | None, user_input: str) -> str:
    """
    Generates initial BRD sections based on user input.

    Uses the STRATA_BRD_PRO_PERSONA and INITIAL_BRD_SECTIONS_TASK_TEMPLATE.
    Focuses on: Executive Summary, Vision & Scope, and basic Functional Requirements.
    Returns generated BRD content as a string, or an error message string if LLM fails.
    """
    if not llm:
        print("ERROR: LLM not available (OPENAI_API_KEY missing or invalid, or LLM not provided). Cannot generate BRD sections.")
        # Construct a placeholder structure based on the template for user feedback
        sections_to_generate_header = "SECTIONS TO GENERATE:"
        start_index = INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find(sections_to_generate_header)
        sections_text = "[Structure Undefined - Template Parsing Failed]"
        if start_index != -1:
            sections_text = INITIAL_BRD_SECTIONS_TASK_TEMPLATE[
                start_index + len(sections_to_generate_header):
            ].strip()
            # Clean up example for placeholder
            fr_example_text = """\
    *   Example:
        *   **FR-001: [User Story Title]**
            *   As a [type of user], I want [an action] so that [a benefit/value].
            *   **Acceptance Criteria:**
                *   Criterion 1.
                *   Criterion 2."""
            sections_text = sections_text.replace(fr_example_text, "    *   [Functional Requirements details would be generated here by LLM]")

        return f"""
####################################################################################
ERROR: LLM NOT AVAILABLE (OPENAI_API_KEY missing or invalid).
LLM was not called. Cannot generate BRD sections.
This is a placeholder output.
Input received: "{user_input[:150]}..."

If LLM were available, it would attempt to generate sections like:
{sections_text}
####################################################################################
"""

    print(f"--- Calling LLM for BRD Generation with input: {user_input[:100]}... ---")

    try:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        ])

        chain = prompt_template | llm
        response = chain.invoke({"user_input": user_input})

        generated_content = response.content
        print("--- LLM Response Received for BRD Generation ---")
        return generated_content
    except AuthenticationError as e:
        print(f"ERROR: OpenAI AuthenticationError during BRD generation: {e}. Check your API key.")
        return "Error: LLM authentication failed. Please check your API key. BRD generation could not be completed."
    except RateLimitError as e:
        print(f"ERROR: OpenAI RateLimitError during BRD generation: {e}. You might be exceeding your quota or rate limits.")
        return "Error: LLM rate limit exceeded. Please try again later or check your OpenAI plan. BRD generation could not be completed."
    except (APITimeoutError, APIConnectionError) as e:
        error_type = type(e).__name__
        print(f"ERROR: OpenAI {error_type} during BRD generation: {e}. Check your network connection or OpenAI status.")
        return f"Error: LLM connection issue ({error_type}). Please check your network or try again later. BRD generation could not be completed."
    except APIError as e: # Catch other/general OpenAI API errors
        error_type = type(e).__name__
        print(f"ERROR: OpenAI APIError ({error_type}) during BRD generation: {e}.")
        return f"Error: An OpenAI API issue occurred ({error_type}) while generating BRD content. BRD generation could not be completed."
    except Exception as e: # Catch other unexpected errors (LangChain, etc.)
        error_type = type(e).__name__
        module = getattr(type(e), '__module__', '')
        print(f"ERROR: An unexpected error ({error_type} in module '{module}') occurred during BRD generation: {e}")
        return f"Error: An unexpected issue ('{error_type}') occurred while generating BRD content. BRD generation could not be completed."


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
    reraise=True
)
def get_clarification_questions(llm: ChatOpenAI | None, current_project_summary: str, latest_user_utterance: str) -> List[str]:
    """
    Analyzes the current project summary and latest user utterance to determine if clarification
    questions are needed to draft a comprehensive BRD.
    Returns a list of questions or an empty list if no questions are needed.
    """
    if not llm:
        print("ERROR: LLM not available (OPENAI_API_KEY missing or invalid). Cannot generate clarification questions.")
        # Return a message indicating the issue for the state.
        return ["LLM_UNAVAILABLE: Could not generate clarification questions due to missing API key."]
        print("ERROR: LLM not available (OPENAI_API_KEY missing or LLM not provided). Cannot generate clarification questions.")
        # Return a default question or empty list if no LLM.
        # For now, returning an empty list and a message indicating the issue for the state.
        # It might be better for the graph to know this explicitly.
        # For now, the calling node should check if messages were added.
        return ["LLM_UNAVAILABLE: Could not generate clarification questions due to missing API key or LLM not provided."]

    print(f"--- Calling LLM for Clarification Questions. Summary: '{current_project_summary[:100]}...', Utterance: '{latest_user_utterance[:100]}...' ---")

    try:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", CLARIFICATION_QUESTIONS_TEMPLATE)
        ])

        chain = prompt_template | llm
        response = chain.invoke({
            "current_project_summary": current_project_summary,
            "latest_user_utterance": latest_user_utterance
        })

        response_content = response.content.strip()
        print(f"--- LLM Response for Clarification Questions: ---\n{response_content}")

        if response_content == "NO_QUESTIONS_NEEDED":
            print("INFO: LLM indicated no clarification questions are needed.")
            return []

        # Attempt to parse as JSON first (expected format for future prompt versions)
        try:
            # The prompt is expected to return a JSON list of strings.
            # Example: ["What is the target audience?", "What are the key success metrics?"]
            parsed_questions = json.loads(response_content)
            if isinstance(parsed_questions, list) and all(isinstance(q, str) for q in parsed_questions):
                print("INFO: Successfully parsed clarification questions from JSON response.")
                return parsed_questions
            else:
                print("WARNING: LLM response was valid JSON but not a list of strings. Falling back to text parsing.")
                # Fall through to text parsing logic
        except json.JSONDecodeError:
            print("WARNING: LLM response for clarification questions was not valid JSON. Falling back to text parsing.")
            # Fall through to text parsing logic (regex/line splitting)

        # Fallback: Regex/line splitting for current or malformed responses
        questions_found_fallback = []
        raw_lines = response_content.splitlines()
        for line in raw_lines:
            original_line_stripped = line.strip()
            if not original_line_stripped: # Skip empty or whitespace-only lines
                continue

            # Attempt to strip common list markers (e.g., "1. ", "- ")
            cleaned_line = re.sub(r"^\s*(\d+[\.\)]\s*|-\s*)", "", original_line_stripped).strip()

            if cleaned_line: # If anything remains after stripping markers
                questions_found_fallback.append(cleaned_line)

        if not questions_found_fallback and response_content != "NO_QUESTIONS_NEEDED":
             # This case means fallback parsing also failed to yield questions from a non-empty, non-"NO_QUESTIONS_NEEDED" response.
             print(f"WARNING: Fallback text parsing also failed to extract questions from response: {response_content}")
             # Return the raw response as a single question to indicate parsing failure but content availability.
             return [f"Unparsed response (fallback): {response_content}"]

        if questions_found_fallback:
            print("INFO: Extracted questions using fallback text parsing.")
            return questions_found_fallback

        # If response_content was not NO_QUESTIONS_NEEDED, not JSON, and fallback found nothing (e.g. empty strings after stripping)
        # This should be rare if the above logic is correct.
        print(f"INFO: No questions extracted after JSON and fallback parsing. Original response: {response_content}")
        return []

    except AuthenticationError as e:
        print(f"ERROR: OpenAI AuthenticationError during clarification questions: {e}.")
        return ["LLM_AUTH_ERROR: Authentication failed. Could not get clarification questions."]
    except RateLimitError as e:
        print(f"ERROR: OpenAI RateLimitError during clarification questions: {e}.")
        return ["LLM_RATE_LIMIT_ERROR: Rate limit exceeded. Could not get clarification questions."]
    except (APITimeoutError, APIConnectionError) as e:
        error_type = type(e).__name__
        print(f"ERROR: OpenAI {error_type} during clarification questions: {e}.")
        return [f"LLM_CONNECTION_ERROR: {error_type}. Could not get clarification questions."]
    except APIError as e:
        error_type = type(e).__name__
        print(f"ERROR: OpenAI APIError ({error_type}) during clarification questions: {e}.")
        return ["LLM_API_ERROR: APIError. Could not get clarification questions."]
    except Exception as e:
        error_type = type(e).__name__
        module = getattr(type(e), '__module__', '')
        print(f"ERROR: An unexpected error ({error_type} in '{module}') occurred during clarification questions: {e}")
        return [f"UNEXPECTED_ERROR: {error_type}. Could not get clarification questions."]


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
    reraise=True
)
def refine_project_understanding(llm: ChatOpenAI | None, current_summary: str, questions_asked: List[str], user_answers: str) -> str:
    """
    Refines the project understanding by synthesizing the current summary, questions asked,
    and user's answers into a new, coherent summary.
    Returns the revised project summary.
    """
    if not llm:
        print("ERROR: LLM not available (OPENAI_API_KEY missing or LLM not provided). Cannot refine project understanding.")
        # Return the original summary appended with an error message.
        return f"{current_summary}\n\n[LLM_UNAVAILABLE: Could not refine project understanding due to missing API key or LLM not provided. The above understanding is based on previous information only.]"

    print(f"--- Calling LLM for Project Understanding Refinement. ---")
    print(f"  Current Summary: '{current_summary[:100]}...'")
    # Format questions for the prompt
    formatted_questions = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions_asked) if not q.startswith("LLM_") and not q.startswith("UNEXPECTED_")]) # Filter out error placeholders
    if not formatted_questions and any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") for q in questions_asked):
        formatted_questions = "No valid questions were previously generated due to an error."
    elif not formatted_questions:
         formatted_questions = "No specific questions were previously asked or they were not recorded."


    print(f"  Questions Asked (for context):\n{formatted_questions}")
    print(f"  User Answers: '{user_answers[:100]}...'")

    try:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", STRATA_BRD_PRO_PERSONA),
            ("human", REFINE_UNDERSTANDING_TEMPLATE)
        ])

        chain = prompt_template | llm
        response = chain.invoke({
            "current_project_summary": current_summary,
            "questions_that_were_asked": formatted_questions,
            "user_answers": user_answers
        })

        revised_summary = response.content.strip()
        print(f"--- LLM Response for Refined Summary: ---\n{revised_summary[:300]}...")
        return revised_summary

    except AuthenticationError as e:
        print(f"ERROR: OpenAI AuthenticationError during understanding refinement: {e}.")
        return f"{current_summary}\n\n[LLM_AUTH_ERROR: Authentication failed. Could not refine project understanding.]"
    except RateLimitError as e:
        print(f"ERROR: OpenAI RateLimitError during understanding refinement: {e}.")
        return f"{current_summary}\n\n[LLM_RATE_LIMIT_ERROR: Rate limit exceeded. Could not refine project understanding.]"
    except (APITimeoutError, APIConnectionError) as e:
        error_type = type(e).__name__
        print(f"ERROR: OpenAI {error_type} during understanding refinement: {e}.")
        return f"{current_summary}\n\n[LLM_CONNECTION_ERROR: {error_type}. Could not refine project understanding.]"
    except APIError as e: # Catch other/general OpenAI API errors
        error_type = type(e).__name__
        print(f"ERROR: OpenAI APIError ({error_type}) during understanding refinement: {e}.")
        return f"{current_summary}\n\n[LLM_API_ERROR: APIError. Could not refine project understanding.]"
    except Exception as e: # Catch other unexpected errors
        error_type = type(e).__name__
        module = getattr(type(e), '__module__', '')
        print(f"ERROR: An unexpected error ({error_type} in '{module}') occurred during understanding refinement: {e}")
        return f"{current_summary}\n\n[UNEXPECTED_ERROR: {error_type}. Could not refine project understanding.]"


if __name__ == '__main__':
    # Standard library import for JSON parsing
    import json

    print("--- Testing BRD Agent Functions ---")
    # The .env loading should ideally be handled by the main entry point of the application (e.g., main.py)
    # For direct script testing, ensure .env is loaded if you rely on it here.
    # For this test, we'll explicitly check for the API key.

    local_llm_instance: ChatOpenAI | None = None
    if os.getenv("OPENAI_API_KEY"):
        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
        temperature_str = os.getenv("OPENAI_TEMPERATURE", "0.7")
        try:
            temperature = float(temperature_str)
        except ValueError:
            print(f"WARNING: Invalid OPENAI_TEMPERATURE value '{temperature_str}'. Defaulting to 0.7 for local test LLM.")
            temperature = 0.7
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            local_llm_instance = ChatOpenAI(model=model_name, temperature=temperature, openai_api_key=api_key)
            print(f"INFO: Local LLM instance for testing initialized with model: {model_name}, temperature: {temperature}.")
        except Exception as e:
            print(f"ERROR: Failed to initialize local_llm_instance for testing: {e}")
            local_llm_instance = None
    else:
        print("WARNING: OPENAI_API_KEY not found in environment. LLM-dependent tests will show placeholder/error messages as LLM cannot be initialized.")

    print("\n--- Test: generate_initial_brd_sections ---")
    sample_input_brd = "Develop an AI-powered chatbot for customer service that can handle product returns and answer FAQs."
    # Pass the local_llm_instance to the function
    brd_output = generate_initial_brd_sections(local_llm_instance, sample_input_brd)
    print("\nOutput from generate_initial_brd_sections:")
    print(brd_output)

    # Test logic now depends on local_llm_instance being successfully created
    if local_llm_instance:
        print("\n--- Test: get_clarification_questions (LLM instance available) ---")
        summary_test_cq = "The user wants a new e-commerce platform. It should sell books."
        utterance_test_cq = "We also need to support credit card payments and target young adults."

        print(f"\nSimulating get_clarification_questions with summary: '{summary_test_cq}' and utterance: '{utterance_test_cq}'")
        # Pass the local_llm_instance
        questions = get_clarification_questions(local_llm_instance, summary_test_cq, utterance_test_cq)

        if questions and not any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") or q.startswith("Unparsed response") for q in questions):
            print("\nGenerated Clarification Questions (Success):")
            for q_idx, q_text in enumerate(questions):
                print(f"  {q_idx+1}. {q_text}")

            print("\n--- Test: refine_project_understanding (LLM instance available, using above questions) ---")
            answers_parts = []
            for i in range(len(questions)):
                answers_parts.append(f"Answer to question {i+1} would be here.")
            answers_test = " ".join(answers_parts)
            if not answers_test: answers_test = "User provided comprehensive answers to all questions."

            # Pass the local_llm_instance
            refined_summary = refine_project_understanding(
                local_llm_instance,
                current_summary=summary_test_cq + " " + utterance_test_cq,
                questions_asked=questions,
                user_answers=answers_test
            )
            print(f"\nInitial combined summary was: {summary_test_cq} {utterance_test_cq}")
            print(f"Refined Summary is: {refined_summary}")

        elif any(q.startswith("LLM_UNAVAILABLE") for q in questions): # Should ideally not happen if local_llm_instance is not None
            print("\nClarification Questions: LLM was reported as unavailable by the function unexpectedly.")
        elif any(q.startswith("LLM_") or q.startswith("UNEXPECTED_") for q in questions):
            print(f"\nClarification Questions: Received an error message from LLM call: {questions[0]}")
        elif any(q.startswith("Unparsed response") for q in questions):
            print(f"\nClarification Questions: Could not parse LLM response, received: {questions[0]}")
        else: # Handles empty list specifically or other non-error cases
             print("\nClarification Questions: LLM indicated no clarification questions are needed or parsing yielded no questions.")
    else:
        print("\n--- Skipping LLM-dependent tests for get_clarification_questions and refine_project_understanding as LLM instance is not available. ---")
        # Test the behavior when LLM is not available by explicitly passing None
        print("\n--- Test: get_clarification_questions (LLM instance explicitly None) ---")
        questions_no_llm = get_clarification_questions(None, "Test summary", "Test utterance")
        print("\nOutput from get_clarification_questions (LLM instance None):")
        if questions_no_llm and questions_no_llm[0].startswith("LLM_UNAVAILABLE"):
            print(f"  Success: Received expected message: {questions_no_llm[0]}")
        else:
            print(f"  Unexpected output: {questions_no_llm}")

        print("\n--- Test: refine_project_understanding (LLM instance explicitly None) ---")
        refined_summary_no_llm = refine_project_understanding(None, "Initial summary.", ["Q1?"], "Answer1.")
        print("\nOutput from refine_project_understanding (LLM instance None):")
        if "[LLM_UNAVAILABLE:" in refined_summary_no_llm:
            print(f"  Success: Received expected message in summary: \n{refined_summary_no_llm}")
        else:
            print(f"  Unexpected output: {refined_summary_no_llm}")

    print("\n--- End of BRD Agent Function Tests ---")
