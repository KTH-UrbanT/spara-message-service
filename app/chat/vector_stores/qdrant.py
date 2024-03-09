import os
from app.chat.embeddings.openai import embeddings
from qdrant_client import QdrantClient
from langchain_community.vectorstores import Qdrant

''''
Qdrant implementation with free-tier cloud
'''

#fetch default environment variables
url = os.getenv("QDRANT_URL")
api_key = os.getenv("QDRANT_API_KEY")
collection_name = os.getenv("QDRANT_COLLECTION_NAME")

#construct a langchain Qdrant collection 
client = QdrantClient(host=url)
vector_store = Qdrant.construct_instance(
    embedding=embeddings, 
    url=url,
    prefer_grpc=True,
    api_key=api_key,
    collection_name=collection_name,
    )

#build qdrant retriever
def build_retriever(chat_args, k):
    search_kwargs = {
        "filter": { "pdf_id": chat_args.pdf_id },
        "k": k
    }
    return vector_store.as_retriever(
        search_kwargs=search_kwargs
    )


