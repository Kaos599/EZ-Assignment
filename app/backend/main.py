# In app/backend/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List
import shutil
import os
import PyPDF2

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, environment variables should be set manually
    pass

from app.utils.gemini_utils import generate_summary # Keep existing summary util
# Remove the old Q&A util if it's fully replaced, or keep if used elsewhere (not in this plan)
# from app.utils.gemini_utils import answer_question_from_document

# LangGraph imports
from app.utils.graph_utils import ask_anything_graph_app, AskAnythingState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage # For chat history typing

# Updated document_store
document_store = {
    "filename": None,
    "text": None,
    "summary": None,
    "chat_history": [] # Initialize chat_history as an empty list
}

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI()

async def get_document_text():
    if document_store["text"] is None:
        raise HTTPException(status_code=404, detail="No document uploaded or processed yet.")
    return document_store["text"]

async def get_chat_history() -> List[BaseMessage]:
    # Ensures chat_history is always a list, even if somehow becomes None
    return document_store.get("chat_history", [])


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed_extensions = {"txt", "pdf"}
    filename = file.filename
    extension = filename.split(".")[-1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a TXT or PDF file.")

    file_path = os.path.join(UPLOADS_DIR, filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_text = ""
        if extension == "txt":
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
        elif extension == "pdf":
            try:
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    if not reader.pages:
                        os.remove(file_path)
                        raise HTTPException(status_code=400, detail="PDF file has no pages or is corrupted.")
                    for page_num in range(len(reader.pages)):
                        page = reader.pages[page_num]
                        extracted_text += page.extract_text() or ""
            except PyPDF2.errors.PdfReadError as pre:
                os.remove(file_path)
                raise HTTPException(status_code=400, detail=f"Error reading PDF (possibly encrypted or corrupted): {str(pre)}")
            except Exception as e:
                os.remove(file_path)
                raise HTTPException(status_code=500, detail=f"Error processing PDF file: {str(e)}")

        if not extracted_text.strip():
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Could not extract text from the document. The document might be empty or scanned (image-based).")

        document_store["filename"] = filename
        document_store["text"] = extracted_text
        document_store["summary"] = None
        document_store["chat_history"] = [] # Reset chat history for new document

        current_summary = None
        summary_error_detail = None
        try:
            current_summary = await generate_summary(extracted_text)
            document_store["summary"] = current_summary
        except HTTPException as e:
            print(f"HTTPException generating summary for {filename}: {e.detail}")
            summary_error_detail = e.detail
        except Exception as e:
            print(f"Unexpected error generating summary for {filename}: {str(e)}")
            summary_error_detail = str(e)

        if current_summary:
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Document uploaded, processed, and summarized successfully.",
                    "filename": filename,
                    "summary": current_summary
                }
            )
        else:
            return JSONResponse(
                status_code=207,
                content={
                    "message": "Document uploaded and text extracted, but summary generation failed.",
                    "filename": filename,
                    "text_extract_status": "Success",
                    "summary_status": "Failed",
                    "summary_error": summary_error_detail or "Unknown error during summary generation."
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during upload: {str(e)}")
    finally:
        if file and hasattr(file, 'file') and not file.file.closed:
             file.file.close()


@app.post("/ask")
async def ask_question_endpoint(
    question: str, # Expecting question as a query parameter or form data
    doc_text: str = Depends(get_document_text),
    current_chat_history: List[BaseMessage] = Depends(get_chat_history)
):
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Prepare state for LangGraph
    # Minimal comments: State preparation for graph.
    graph_input_state = AskAnythingState(
        document_text=doc_text,
        input_question=question,
        chat_history=current_chat_history, # Pass current history
        answer="" # Placeholder for the answer to be filled by the graph
    )

    try:
        # Minimal comments: Graph invocation.
        final_graph_state = await ask_anything_graph_app.ainvoke(graph_input_state)

        # Update the global document_store with the new chat history from the graph
        # The graph itself appends to the history list passed in its state.
        # The final_graph_state['chat_history'] will contain the full updated history.
        document_store["chat_history"] = final_graph_state.get("chat_history", [])

        # For now, the response structure from /ask will just be the answer.
        # Justification is part of the conversational flow but not explicitly structured out here.
        # The prompt to the LLM in graph_utils asks it to be concise and answer directly.
        return JSONResponse(content={
            "answer": final_graph_state.get("answer", "No answer generated."),
            "justification": "Justification is part of the conversational answer. Review history for full context."
            # Placeholder for justification. LangGraph's primary role here is memory.
            # We might need to adjust graph_utils or add another LLM call if structured justification is critical *and separate* from the answer.
        })
    except Exception as e:
        # Catch potential errors from graph invocation
        print(f"Error during LangGraph invocation in /ask endpoint: {e}")
        # Consider if any specific error details should be hidden from the client
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your question with the AI graph: {str(e)}")


@app.get("/summary")
async def get_summary_endpoint():
    # ... (summary endpoint remains the same)
    if document_store["text"] is None:
         raise HTTPException(status_code=404, detail="No document uploaded yet. Please upload a document first.")
    if document_store["summary"] is None:
        raise HTTPException(status_code=404, detail="Summary not available for the current document. It might have failed during generation.")
    return JSONResponse(content={"summary": document_store["summary"], "filename": document_store["filename"]})

# Endpoints for /challenge and /evaluate remain the same as they don't use conversational memory yet
# ... (challenge and evaluate endpoint definitions)
from pydantic import BaseModel, Field
from app.utils.gemini_utils import generate_challenge_questions, evaluate_user_answer

@app.post("/challenge")
async def get_challenge_questions_endpoint(doc_text: str = Depends(get_document_text)):
    try:
        num_questions = 3
        response_data = await generate_challenge_questions(doc_text, num_questions)
        if "error" in response_data:
             raise HTTPException(status_code=500, detail=response_data.get("raw_response", response_data["error"]))
        if not response_data.get("questions") or len(response_data.get("questions", [])) != num_questions: # Check length safely
            print(f"Error: Did not receive the expected number of challenge questions. Response: {response_data}")
            raise HTTPException(status_code=500, detail=f"Could not generate the required number of challenge questions. Assistant response: {response_data.get('questions', 'No questions found.')}")
        return JSONResponse(content=response_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in /challenge endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while generating challenge questions: {str(e)}")

class EvaluationRequest(BaseModel):
    original_question: str = Field(..., min_length=1)
    user_answer: str = Field(..., min_length=1)

@app.post("/evaluate")
async def evaluate_user_answer_endpoint(request_data: EvaluationRequest, doc_text: str = Depends(get_document_text)):
    try:
        response_data = await evaluate_user_answer(doc_text, request_data.original_question, request_data.user_answer)
        if "error" in response_data:
             raise HTTPException(status_code=500, detail=response_data.get("raw_response", response_data["error"]))
        return JSONResponse(content=response_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error in /evaluate endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while evaluating the answer: {str(e)}")

@app.get("/")
async def read_root():
    return {"message": "Backend is running. Current document: " + str(document_store.get("filename"))}

if __name__ == "__main__":
    import uvicorn
    # Get the host and port from environment variables, with defaults
    HOST = os.getenv("BACKEND_HOST")
    PORT = int(os.getenv("BACKEND_PORT"))
    
    print(f"Attempting to run backend on {HOST}:{PORT}. Ensure GEMINI_API_KEY is set in your environment.")
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY is not set. Gemini API calls will fail.")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True, factory=False, app_dir="app/backend")
