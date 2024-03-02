from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.chat.vector_stores.qdrant import vector_store



#create embeddings based on split documents
#TODO: need to change chunk size??

def create_embeddings_for_pdf(pdf_id: str, pdf_path: str):

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    loader = PyPDFLoader(pdf_path)
    docs = loader.load_and_split(text_splitter)

    for doc in docs:
        doc.metadata = {
            "page": doc.metadata["page"],
            "text": doc.page_content,
            "pdf_id": pdf_id
        }

    #can call this every single time since it either creates new qdrant collection, or adds to it if it exists
    vector_store.add_documents(docs)
    

