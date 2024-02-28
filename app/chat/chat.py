# from langchain.chains import ConversationalRetrievalChain
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from app.chat.models import ChatArgs
# from app.chat.vector_stores.pinecone import build_retriever
from app.chat.llms.chatopenai import build_llm
# from app.chat.memories.sql_memory import build_memory

def build_chat(chat_args: ChatArgs):
    # retriever = build_retriever(chat_args)
    # llm = build_llm(chat_args)
    # prompt = PromptTemplate(template="You are a helpful assistant that can answer any questions in Ukrainian.",input_variables=["data"])
    # memory = build_memory(chat_args)

    return LLMChain(
        # llm=llm,
        # prompt=prompt
        # memory=memory,
        # retriever=retriever
    )