from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import List
import pandas as pd
import io
from pypdf import PdfReader
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


router = APIRouter()

class IngestResponse(BaseModel):
    message: str
    status: str


# Optimized Chunking Strategy: Recursive Character Splitting
# 1000 chars is ~200- tokens, ideal for targeted retrieval and low cost
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n","\n"," ",""]
)


def process_csv_in_background(content: bytes):
    # Basic CSV processing for tabular data
    df = pd.read_csv(io.BytesIO(content))

    # Assume CSV has 'patient' or 'text' column
    text_col = 'patient' if 'patient' in df.columns else df.columns[0]

    docs = df[text_col].astype(str).to_list()

    final_docs = []
    final_metadata = []

    for i, doc_text in enumerate(docs):
        chunks = text_splitter.split_text(doc_text)
        for chunk in chunks:
            final_docs.append(chunk)
            meta = df.iloc[i].to_dict()
            meta['text'] = chunk
            meta['source'] = 'CSV Upload'
            final_metadata.append(meta)

    vector_store.add_documents(final_docs, final_metadata)
    print(f"Ingested {len(final_docs)} chunks from CSV")


def process_pdf_in_background(content: bytes, filename: str):
    reader = PdfReader(io.BytesIO(content))
    all_text = ""
    for page in reader.pages:
        all_text +=(page.extract_text() or "") + "\n"

    chunks = text_splitter.split_text(all_text)
    final_metadata = [{"text": chunks, "source": filename} for chunk in chunks]
    vector_store.add_documents(chunks, final_metadata)
    print(f"Ingested {len(chunks)} chunks from PDF: {filename}")



def process_docx_in_background(content: bytes, filename: str):
    doc = Document(io.BytesIO(content))
    full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

    chunks = text_splitter.split_text(full_text)
    final_metadata = [{'text': chunk, "source": filename} for chunk in chunks]

    vector_store.add_documents(chunks, final_metadata)
    print(f"Ingested {len(chunks)} chunks from DOCX: {filename}")


'''
1. API Route Definition
Creates a POST API endpoint
URL: /ingest/file
Response will follow the schema: IngestResponse

👉 Example response:

{
  "message": "Ingestion started",
  "status": "success"
}

2. Function Definition
🔹 async : Allows non-blocking operations (important for file handling)
🔹 background_tasks : FastAPI utility to run tasks after response is sent
🔹 file: UploadFile : Accepts file upload from user
👉 File(...) means: file is required
'''
@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    '''
    await tells Python: “Pause this function here until the file is read, but don’t block the entire server.”
    file.read() = asynchronous operation (takes time)
    await = wait for result without freezing everything
    '''
    content = await file.read()
    filename = file.filename

    if filename.endswith('.csv'):
        background_tasks.add_task(process_csv_in_background, content)
    elif filename.endswith('.pdf'):
        background_tasks.add_task(process_csv_in_background, content,filename)
    elif filename.endswith('.docx'):
        background_tasks.add_task(process_docx_in_background, content, filename)
    else:
        return IngestResponse(message=f"Unsupported file format", status='error')
    
    return IngestResponse(message=f"Ingestion for {filename} started in background", status='success')



    


