from langchain.chat_models import ChatOpenAI

def build_llm(chat_args):
    return ChatOpenAI() #TODO: possibly add streaming=chat_args.streaming