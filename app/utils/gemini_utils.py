import os
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from fastapi import HTTPException # For raising HTTP exceptions back to FastAPI
import json # Ensure json is imported
from dotenv import load_dotenv

load_dotenv()

# Configure the Gemini API key
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set.")
    GEMINI_API_KEY = None

MODEL_NAME = os.getenv("GEMINI_MODEL_NAME")

def get_gemini_model():
    """Initializes and returns the Gemini model instance."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured. Cannot initialize model.")
    return genai.GenerativeModel(MODEL_NAME)

async def generate_text_from_gemini(prompt: str, is_json_response: bool = False) -> str:
    """
    Generic function to generate text using the Gemini API.
    If is_json_response is True, it configures the API for JSON output.
    """
    try:
        model = get_gemini_model()

        generation_config = genai.types.GenerationConfig(
            temperature=0.7 # Adjust as needed
        )

        if is_json_response:
            generation_config.response_mime_type = "application/json"
            # The prompt needs to be crafted to make the model output JSON.
            # Example: f"Extract information and respond in JSON format: {prompt}"

        response: GenerateContentResponse = await model.generate_content_async(
            contents=[prompt],
            generation_config=generation_config,
        )

        return response.text
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        # Raise an HTTPException so FastAPI can handle it and return a proper error response
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")


async def generate_summary(document_text: str, max_words: int = 150) -> str:
    """
    Generates a summary for the given document text using the Gemini API.
    """
    # Limit input length to manage token usage for summaries and overall performance
    # The exact limit might depend on the model's context window and typical document sizes.
    # 10000 characters is an arbitrary starting point.
    effective_document_text = document_text
    if len(document_text) > 20000: # Increased limit slightly
        print(f"Document text truncated for summary generation from {len(document_text)} to 20000 characters.")
        effective_document_text = document_text[:20000]


    prompt = f"""Please provide a concise summary of the following document.
The summary should be no more than {max_words} words.
Focus on the key points and main topic of the document.

Document:
---
{effective_document_text}
---

Summary:"""

    summary_text = await generate_text_from_gemini(prompt)
    return summary_text


async def generate_challenge_questions(document_text: str, num_questions: int = 3) -> dict:
    """
    Generates a specified number of logic-based or comprehension-focused questions
    from the document using the Gemini API.

    Returns a dictionary: {"questions": [{"id": 1, "text": "..."}, {"id": 2, "text": "..."}, ...]}
    """
    MAX_DOC_LENGTH_FOR_CHALLENGE = 50000 # Similar to QA, needs good context
    effective_document_text = document_text
    if len(document_text) > MAX_DOC_LENGTH_FOR_CHALLENGE:
        print(f"Document text truncated for challenge question generation from {len(document_text)} to {MAX_DOC_LENGTH_FOR_CHALLENGE} characters.")
        effective_document_text = document_text[:MAX_DOC_LENGTH_FOR_CHALLENGE]

    prompt = f"""You are a tool for creating educational challenges.
Based *only* on the content of the provided document, generate exactly {num_questions} distinct logic-based or comprehension-focused questions.
These questions should test a user's understanding of the document's content, requiring inference or careful reading.
Avoid simple keyword lookup questions.

Document:
---
{effective_document_text}
---

Please structure your response as a JSON object with a single key "questions".
The value of "questions" should be a list of JSON objects, where each object has an "id" (integer, starting from 1) and a "text" (the question itself).

Example of a good response:
{{
  "questions": [
    {{
      "id": 1,
      "text": "Based on the report's findings, what is the primary factor contributing to X, and why?"
    }},
    {{
      "id": 2,
      "text": "If the trends discussed in section 3 continue, what is a likely outcome for Y according to the document?"
    }},
    {{
      "id": 3,
      "text": "Contrast the perspectives on Z presented in the introduction and conclusion sections."
    }}
  ]
}}

Response (JSON):
"""

    raw_response_text = await generate_text_from_gemini(prompt, is_json_response=True)

    try:
        parsed_response = json.loads(raw_response_text)
        if not isinstance(parsed_response, dict) or "questions" not in parsed_response or not isinstance(parsed_response["questions"], list):
            print(f"Warning: Gemini response for challenge questions was not in the expected JSON format. Raw: {raw_response_text}")
            # Fallback: try to return raw text if parsing fails, so it can be inspected
            return {"error": "Failed to parse questions.", "raw_response": raw_response_text}

        # Validate structure of each question
        valid_questions = []
        for i, q_data in enumerate(parsed_response["questions"]):
            if isinstance(q_data, dict) and "text" in q_data:
                valid_questions.append({"id": q_data.get("id", i + 1), "text": q_data["text"]})
            else:
                # Handle malformed question object
                print(f"Warning: Malformed question object in response: {q_data}")
                valid_questions.append({"id": i + 1, "text": "Error: Malformed question data."})

        if len(valid_questions) != num_questions and not valid_questions[0].get("text","").startswith("Error"):
             print(f"Warning: Expected {num_questions} questions, but received {len(valid_questions)}. Raw: {raw_response_text}")
             # We can still return what we got, or handle it more strictly.

        return {"questions": valid_questions}

    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from Gemini for challenge questions. Raw: {raw_response_text}")
        return {"error": "Could not decode JSON response from assistant.", "raw_response": raw_response_text}
    except Exception as e:
        print(f"Unexpected error parsing challenge questions response: {e}. Raw: {raw_response_text}")
        raise HTTPException(status_code=500, detail=f"Error processing assistant's response for challenge questions: {str(e)}")


async def evaluate_user_answer(document_text: str, original_question: str, user_answer: str) -> dict:
    """
    Evaluates a user's answer to a specific question based on the document text using the Gemini API.
    Provides feedback and justification.

    Returns a dictionary: {"feedback": "...", "justification": "...", "is_correct": true/false} (example structure)
    """
    MAX_DOC_LENGTH_FOR_EVAL = 50000 # Consistent with other context-heavy operations
    effective_document_text = document_text
    if len(document_text) > MAX_DOC_LENGTH_FOR_EVAL:
        print(f"Document text truncated for answer evaluation from {len(document_text)} to {MAX_DOC_LENGTH_FOR_EVAL} characters.")
        effective_document_text = document_text[:MAX_DOC_LENGTH_FOR_EVAL]

    prompt = f"""You are an AI assistant evaluating a user's answer to a question about a document.
Your task is to:
1. Determine if the user's answer is correct based *only* on the provided document.
2. Provide brief feedback to the user.
3. Justify your evaluation with a reference to the document. If the user's answer is incorrect, explain why based on the document.

Document:
---
{effective_document_text}
---

Original Question: {original_question}
User's Answer: {user_answer}

Please structure your response as a JSON object with three keys:
- "is_correct": boolean (true if the user's answer is substantially correct based on the document, false otherwise).
- "feedback": string (a brief explanation for the user, e.g., "Correct!", "Partially correct, but you missed...", "Incorrect, because the document states...").
- "justification": string (a specific reference or explanation from the document supporting your feedback, e.g., "The document states on page X...", "This is supported by the section on Y.").

Example of a good response (if user is correct):
{{
  "is_correct": true,
  "feedback": "Excellent! Your understanding of the document's statement on X is accurate.",
  "justification": "This aligns with the information in Section 2, Paragraph 3, which states '...'"
}}

Example of a good response (if user is incorrect):
{{
  "is_correct": false,
  "feedback": "Not quite. While you mentioned Y, the document actually attributes Z to this outcome.",
  "justification": "According to the 'Discussion' section, the primary cause is Z, not Y (see paragraph 5)."
}}

Response (JSON):
"""

    raw_response_text = await generate_text_from_gemini(prompt, is_json_response=True)

    try:
        parsed_response = json.loads(raw_response_text)
        if not isinstance(parsed_response, dict) or \
           "is_correct" not in parsed_response or \
           "feedback" not in parsed_response or \
           "justification" not in parsed_response:
            print(f"Warning: Gemini response for answer evaluation was not in the expected JSON format. Raw: {raw_response_text}")
            return {"error": "Failed to parse evaluation.", "raw_response": raw_response_text, "is_correct": False, "feedback": "Error: Could not parse assistant's evaluation.", "justification": "Raw response: " + raw_response_text}

        # Ensure 'is_correct' is a boolean
        if not isinstance(parsed_response["is_correct"], bool):
            # Attempt to coerce if it's a string like "true" or "false"
            if isinstance(parsed_response["is_correct"], str):
                if parsed_response["is_correct"].lower() == "true":
                    parsed_response["is_correct"] = True
                elif parsed_response["is_correct"].lower() == "false":
                    parsed_response["is_correct"] = False
                else:
                    # If not clearly true/false string, default to false and note in feedback
                    parsed_response["feedback"] += " (Note: 'is_correct' field from AI was not a clear boolean.)"
                    parsed_response["is_correct"] = False # Default to false if ambiguous
            else: # Not a bool or recognized string
                 parsed_response["feedback"] += " (Note: 'is_correct' field from AI was not a boolean.)"
                 parsed_response["is_correct"] = False # Default to false

        return parsed_response
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from Gemini for answer evaluation. Raw: {raw_response_text}")
        return {"error": "Could not decode JSON response from assistant.", "raw_response": raw_response_text, "is_correct": False, "feedback": "Error: Assistant's evaluation was not valid JSON.", "justification": "Raw response: " + raw_response_text}
    except Exception as e:
        print(f"Unexpected error parsing evaluation response: {e}. Raw: {raw_response_text}")
        raise HTTPException(status_code=500, detail=f"Error processing assistant's evaluation response: {str(e)}")
