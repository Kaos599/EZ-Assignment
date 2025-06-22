import os
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # 

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


gemini_api_key = os.getenv("GEMINI_API_KEY") 
if not gemini_api_key:
    raise ValueError("API key not configured. Set either GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")

# 1. Define the state for the graph
class AskAnythingState(TypedDict):
    document_text: str
    input_question: str
    chat_history: Annotated[List[BaseMessage], lambda x, y: x + y] # Append-only history
    answer: str


# 2. Initialize the LLM
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.7)

# 3. Define graph nodes
async def call_gemini_model_node(state: AskAnythingState):
    messages_for_llm = []

    system_prompt_template = (
        "You are a helpful AI assistant answering questions based ONLY on the provided document context and the conversation history. "
        "Do not use any external knowledge. If the answer is not found in the document, say so. "
        "Be concise and directly answer the question. "
        "Remember the previous turns of our conversation for context if the user refers to them. "
        "The document content is provided below."
        "\n\n--- BEGIN DOCUMENT ---\n{document_text}\n--- END DOCUMENT ---"
    )


    MAX_DOC_LENGTH_FOR_PROMPT = 100000 
    effective_document_text = state["document_text"]
    if len(effective_document_text) > MAX_DOC_LENGTH_FOR_PROMPT:
        effective_document_text = effective_document_text[:MAX_DOC_LENGTH_FOR_PROMPT] + "\n... [document truncated] ..."

    formatted_system_prompt = system_prompt_template.format(document_text=effective_document_text)
    messages_for_llm.extend(state["chat_history"])


    if not state["chat_history"]: 
        full_input_prompt = formatted_system_prompt + f"\n\nUser Question: {state['input_question']}"
        messages_for_llm.append(HumanMessage(content=full_input_prompt))
    else: 
        messages_for_llm.append(HumanMessage(content=state["input_question"]))


    ai_response_message = await llm.ainvoke(messages_for_llm)


    generated_answer = ai_response_message.content



    return {"answer": generated_answer, "chat_history": [HumanMessage(content=state["input_question"]), AIMessage(content=generated_answer)]}


# 4. Define the graph

workflow = StateGraph(AskAnythingState)
workflow.add_node("llm_call", call_gemini_model_node)
workflow.set_entry_point("llm_call")
workflow.add_edge("llm_call", END)

# Compile the graph

ask_anything_graph_app = workflow.compile(checkpointer=None) # No checkpointer for now


async def run_example():

    initial_state = AskAnythingState(
        document_text="The sky is blue. Grass is green.",
        input_question="What color is the sky?",
        chat_history=[],
        answer=""
    )

    print("--- Initial Run ---")

    # async for event in ask_anything_graph_app.astream_events(initial_state, version="v1"):
    #     kind = event["event"]
    #     if kind == "on_chat_model_stream":
    #         print(event["data"]["chunk"].content, end="")
    #     elif kind in {"on_tool_start", "on_tool_end"}:
    #         pass # Handle tool events if any
    # print()


    final_state = await ask_anything_graph_app.ainvoke(initial_state)
    print(f"Question: {initial_state['input_question']}")
    print(f"Answer: {final_state['answer']}")
    print(f"History: {final_state['chat_history']}")

    print("\n--- Second Run (with history) ---")
    second_question_state = AskAnythingState(
        document_text="The sky is blue. Grass is green. The sun is bright yellow.",
        input_question="And what about the sun?",
        chat_history=final_state['chat_history'], 
        answer=""
    )
    final_state_2 = await ask_anything_graph_app.ainvoke(second_question_state)
    print(f"Question: {second_question_state['input_question']}")
    print(f"Answer: {final_state_2['answer']}")
    print(f"History: {final_state_2['chat_history']}")

if __name__ == "__main__":
    import asyncio
   
    asyncio.run(run_example())
   
    print("graph_utils.py loaded. Example run_example() is commented out.")
