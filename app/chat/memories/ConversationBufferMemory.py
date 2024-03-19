from langchain.memory import ConversationBufferMemory, FileChatMessageHistory

def build_buffermemory(chat_args):
    return ConversationBufferMemory(
        memory_key="messages",
        chat_memory=FileChatMessageHistory("messages.json"), #TODO: store this in database, not in a json in the long run
        return_messages=True,
        #chat_memory= TODO:add sql variables here

    )
