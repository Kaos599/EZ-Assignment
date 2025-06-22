# In app/backend/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List
import shutil
import os
import PyPDF2
import uuid
from contextlib import asynccontextmanager

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
   
    pass

from app.utils.gemini_utils import generate_summary 



from app.utils.graph_utils import ask_anything_graph_app, AskAnythingState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage 
from app.utils.mongo_utils import mongo_manager, init_mongodb, cleanup_mongodb

# Updated document_store
document_store = {
    "filename": None,
    "text": None,
    "summary": None,
    "chat_history": [],
    "session_id": None
}

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mongodb()
    yield
    await cleanup_mongodb()

app = FastAPI(lifespan=lifespan)

async def get_document_text():
    if document_store["text"] is None:
        raise HTTPException(status_code=404, detail="No document uploaded or processed yet.")
    return document_store["text"]

async def get_chat_history() -> List[BaseMessage]:
    # Ensures chat_history is always a list, even if somehow becomes None
    return document_store.get("chat_history", [])

def get_or_create_session_id() -> str:
    if not document_store.get("session_id"):
        document_store["session_id"] = str(uuid.uuid4())
    return document_store["session_id"]

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
        document_store["chat_history"] = []
        document_store["session_id"] = str(uuid.uuid4())

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

        await mongo_manager.store_document(
            filename=filename,
            text=extracted_text,
            summary=current_summary,
            file_path=file_path
        )

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
    question: str, 
    doc_text: str = Depends(get_document_text),
    current_chat_history: List[BaseMessage] = Depends(get_chat_history)
):
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    session_id = get_or_create_session_id()
    
    if mongo_manager.is_connected and document_store.get("filename"):
        stored_history = await mongo_manager.get_chat_history(session_id, document_store["filename"])
        if stored_history:
            current_chat_history = stored_history
            document_store["chat_history"] = stored_history


    graph_input_state = AskAnythingState(
        document_text=doc_text,
        input_question=question,
        chat_history=current_chat_history, 
        answer="" 
    )

    try:
        final_graph_state = await ask_anything_graph_app.ainvoke(graph_input_state)
        updated_history = final_graph_state.get("chat_history", [])
        document_store["chat_history"] = updated_history

        if mongo_manager.is_connected and document_store.get("filename"):
            await mongo_manager.store_chat_history(
                session_id=session_id,
                document_filename=document_store["filename"],
                chat_history=updated_history
            )


        return JSONResponse(content={
            "answer": final_graph_state.get("answer", "No answer generated."),
            "justification": "Justification is part of the conversational answer. Review history for full context."
        })
    except Exception as e:
       
        print(f"Error during LangGraph invocation in /ask endpoint: {e}")
       
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your question with the AI graph: {str(e)}")


@app.get("/summary")
async def get_summary_endpoint():
   
    if document_store["text"] is None:
         raise HTTPException(status_code=404, detail="No document uploaded yet. Please upload a document first.")
    if document_store["summary"] is None:
        raise HTTPException(status_code=404, detail="Summary not available for the current document. It might have failed during generation.")
    return JSONResponse(content={"summary": document_store["summary"], "filename": document_store["filename"]})


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

@app.get("/health")
async def health_check():
    mongo_health = await mongo_manager.health_check()
    return JSONResponse(content={
        "status": "healthy",
        "document_store": {
            "current_document": document_store.get("filename"),
            "has_text": document_store.get("text") is not None,
            "has_summary": document_store.get("summary") is not None,
            "chat_history_length": len(document_store.get("chat_history", []))
        },
        "mongodb": mongo_health
    })

@app.get("/")
async def read_root():
    return {"message": "Backend is running. Current document: " + str(document_store.get("filename"))}

if __name__ == "__main__":
    import uvicorn
   
    HOST = os.getenv("BACKEND_HOST")
    PORT = int(os.getenv("BACKEND_PORT"))
    
    print(f"Attempting to run backend on {HOST}:{PORT}. Ensure GEMINI_API_KEY is set in your environment.")
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY is not set. Gemini API calls will fail.")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True, factory=False, app_dir="app/backend")
