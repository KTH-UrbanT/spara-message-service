from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.prompts import MessagesPlaceholder, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.memory import ConversationSummaryMemory, FileChatMessageHistory
from dotenv import load_dotenv


from app.chat import build_chat

load_dotenv()
def my_function():

    chat = ChatOpenAI(verbose=True)

    memory = ConversationSummaryMemory(memory_key="messages",
                                       llm=chat, #use same llm for this memory as before
                                      # chat_memory=FileChatMessageHistory("messages.json"), #TODO: store this in database, not in a json in the long run
                                      return_messages=True
                                    )

    prompt = ChatPromptTemplate(
        input_variables=["user_input", "messages"],
        messages=[
            MessagesPlaceholder(variable_name="messages"),
            HumanMessagePromptTemplate.from_template("{user_input}")
        ]
    )

    chain = LLMChain(
        llm=chat,
        prompt=prompt,
        memory=memory,
        verbose=True,
    )

    while True:
        # Get user input
        user_input = input("User: ")

        result = chain.invoke(input={"user_input": user_input})

        print(result["text"])