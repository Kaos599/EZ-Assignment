# DocuMind AI: Intelligent Document Assistant 🚀

**Built for the EZ Submission Round**

DocuMind AI is a GenAI-powered assistant designed to help you interact with your documents (PDF or TXT) in a smart, conversational way. It goes beyond simple search by providing concise summaries, answering complex questions with justification, and even challenging your comprehension. With the recent integration of MongoDB, your documents and chat history are now persistently stored, ensuring a seamless and reliable experience.

## ✨ Features

*   **Document Upload:** Seamlessly upload PDF (text-based) and TXT file formats for analysis.
*   **Persistent Storage (MongoDB):** Documents and chat history are now persistently stored in MongoDB, ensuring your data is safe and accessible across sessions.
    *   **Document Storage:** Uploaded PDF/TXT file contents are stored in the `upload_data` collection.
    *   **Chat History Persistence:** All conversational interactions are saved to the `chat` collection, maintaining context for follow-up questions.
*   **Auto Summary:** Generates a concise and accurate summary (≤ 150 words) of the uploaded document, providing quick insights.
*   **Ask Anything Mode:** Engage in free-form conversations with the AI about your document. The AI provides answers with justifications, strictly based on the document's content, preventing hallucinations.
*   **Challenge Me Mode:** Test your understanding! The AI generates three logic-based or comprehension-focused questions from the document and evaluates your answers, providing detailed feedback.
*   **Contextual Understanding:** Utilizes advanced LangGraph flows to maintain conversation memory and contextual understanding, making interactions more natural and effective.
*   **User-Friendly Interface:** A clean, intuitive, and responsive web interface built with Streamlit, ensuring a smooth user experience.

## 🏗️ Architecture

The DocuMind AI application is structured into three main, interconnected components, ensuring modularity and scalability:

1.  **Backend (FastAPI):**
    *   Located in `app/backend/main.py`.
    *   Serves as the central API hub, handling all core functionalities.
    *   Manages file uploads, text extraction (using PyPDF2 for PDFs), and orchestrates the AI processing.
    *   **Now integrates directly with MongoDB** for all document and chat history persistence, managing the `document_store` with database-backed data.
    *   Key Endpoints:
        *   `/upload`: Handles file uploads, text extraction, summary generation, and **stores documents in MongoDB**.
        *   `/summary`: Retrieves the document summary.
        *   `/ask`: Processes user questions, leverages LangGraph for conversational memory, and **persists chat history in MongoDB**.
        *   `/challenge`: Generates comprehension questions.
        *   `/evaluate`: Evaluates user answers to challenge questions.
        *   `/health`: Provides a health check for the backend and MongoDB connection status.

2.  **Gemini API Utilities (`app/utils/gemini_utils.py`):**
    *   This module acts as the interface to Google's Gemini Pro API.
    *   Responsible for crafting context-rich prompts for various tasks (summarization, Q&A, question generation, evaluation).
    *   Manages requests to the Gemini API, ensuring structured JSON responses.
    *   Handles API key configuration and robust error management for all Gemini API calls.

3.  **LangGraph Utilities (`app/utils/graph_utils.py`):**
    *   Implements the core conversational memory and reasoning flow using LangGraph.
    *   Crucial for the "Ask Anything" mode, enabling the AI to remember previous turns and maintain context for follow-up questions.
    *   Integrates with the `document_store` to provide document context to the conversational AI.

4.  **MongoDB Utilities (`app/utils/mongo_utils.py`):**
    *   **New core component** responsible for all interactions with the MongoDB database.
    *   Manages connection, disconnection, and database operations.
    *   Handles document storage (`upload_data` collection), chat history (`chat` collection), and session management.
    *   Ensures data integrity and efficient retrieval with automatic indexing.

5.  **Frontend (Streamlit):**
    *   Located in `app/frontend/ui.py`.
    *   Provides a user-friendly web-based interface.
    *   Communicates with the FastAPI backend via HTTP requests.
    *   Manages UI state, file uploads, and displays AI responses and chat history.
    *   Includes features like session reset and clear user guidance.

## 📁 Project Structure

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
│       ├── gemini_utils.py # Gemini API interaction logic
│       ├── graph_utils.py  # LangGraph implementation for conversational memory
│       └── mongo_utils.py  # MongoDB database utilities
├── tests/
│   ├── backend/
│   │   ├── __init__.py
│   │   └── test_main.py    # Pytests for backend
│   └── utils/
│       ├── __init__.py
│       └── test_gemini_utils.py # Pytests for utils
├── uploads/                # Directory for temporary file uploads (created automatically)
├── .env                    # Environment variables (including MongoDB and API keys)
├── README.md               # This project documentation
└── requirements.txt        # Python dependencies
```

## 🚀 Setup and Running the Application

Follow these steps to get DocuMind AI up and running locally:

### 1. Prerequisites

*   **Python 3.8 or higher**
*   `pip` (Python package installer)

### 2. Clone the Repository

If you haven't already, clone the project repository:

```bash
git clone <repository_url>
cd <repository_directory>
```

### 3. Create a Virtual Environment (Recommended)

It's highly recommended to use a virtual environment to manage dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Dependencies

Navigate to the project's root directory (where `requirements.txt` is located) and install all required Python packages:

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the root directory of your project (if it doesn't already exist) and add the following:

```dotenv
# Google Gemini API Key
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY" # Often the same as GEMINI_API_KEY

# Backend Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8005

# MongoDB Configuration
MONGODB_URI="YOUR_MONGODB_URI"
MONGO_DB_NAME="YOUR_DB_NAME"
MONGO_CHAT_COLLECTION_NAME="YOUR_CHAT_COLLECTION_NAME"
MONGO_DATA_COLLECTION_NAME="YOUR_DATA_COLLECTION_NAME"
```

**Important:** Replace `"YOUR_GEMINI_API_KEY"` and `"YOUR_GOOGLE_API_KEY"` with your actual API keys from Google AI Studio or Google Cloud. The MongoDB URI provided is for demonstration purposes and should be replaced with your own secure connection string in a production environment.

### 6. Run the Backend Server

Open your first terminal window in the project root and start the FastAPI backend:

```bash
uvicorn app.backend.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-8005} --reload
```

You should see output similar to `Uvicorn running on http://0.0.0.0:8005`. This server will automatically reload when code changes are detected.

### 7. Run the Frontend Application

Open a **second terminal window** in the project root (while the backend is still running). Activate your virtual environment if you haven't already, then run the Streamlit frontend:

```bash
streamlit run app/frontend/ui.py
```

Streamlit will typically open the application in your default web browser automatically (usually at `http://localhost:8501`).

### 8. Using the Application

*   **Upload Document:** In the Streamlit UI, use the sidebar to upload a PDF or TXT file. The document will be processed, summarized, and its content will be stored in MongoDB.
*   **Interact with AI:** Switch between "Ask Anything" and "Challenge Me" tabs to interact with your document.
*   **Persistent Chat:** Your conversations in "Ask Anything" mode will be saved to MongoDB, allowing you to resume context even if the application restarts.
*   **Reset Session:** Use the "Reset Session" button in the sidebar to clear the current document and start a fresh interaction.

## 🧠 Reasoning Flow (Example: Ask Anything with MongoDB)

1.  **User Input (Frontend):** The user uploads a document and types a question in the "Ask Anything" tab.
2.  **API Request (Frontend to Backend):** Streamlit sends an HTTP POST request to the `/ask` endpoint of the FastAPI backend with the user's question.
3.  **Backend Processing (`main.py`):**
    *   The `/ask` endpoint receives the question.
    *   It retrieves the document text and the existing chat history (if any) associated with the current session ID from **MongoDB via `mongo_manager`**. If no history exists, a new session is initiated.
    *   The retrieved document text and chat history are used to prepare the state for the LangGraph application.
4.  **LangGraph Interaction (`graph_utils.py`):**
    *   The `ask_anything_graph_app` is invoked with the current document context, user question, and chat history.
    *   LangGraph manages the conversational flow, prompting the Gemini model with the full context (document + history).
5.  **Gemini Interaction (`gemini_utils.py`):**
    *   The `gemini_utils.py` functions construct detailed prompts, including the document text, the user's question, and instructions for the Gemini model to provide an answer and justification based *only* on the provided context.
    *   The prompt is sent to the Gemini API, and the response is parsed.
6.  **Response Handling (LangGraph -> Backend):**
    *   The Gemini model's answer is returned through LangGraph.
    *   The updated chat history (including the latest question and answer) is retrieved from the final LangGraph state.
    *   The backend then **stores this updated chat history back into MongoDB** for the current session.
7.  **Display (Frontend):** Streamlit receives the AI's answer and justification from the backend, displays it to the user, and updates the visible chat history.

This enhanced flow ensures that your conversations are not lost and the AI always has the most complete context for its responses.

## 📋 Project Status

This project is actively developed and maintained, with a focus on enhancing AI capabilities and user experience.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## 💖 Acknowledgements

*   **Google Gemini API:** For powerful conversational AI capabilities.
*   **FastAPI:** For building a robust and efficient backend API.
*   **Streamlit:** For a fantastic framework to create interactive web applications.
*   **LangChain & LangGraph:** For facilitating advanced conversational memory and agentic flows.
*   **PyPDF2:** For PDF text extraction.
*   **MongoDB & Motor:** For reliable and scalable NoSQL database persistence.
*   **The open-source community:** For countless resources and inspiration.

