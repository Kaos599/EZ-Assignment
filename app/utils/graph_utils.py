import os
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # For potential future in-memory checkpoints

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, environment variables should be set manually
    pass

# Ensure API key is available for LangChain (uses GOOGLE_API_KEY)
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not gemini_api_key:
    raise ValueError("API key not configured. Set either GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")

# Set GOOGLE_API_KEY for LangChain if not already set
if not os.getenv("GOOGLE_API_KEY") and gemini_api_key:
    os.environ["GOOGLE_API_KEY"] = gemini_api_key

# 1. Define the state for the graph
class AskAnythingState(TypedDict):
    document_text: str
    input_question: str
    chat_history: Annotated[List[BaseMessage], lambda x, y: x + y] # Append-only history
    answer: str
    # No separate 'context_for_llm' in this version, document_text is used directly

# 2. Initialize the LLM
# Using gemini-1.5-flash-latest as it's fast and capable for general Q&A
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.7)

# 3. Define graph nodes
async def call_gemini_model_node(state: AskAnythingState):
    messages_for_llm = []

    # System prompt (or initial part of the first human message)
    # This prompt needs to guide the LLM to use the document and history.
    # Minimal comments: The prompt guides the AI.
    system_prompt_template = (
        "You are a helpful AI assistant answering questions based ONLY on the provided document context and the conversation history. "
        "Do not use any external knowledge. If the answer is not found in the document, say so. "
        "Be concise and directly answer the question. "
        "Remember the previous turns of our conversation for context if the user refers to them. "
        "The document content is provided below."
        "\n\n--- BEGIN DOCUMENT ---\n{document_text}\n--- END DOCUMENT ---"
    )

    # Prepare the document context. For very long docs, truncation might be needed here.
    # For now, assume document_text is manageable or add truncation if it becomes an issue.
    # Max input tokens for gemini-1.5-flash is very large, but be mindful of cost/latency.
    MAX_DOC_LENGTH_FOR_PROMPT = 100000 # Characters, a generous limit for flash model
    effective_document_text = state["document_text"]
    if len(effective_document_text) > MAX_DOC_LENGTH_FOR_PROMPT:
        effective_document_text = effective_document_text[:MAX_DOC_LENGTH_FOR_PROMPT] + "\n... [document truncated] ..."

    formatted_system_prompt = system_prompt_template.format(document_text=effective_document_text)

    # The system prompt can be the first part of the history if the model prefers that,
    # or a dedicated system message if using a model/API that supports it directly.
    # For ChatGoogleGenerativeAI, we often prepend it to the user's first message or as the first message.
    # Let's try adding it as a system-like message at the beginning of the history for the LLM.
    # LangChain messages are typically HumanMessage, AIMessage. Some models use SystemMessage.
    # We can simulate a system message by how we structure the prompt.

    # Add chat history
    # The chat_history in the state should already be a list of BaseMessage objects
    messages_for_llm.extend(state["chat_history"])

    # Add the current question as a HumanMessage, prefixed by the system prompt context
    # This is a common way to provide system instructions with Gemini via LangChain.
    if not state["chat_history"]: # If history is empty, this is the first user message
        full_input_prompt = formatted_system_prompt + f"\n\nUser Question: {state['input_question']}"
        messages_for_llm.append(HumanMessage(content=full_input_prompt))
    else: # If history exists, just add the new question
        messages_for_llm.append(HumanMessage(content=state["input_question"]))

    # Invoke the LLM
    # Minimal comments: LLM call with prepared messages.
    ai_response_message = await llm.ainvoke(messages_for_llm)

    # The response from ChatGoogleGenerativeAI is already a BaseMessage (AIMessage)
    # We just need its content for the 'answer' field in our state.
    generated_answer = ai_response_message.content

    # Update chat history (LangGraph handles accumulation via Annotated[..., lambda x, y: x + y])
    # We need to return the new human question and AI answer to be appended.
    # However, the 'chat_history' in the state is already updated by LangGraph's mechanism
    # if we correctly structure the graph to pass HumanMessage & AIMessage.
    # The state definition `Annotated[List[BaseMessage], lambda x, y: x + y]`
    # means any 'chat_history' key returned by a node will be appended to the existing one.

    return {"answer": generated_answer, "chat_history": [HumanMessage(content=state["input_question"]), AIMessage(content=generated_answer)]}


# 4. Define the graph
# Minimal comments: Graph definition with one node.
workflow = StateGraph(AskAnythingState)
workflow.add_node("llm_call", call_gemini_model_node)
workflow.set_entry_point("llm_call")
workflow.add_edge("llm_call", END)

# Compile the graph
# Minimal comments: Graph compilation.
# For now, no persistent checkpointing. MemorySaver can be used for in-memory checkpoints if needed for multi-turn within a single API call flow.
# However, for a typical request-response API endpoint, we'll manage history outside and pass it in.
# The main benefit of langgraph here is the state management and standardized component calls.
ask_anything_graph_app = workflow.compile(checkpointer=None) # No checkpointer for now

# Example usage (for testing this module directly, not for FastAPI integration yet)
async def run_example():
    # Minimal comments: Example graph execution.
    initial_state = AskAnythingState(
        document_text="The sky is blue. Grass is green.",
        input_question="What color is the sky?",
        chat_history=[],
        answer=""
    )

    print("--- Initial Run ---")
    # For a streaming response:
    # async for event in ask_anything_graph_app.astream_events(initial_state, version="v1"):
    #     kind = event["event"]
    #     if kind == "on_chat_model_stream":
    #         print(event["data"]["chunk"].content, end="")
    #     elif kind in {"on_tool_start", "on_tool_end"}:
    #         pass # Handle tool events if any
    # print()

    # For a single response object:
    final_state = await ask_anything_graph_app.ainvoke(initial_state)
    print(f"Question: {initial_state['input_question']}")
    print(f"Answer: {final_state['answer']}")
    print(f"History: {final_state['chat_history']}")

    print("\n--- Second Run (with history) ---")
    second_question_state = AskAnythingState(
        document_text="The sky is blue. Grass is green. The sun is bright yellow.", # Doc text can be passed each time
        input_question="And what about the sun?",
        chat_history=final_state['chat_history'], # Pass the updated history
        answer=""
    )
    final_state_2 = await ask_anything_graph_app.ainvoke(second_question_state)
    print(f"Question: {second_question_state['input_question']}")
    print(f"Answer: {final_state_2['answer']}")
    print(f"History: {final_state_2['chat_history']}")

if __name__ == "__main__":
    import asyncio
    # This requires GEMINI_API_KEY to be set in the environment
    # asyncio.run(run_example())
    # Commented out direct run for subtask, as it requires API key and might fail in CI
    print("graph_utils.py loaded. Example run_example() is commented out.")
