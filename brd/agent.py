import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
# Removed BaseLangChainError import
# It's good practice to also be aware of specific OpenAI errors,
# though LangChain might wrap them.
from openai import APIError, RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError


from brd.prompts import STRATA_BRD_PRO_PERSONA, INITIAL_BRD_SECTIONS_TASK_TEMPLATE

# Initialize the LLM
if not os.getenv("OPENAI_API_KEY"):
    print("Warning: OPENAI_API_KEY not found in environment. LLM calls will fail.")

# TODO: Experiment with more advanced models (e.g., GPT-4) and temperature settings
#       as the agent matures. Consider making these configurable.
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)

# TODO: In a production setting, consider adding retry logic (e.g., using the 'tenacity' library)
#       for LLM calls to handle transient network issues or temporary API unavailability.

def generate_initial_brd_sections(user_input: str) -> str:
    """
    Generates a subset of BRD sections based on user input and the StrataBRD Pro persona.
    Focuses on: Executive Summary, Vision & Scope, and a basic Functional Requirements structure.
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
        print("--- LLM Response Received ---")
        return generated_content
    # Specific OpenAI errors
    except APIError as e: # Catching the base OpenAI error
        error_type = type(e).__name__
        print(f"OpenAI API Error during LLM call ({error_type}): {e}")

        # Check for specific OpenAI error types
        if isinstance(e, AuthenticationError):
            return "Error: LLM authentication failed. Please check your API key."
        elif isinstance(e, RateLimitError):
            return "Error: LLM rate limit exceeded. Please try again later or check your plan."
        elif isinstance(e, (APITimeoutError, APIConnectionError)):
            return "Error: LLM connection issue. Please check your network or try again later."
        else: # General APIError that isn't more specific from the ones above
            return f"Error: An OpenAI API issue occurred while generating BRD content ({error_type})."
    # Catch other potential errors that could be LangChain related or other unexpected issues
    except Exception as e:
        error_type = type(e).__name__
        # Check if it's an error from LangChain by looking for 'langchain' in module name, if possible
        module = getattr(type(e), '__module__', '')
        if 'langchain' in module:
            print(f"LangChain related error during LLM call ({error_type}): {e}")
            return f"Error: A LangChain operation failed while generating BRD content ({error_type})."
        else:
            print(f"An unexpected error occurred during LLM call ({error_type}): {e}")
            return "Error: An unexpected issue occurred while generating BRD content."

if __name__ == '__main__':
    print("Testing BRD generation function...")
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
        # Test specific error handling (conceptual, requires mocking to trigger)
        # print("\nTesting error handling (conceptual):")
        # try:
        #    # Mock LLM to raise openai.AuthenticationError for example
        #    pass
        # except Exception as e:
        #    print(f"Caught during test: {generate_initial_brd_sections('test error')}")

        sample_input = "Develop an AI-powered chatbot for customer service that can handle product returns and answer FAQs."
        brd_output = generate_initial_brd_sections(sample_input)
        print("\n--- Generated BRD Output ---")
        print(brd_output)
        print("--- End of Test ---")
