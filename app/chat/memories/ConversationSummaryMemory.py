from langchain.memory import ConversationSummaryMemory
from langchain_openai import ChatOpenAI

#Get the llm that runs in the conversationsummary memory
#TODO: re-define based on individual needs
chat = ChatOpenAI(verbose=True)
def build_summarymemory():
    return ConversationSummaryMemory(
        memory=ConversationSummaryMemory(memory_key="messages",
                                         llm=chat,  # use same llm for this memory as before
                                         return_messages=True
                                         )
    )