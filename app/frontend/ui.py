# Modify app/frontend/ui.py

import streamlit as st
import requests
import os


BACKEND_URL = os.getenv("BACKEND_URL")


def upload_document_to_backend(uploaded_file_obj):
    if uploaded_file_obj is not None:
        files = {'file': (uploaded_file_obj.name, uploaded_file_obj.getvalue(), uploaded_file_obj.type)}
        try:
            response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            st.error(f"Error uploading document: The request timed out. The document might be too large or the backend is taking a while.")
            return None
        except requests.exceptions.RequestException as e:
            st.error(f"Error uploading document: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try: st.error(f"Backend error details: {e.response.json()}")
                except ValueError: st.error(f"Backend error details: {e.response.text}")
            return None
    return None

def ask_question_to_backend(question: str):
    if not question.strip():
        st.warning("Please enter a question.")
        return None
    try:
        response = requests.post(f"{BACKEND_URL}/ask", params={'question': question}, timeout=120) # Increased timeout for potentially longer LLM chains
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"Error asking question: The request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error asking question: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try: st.error(f"Backend error details: {e.response.json()}")
            except ValueError: st.error(f"Backend error details: {e.response.text}")
        return None

def get_challenge_questions_from_backend():

    try:
        response = requests.post(f"{BACKEND_URL}/challenge", timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"Error getting challenge questions: The request timed out.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error getting challenge questions: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try: st.error(f"Backend error details: {e.response.json()}")
            except ValueError: st.error(f"Backend error details: {e.response.text}")
        return None


def evaluate_answers_at_backend(original_question: str, user_answer: str):

    if not user_answer.strip():
        return {"feedback": "Please provide an answer.", "justification": "", "is_correct": False, "error": "Empty answer"}
    payload = {"original_question": original_question, "user_answer": user_answer}
    try:
        response = requests.post(f"{BACKEND_URL}/evaluate", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "Timeout", "feedback": "Evaluation request timed out.", "justification": "", "is_correct": False}
    except requests.exceptions.RequestException as e:
        error_detail = f"Error evaluating answer: {e}"
        if hasattr(e, 'response') and e.response is not None:
            try: error_detail += f" Backend: {e.response.json()}"
            except ValueError: error_detail += f" Backend: {e.response.text}"
        return {"error": "RequestException", "feedback": error_detail, "justification": "", "is_correct": False}


def reset_session():

    keys_to_reset = [
        'document_uploaded', 'document_filename', 'document_summary',
        'error_message', 'ask_question_input', 'ask_results',
        'challenge_questions', 'user_challenge_answers',
        'challenge_evaluation_results', 'processed_doc_name', 'ask_history'
    ]
    default_values = {
        'document_uploaded': False, 'document_filename': None, 'document_summary': None,
        'error_message': None, 'ask_question_input': "", 'ask_results': None,
        'challenge_questions': None, 'user_challenge_answers': {},
        'challenge_evaluation_results': {}, 'processed_doc_name': None,
        'ask_history': []
    }
    for key in keys_to_reset:
        st.session_state[key] = default_values.get(key, None)
        if key == 'user_challenge_answers': st.session_state[key] = {}
        if key == 'challenge_evaluation_results': st.session_state[key] = {}
        if key == 'ask_history': st.session_state[key] = []
    if 'file_uploader_key' not in st.session_state:
        st.session_state.file_uploader_key = 0
    st.session_state.file_uploader_key += 1


st.set_page_config(page_title="DocuMind AI", layout="wide", initial_sidebar_state="expanded")
st.title("🧠 DocuMind AI: Intelligent Document Assistant")
st.markdown("_Upload a PDF or TXT document to unlock its secrets! This assistant uses AI to help you understand and engage with your documents._")

default_session_keys = {
    'document_uploaded': False, 'document_filename': None, 'document_summary': None,
    'error_message': None, 'ask_question_input': "", 'ask_results': None,
    'challenge_questions': None, 'user_challenge_answers': {},
    'challenge_evaluation_results': {}, 'processed_doc_name': None,
    'ask_history': [], 'file_uploader_key': 0
}
for key, default_value in default_session_keys.items():
    if key not in st.session_state:
        st.session_state[key] = default_value


with st.sidebar:

    st.header("📄 Document Operations")
    st.caption("Upload your document here and manage your session. The AI's responses are based solely on the content of the uploaded document.")
    uploaded_file = st.file_uploader(
        "Choose a PDF or TXT file",
        type=["pdf", "txt"],
        key=f"file_uploader_{st.session_state.file_uploader_key}",
        help="Supports PDF (text-based) and plain TXT files. Scanned image-based PDFs may not work well."
    )
    if st.button("Process Document", key="process_doc_btn", disabled=uploaded_file is None, use_container_width=True, help="Click to upload, extract text, and generate an initial summary."):
        if uploaded_file is not None:
            with st.spinner("🔬 Analyzing document & crafting summary..."):
                reset_session()
                st.session_state.document_filename = uploaded_file.name
                upload_response = upload_document_to_backend(uploaded_file)
                if upload_response: 
                    st.session_state.document_filename = upload_response.get("filename", uploaded_file.name)
                    st.session_state.processed_doc_name = st.session_state.document_filename
                    st.session_state.document_uploaded = True
                    if upload_response.get("summary"):
                        st.session_state.document_summary = upload_response["summary"]
                        st.success(f"Doc '{st.session_state.document_filename}' processed!")
                    elif upload_response.get("message") and "summary generation failed" in upload_response.get("message","").lower():
                        st.session_state.document_summary = "Summary generation failed."
                        st.warning(f"Doc processed, summary failed.")
                        st.session_state.error_message = upload_response.get("summary_error", "Unknown summary error.")
                    else:
                        st.session_state.document_summary = "Summary not available."
                        st.info(f"Doc processed. Summary status unknown.")
                else: 
                    st.session_state.error_message = "Failed to upload/process document. Backend call failed or timed out." 
                    st.error("Document processing failed.")
                    st.session_state.document_filename = None
                    st.session_state.processed_doc_name = None
        else:
            st.warning("Please upload a file first.") 

    st.markdown("---")
    if st.button("🔄 Reset Session & Clear Document", key="reset_session_btn", use_container_width=True, help="Clears the current document, all interactions, and resets the interface."):
        reset_session()
        st.success("Session has been reset.")
        st.experimental_rerun()
    st.markdown("---")
    with st.expander("💡 Tips for Best Results", expanded=False):
        st.markdown("- Use clear, text-based documents.\n- Ask specific questions for 'Ask Anything'.\n- The AI only knows what's in the document.\n- Ensure PDFs are text-based, not scans.")


if st.session_state.document_uploaded and st.session_state.document_filename:
    st.header(f"🔍 Exploring: `{st.session_state.document_filename}`")

    if st.session_state.document_summary:
        with st.expander("📜 Document Summary (AI-generated, ≤ 150 words)", expanded=True):
            if "Summary generation failed" in st.session_state.document_summary :
                 st.warning(st.session_state.document_summary)
                 if st.session_state.error_message and "Unknown summary error" in st.session_state.error_message :
                      st.error(f"Details: {st.session_state.error_message}")
            elif "Summary not available" in st.session_state.document_summary:
                st.info(st.session_state.document_summary)
            else:
                st.markdown(st.session_state.document_summary)

    st.markdown("---")
    st.subheader("💬 Interaction Modes")

    tab1, tab2 = st.tabs(["❓ **Ask Anything**", "🧠 **Challenge Me**"])

    with tab1:
        st.markdown("#### Pose Your Questions")
        st.caption("Get answers to your questions directly from the document's content. The AI now remembers the conversation context!") 

        col1_ask, col2_ask = st.columns([3,1])
        with col1_ask:
            question_input = st.text_input(
                "Your question:",
                key="ask_question_field",
                placeholder="e.g., What were the main findings? Then ask: Why were they significant?", 
                label_visibility="collapsed",
                help="Type a clear and specific question. You can ask follow-up questions!" 
            )
        with col2_ask:
            if st.button("💬 Get Answer", key="ask_submit", use_container_width=True):
                if question_input:
                    with st.spinner("Consulting the document (with memory)..."): 
                        st.session_state.ask_results = None
                        ask_response = ask_question_to_backend(question_input)
                        if ask_response:
                            st.session_state.ask_results = ask_response
                            history_entry = {
                                "question": question_input,
                                "answer": ask_response.get("answer", "N/A"),
                                "justification": ask_response.get("justification", "") 
                            }
                            st.session_state.ask_history.insert(0, history_entry)
                            if len(st.session_state.ask_history) > 5:
                                st.session_state.ask_history.pop()
                        else:
                            st.session_state.ask_results = {"answer": "Failed to get an answer.", "justification": ""}
                else:
                    st.warning("Please enter a question.")

        if st.session_state.ask_results:
            with st.expander("💡 Assistant's Response", expanded=True):
                st.markdown(f"##### Answer:")
                st.info(f"{st.session_state.ask_results.get('answer', 'N/A')}")

                
                justification_text = st.session_state.ask_results.get("justification", "")
                if justification_text and "Justification is part of the conversational answer" not in justification_text :
                    st.markdown(f"##### Justification from Document:")
                    st.caption(f"{justification_text}")
                else:
                    st.caption("_The answer is based on the document and conversation history._") 

                if "Error: The assistant's response was not in the expected format." in st.session_state.ask_results.get("answer",""):
                    st.warning("The assistant's response format was not as expected.")

        st.markdown("---")
        with st.expander("🕰️ Recent Q&A History (Last 5)", expanded=False):
            if not st.session_state.ask_history:
                st.caption("No questions asked yet in this session.")
            else:
                for i, entry in enumerate(st.session_state.ask_history):
                    st.markdown(f"**Q{len(st.session_state.ask_history)-i}:** {entry['question']}")
                    st.markdown(f"**A:** {entry['answer']}")
                    
                    hist_justification = entry.get('justification', '')
                    if hist_justification and "Justification is part of the conversational answer" not in hist_justification and hist_justification != "N/A":
                        st.caption(f"Justification: {hist_justification}")
                    if i < len(st.session_state.ask_history) - 1:
                        st.markdown("---")

    with tab2: 
        
        st.markdown("#### Test Your Comprehension")
        st.caption("The AI will generate questions based on the document. Answer them to test your understanding. Evaluations are also AI-generated and based on the document content.")
        if st.button("✨ Generate New Challenge Questions", key="generate_challenge_q", use_container_width=True, help="Generates 3 new questions from the document content."):
            with st.spinner("Crafting challenge questions..."):
                st.session_state.challenge_questions = None; st.session_state.user_challenge_answers = {}; st.session_state.challenge_evaluation_results = {}
                challenge_response = get_challenge_questions_from_backend()
                if challenge_response and "questions" in challenge_response and challenge_response["questions"]:
                    processed_questions = []
                    for i_cq, q_data in enumerate(challenge_response["questions"]):
                        q_id = q_data.get("id", f"q_{i_cq}")
                        if not isinstance(q_id, (str, int)): q_id = f"q_{i_cq}"
                        processed_questions.append({"id": q_id, "text": q_data.get("text", "Question text missing.")})
                    st.session_state.challenge_questions = processed_questions
                elif challenge_response and "error" in challenge_response: st.error(f"Could not generate challenge questions: {challenge_response.get('raw_response', challenge_response['error'])}")
                else: st.error("Failed to generate challenge questions or no questions returned.")
        if st.session_state.challenge_questions:
            st.markdown("---"); all_answers_provided_challenge = True
            for i_cq_disp, q_data in enumerate(st.session_state.challenge_questions):
                q_id = q_data["id"]; q_text = q_data["text"]
                st.markdown(f"##### Question {i_cq_disp + 1}:"); st.markdown(q_text)
                answer = st.text_area(
                    f"Your answer for Question {i_cq_disp + 1}:",
                    value=st.session_state.user_challenge_answers.get(q_id, ""),
                    key=f"challenge_ans_{q_id}", height=100, label_visibility="collapsed",
                    help=f"Type your answer for question {i_cq_disp+1} here. The evaluation will check against the document's content."
                )
                st.session_state.user_challenge_answers[q_id] = answer
                if not answer.strip(): all_answers_provided_challenge = False
                if q_id in st.session_state.challenge_evaluation_results:
                    with st.expander(f"Show Evaluation for Question {i_cq_disp+1}", expanded=False):
                        eval_res = st.session_state.challenge_evaluation_results[q_id]
                        if eval_res.get("is_correct"): st.success(f"✔️ Correct! {eval_res.get('feedback', '')}")
                        else: st.error(f"❌ Incorrect. {eval_res.get('feedback', '')}")
                        st.caption(f"Justification: {eval_res.get('justification', 'N/A')}")
                        if "error" in eval_res and eval_res["error"] not in ["Empty answer", None]: st.warning(f"Evaluation note: {eval_res.get('feedback')}")
                st.markdown("---")
            if st.button("Submit All Answers for Evaluation", key="submit_challenge_eval", use_container_width=True, disabled=not all_answers_provided_challenge, help="All questions must be answered to enable submission."):
                if not all_answers_provided_challenge: st.warning("Please provide an answer for all questions before submitting.")
                else:
                    with st.spinner("🧑‍🏫 Evaluating your answers..."):
                        st.session_state.challenge_evaluation_results = {}
                        success_all_evals = True
                        for q_data_eval in st.session_state.challenge_questions:
                            q_id_eval = q_data_eval["id"]; original_q_text_eval = q_data_eval["text"]
                            user_ans_eval = st.session_state.user_challenge_answers.get(q_id_eval, "")
                            if not user_ans_eval.strip():
                                st.session_state.challenge_evaluation_results[q_id_eval] = {"feedback": "No answer provided.", "justification": "", "is_correct": False}
                                success_all_evals = False; continue
                            eval_response = evaluate_answers_at_backend(original_q_text_eval, user_ans_eval)
                            if eval_response:
                                st.session_state.challenge_evaluation_results[q_id_eval] = eval_response
                                if "error" in eval_response and eval_response["error"] is not None : success_all_evals = False
                            else:
                                st.session_state.challenge_evaluation_results[q_id_eval] = {"feedback": "Failed to get evaluation.", "justification": "", "is_correct": False}
                                success_all_evals = False
                        if success_all_evals: st.success("All answers evaluated!")
                        else: st.warning("Some answers could not be evaluated or an error occurred.")
            elif not all_answers_provided_challenge and st.session_state.challenge_questions :
                 st.caption("*(The 'Submit All Answers' button will be enabled once all questions are answered.)*")
else:
    st.info("👋 Welcome! Please upload and process a document to begin. Check the sidebar for tips on getting the best results.")
