# DocuMind AI: Intelligent Document Assistant

DocuMind AI is a GenAI-powered assistant that helps you understand and interact with your documents (PDF or TXT). It can provide summaries, answer your questions about the document content, and even challenge your comprehension with logic-based questions.

## Features

*   **Document Upload:** Supports PDF (text-based) and TXT file formats.
*   **Auto Summary:** Generates a concise summary (≤ 150 words) of the uploaded document.
*   **Ask Anything Mode:** Allows you to ask free-form questions about the document. The AI provides answers with justifications based on the document's content.
*   **Challenge Me Mode:**
    *   Generates three logic-based or comprehension-focused questions from the document.
    *   Evaluates your answers and provides feedback with justifications.
*   **User-Friendly Interface:** Clean and intuitive web interface built with Streamlit.

## Architecture

The application consists of three main components:

1.  **Backend (FastAPI):**
    *   Located in `app/backend/main.py`.
    *   Provides API endpoints for all core functionalities:
        *   `/upload`: Handles file uploads, text extraction (using PyPDF2 for PDFs), and initiates summary generation.
        *   `/summary`: (Primarily for internal use/direct access) Returns the document summary.
        *   `/ask`: Processes user questions against the document content.
        *   `/challenge`: Generates comprehension questions from the document.
        *   `/evaluate`: Evaluates user answers to challenge questions.
    *   Manages an in-memory `document_store` to hold the text and summary of the currently active document.

2.  **Gemini API Utilities (`app/utils/gemini_utils.py`):**
    *   This module is the bridge to Google's Gemini Pro API.
    *   It contains functions responsible for:
        *   Constructing specific prompts tailored for each task (summarization, Q&A, question generation, evaluation).
        *   Making requests to the Gemini API.
        *   Requesting and parsing JSON responses from the API for structured data (e.g., answers with justifications, lists of questions, evaluation feedback).
    *   Handles API key configuration and basic error management for Gemini API calls.

3.  **Frontend (Streamlit):**
    *   Located in `app/frontend/ui.py`.
    *   Provides a web-based interface for users to interact with the application.
    *   Communicates with the FastAPI backend via HTTP requests to perform actions.
    *   Manages UI state and user interactions (uploading files, asking questions, answering challenges).
    *   Includes features like session reset, interaction history for "Ask Anything", and user guidance.

## Project Structure

```
.
├── app/
│   ├── backend/
│   │   ├── __init__.py
│   │   └── main.py         # FastAPI backend logic
│   ├── frontend/
│   │   ├── __init__.py
│   │   └── ui.py           # Streamlit frontend UI
│   └── utils/
│       ├── __init__.py
│       └── gemini_utils.py # Gemini API interaction logic
├── tests/
│   ├── backend/
│   │   ├── __init__.py
│   │   └── test_main.py    # Pytests for backend
│   └── utils/
│       ├── __init__.py
│       └── test_gemini_utils.py # Pytests for utils
├── uploads/                # Directory for temporary file uploads (created automatically)
├── README.md               # This file
└── requirements.txt        # Python dependencies
```

## Setup and Running the Application

Follow these steps to set up and run DocuMind AI locally:

**1. Prerequisites:**

*   Python 3.8 or higher.
*   `pip` for installing Python packages.

**2. Clone the Repository (if applicable):**

```bash
git clone <repository_url>
cd <repository_directory>
```

**3. Create a Virtual Environment (Recommended):**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**4. Install Dependencies:**

Navigate to the project root directory (where `requirements.txt` is located) and run:

```bash
pip install -r requirements.txt
```

**5. Set Environment Variables:**

You need to set your Google Gemini API key as an environment variable.

*   **For Linux/macOS:**
    ```bash
    export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```
*   **For Windows (PowerShell):**
    ```powershell
    $env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```
    (Note: This sets it for the current session. For persistent storage, search for "environment variables" in Windows settings.)

Replace `"YOUR_GEMINI_API_KEY"` with your actual API key.

**6. Run the Backend Server:**

Open a terminal in the project root directory and run the FastAPI backend:

```bash
uvicorn app.backend.main:app --host 0.0.0.0 --port 8005 --reload
```

*   `--host 0.0.0.0`: Makes the server accessible on your network.
*   `--port 8000`: Runs the server on port 8000.
*   `--reload`: Enables auto-reloading when code changes (useful for development).

You should see output indicating the server is running (e.g., `Uvicorn running on http://0.0.0.0:8005`).

**7. Run the Frontend Application:**

Open a **new** terminal in the project root directory (while the backend is still running in the other terminal).

Activate your virtual environment if you haven't already:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Then, run the Streamlit frontend:

```bash
streamlit run app/frontend/ui.py
```

Streamlit will typically open the application in your default web browser automatically (usually at `http://localhost:8501`).

**8. Using the Application:**

*   Once the frontend is open in your browser, you can upload a PDF or TXT file using the sidebar.
*   Click "Process Document" to analyze it and see the summary.
*   Use the "Ask Anything" and "Challenge Me" tabs to interact with your document.
*   Use the "Reset Session" button in the sidebar to clear the current document and start fresh.

## Reasoning Flow (Example: Ask Anything)

1.  **User Input (Frontend):** The user uploads a document and types a question in the "Ask Anything" tab in the Streamlit UI.
2.  **API Request (Frontend to Backend):** Streamlit makes an HTTP POST request to the `/ask` endpoint of the FastAPI backend, sending the question. The document's text is already stored in the backend's `document_store` from the upload step.
3.  **Backend Processing (`main.py`):**
    *   The `/ask` endpoint receives the question.
    *   It retrieves the document text from the `document_store`.
    *   It calls the `answer_question_from_document` function from `gemini_utils.py`.
4.  **Gemini Interaction (`gemini_utils.py`):**
    *   `answer_question_from_document` constructs a detailed prompt. This prompt includes the document text, the user's question, and instructions for the Gemini model to answer based *only* on the document and to provide a justification in a specific JSON format (`{"answer": "...", "justification": "..."}`).
    *   It calls the lower-level `generate_text_from_gemini` function, requesting a JSON response.
    *   This function sends the prompt to the Gemini API.
5.  **Response Generation (Gemini API):** The Gemini model processes the prompt and generates the answer and justification as a JSON string.
6.  **Backend Response Handling (`gemini_utils.py` -> `main.py`):**
    *   `generate_text_from_gemini` returns the JSON string.
    *   `answer_question_from_document` parses this JSON string into a Python dictionary.
    *   The dictionary is returned to the `/ask` endpoint in `main.py`.
    *   The endpoint sends this dictionary back to the Streamlit frontend as an HTTP JSON response.
7.  **Display (Frontend):** Streamlit receives the JSON response, extracts the answer and justification, and displays them to the user. The Q&A pair is also added to the session history.

A similar flow applies to summarization, challenge question generation, and answer evaluation, each with its own specific prompt engineering and backend logic.

