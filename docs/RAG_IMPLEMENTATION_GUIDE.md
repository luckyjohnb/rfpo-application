# RAG Implementation Guide

> Complete reference for Retrieval-Augmented Generation (RAG) in a Flask/SQLAlchemy application.
> Written as a standalone guide — usable in this project or any other Python web application.

---

## Table of Contents

1. [What Is RAG and Why Use It](#1-what-is-rag-and-why-use-it)
2. [Architecture Overview](#2-architecture-overview)
3. [Dependency Stack](#3-dependency-stack)
4. [Database Schema](#4-database-schema)
5. [Pipeline: Upload → Extract → Chunk → Embed → Store](#5-pipeline-upload--extract--chunk--embed--store)
6. [Search and Retrieval](#6-search-and-retrieval)
7. [AI Assistant Integration](#7-ai-assistant-integration)
8. [Flask Integration Patterns](#8-flask-integration-patterns)
9. [Configuration and Environment Variables](#9-configuration-and-environment-variables)
10. [PostgreSQL vs SQLite Considerations](#10-postgresql-vs-sqlite-considerations)
11. [Docker and Deployment Impact](#11-docker-and-deployment-impact)
12. [Existing Scaffold in This Project](#12-existing-scaffold-in-this-project)
13. [Complete Implementation Reference](#13-complete-implementation-reference)
14. [Testing](#14-testing)
15. [Performance and Scaling Notes](#15-performance-and-scaling-notes)

---

## 1. What Is RAG and Why Use It

RAG augments an AI model's answers with **your own documents**. Instead of relying solely on the model's training data, you:

1. **Retrieve** the most relevant passages from your document store
2. **Augment** the user's question with those passages as context
3. **Generate** an answer grounded in your actual data

**Use case in this application:** Users upload documents (PDFs, Word docs, spreadsheets) to RFPOs. RAG enables an AI assistant to answer questions like "What's the project budget?" or "Which vendor was recommended?" by searching the uploaded documents rather than hallucinating answers.

**Key benefit:** The AI only references information that actually exists in your documents, with traceable source citations.

---

## 2. Architecture Overview

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  User Upload │────▶│ Document Processor│────▶│   Database       │
│  (PDF, DOCX, │     │                  │     │                 │
│   XLSX, etc) │     │ 1. Extract text  │     │ UploadedFile    │
└──────────────┘     │ 2. Chunk text    │     │ DocumentChunk   │
                     │ 3. Generate      │     │ (text + vectors)│
                     │    embeddings    │     └────────┬────────┘
                     │ 4. Store chunks  │              │
                     └──────────────────┘              │
                                                       ▼
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  User Query  │────▶│  RAG Assistant   │────▶│  Vector Search  │
│  "What's the │     │                  │     │  (FAISS index)  │
│   budget?"   │     │ 1. Embed query   │     │                 │
└──────────────┘     │ 2. Find similar  │     │ Returns top-k   │
                     │    chunks        │     │ similar chunks  │
                     │ 3. Build prompt  │     └─────────────────┘
                     │ 4. Return answer │
                     └──────────────────┘
```

**Two main modules (not yet implemented):**

| Module | Purpose |
|---|---|
| `document_processor.py` | Handles upload processing: text extraction, chunking, embedding generation, storage |
| `ai_assistant_integration.py` | Handles query-time operations: embedding queries, vector search, prompt construction, answer generation |

---

## 3. Dependency Stack

### 3.1 Core RAG Dependencies

These are required for the embedding and vector search pipeline:

| Package | Version | Size Impact | Purpose |
|---|---|---|---|
| `sentence-transformers` | 2.2.2 | ~300 MB (pulls PyTorch) | Converts text to dense vector embeddings |
| `faiss-cpu` | 1.7.4 | ~15 MB | Facebook's library for fast similarity search over vectors |
| `numpy` | 1.24.3 | ~30 MB | Numerical array operations — foundation for all vector math |
| `scikit-learn` | 1.3.2 | ~50 MB | ML utilities used internally by sentence-transformers |

**Total RAG-specific footprint: ~400-500 MB** (dominated by PyTorch, which sentence-transformers requires).

### 3.2 Text Processing Dependencies

These handle tokenization and token counting:

| Package | Version | Size Impact | Purpose |
|---|---|---|---|
| `nltk` | 3.8.1 | ~15 MB (plus data downloads) | Natural language tokenization — splitting text into sentences |
| `tiktoken` | 0.5.2 | ~5 MB | OpenAI's tokenizer — counts tokens for chunk size limits |

### 3.3 Document Extraction Dependencies

These extract raw text from uploaded files (already installed in production):

| Package | Version | Purpose | File Types |
|---|---|---|---|
| `PyPDF2` | 3.0.1 | PDF text extraction | `.pdf` |
| `pymupdf` | 1.23.14 | Advanced PDF processing (better than PyPDF2 for complex layouts) | `.pdf` |
| `python-docx` | 1.1.0 | Word document extraction | `.docx` |
| `openpyxl` | 3.1.2 | Excel spreadsheet extraction | `.xlsx` |
| `python-pptx` | 0.6.23 | PowerPoint extraction | `.pptx` |
| `markdown` | 3.5.1 | Markdown processing | `.md` |
| `pandas` | 2.1.4 | Tabular data manipulation | `.csv`, `.xlsx` |

### 3.4 Requirements File Setup

**For local development** (`requirements.txt`):
```
# RAG and embeddings
sentence-transformers==2.2.2
numpy==1.24.3
scikit-learn==1.3.2
faiss-cpu==1.7.4

# Text processing
nltk==3.8.1
tiktoken==0.5.2

# Document extraction
PyPDF2==3.0.1
python-docx==1.1.0
openpyxl==3.1.2
python-pptx==0.6.23
pymupdf==1.23.14
markdown==3.5.1
pandas==2.1.4
```

**For production** (`requirements-azure.txt`): You may want to omit `sentence-transformers` and `faiss-cpu` if RAG is not active, to reduce image size. The document extraction libraries are lightweight and can remain.

### 3.5 Deep Dive: What Each Package Actually Does

#### sentence-transformers

This is the heart of the embedding pipeline. It wraps Hugging Face transformer models into a simple API that converts text strings into fixed-dimensional float vectors (embeddings).

```python
from sentence_transformers import SentenceTransformer

# Load a pre-trained model (~90 MB download on first use)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Convert text to a 384-dimensional vector
embedding = model.encode("What is the project budget?")
# Returns: numpy array of shape (384,)

# Batch encode multiple texts (much faster than one-by-one)
embeddings = model.encode([
    "The project budget is $500,000",
    "The timeline is 10 months",
    "We recommend Vendor A"
])
# Returns: numpy array of shape (3, 384)
```

**Key concepts:**
- The model maps semantically similar text to nearby vectors in 384-dimensional space
- "budget" and "cost" will produce similar vectors even though the words differ
- Model runs locally — no API calls, no API keys, no data leaves your server
- First call downloads the model weights (~90 MB) to `~/.cache/torch/sentence_transformers/`

**Common models (pick ONE):**

| Model | Dimensions | Speed | Quality | Size |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | Fast | Good | 90 MB |
| `all-mpnet-base-v2` | 768 | Medium | Better | 420 MB |
| `all-MiniLM-L12-v2` | 384 | Medium | Good+ | 120 MB |

`all-MiniLM-L6-v2` is the recommended starting point — best speed/quality tradeoff.

#### faiss-cpu

Facebook AI Similarity Search. Builds an index of vectors and finds the k most similar vectors to a query vector in milliseconds, even with millions of vectors.

```python
import faiss
import numpy as np

dimension = 384  # Must match your embedding model's output dimension
index = faiss.IndexFlatL2(dimension)  # L2 (Euclidean) distance

# Add vectors to the index
vectors = np.array(embeddings, dtype='float32')  # MUST be float32
index.add(vectors)

# Search: find 3 most similar vectors to a query
query = np.array([query_embedding], dtype='float32')
distances, indices = index.search(query, k=3)
# distances: [[0.45, 0.67, 0.89]]  — lower = more similar
# indices: [[2, 0, 1]]  — positions in the original array
```

**Key concepts:**
- `IndexFlatL2` does exact (brute-force) search — perfect for < 100K vectors
- `IndexIVFFlat` does approximate search — faster for > 100K vectors
- Index can be saved to disk and loaded back: `faiss.write_index(index, "vectors.faiss")`
- All vectors MUST be `float32` numpy arrays
- The index does NOT store your text — only vectors. You map indices back to chunks yourself.

#### numpy

Provides the array types that both sentence-transformers and faiss require. Every embedding is a numpy array.

```python
import numpy as np

# Create a vector
v = np.array([0.1, 0.2, 0.3], dtype='float32')

# Normalize a vector (useful for cosine similarity)
v_normalized = v / np.linalg.norm(v)

# Compute cosine similarity between two vectors
similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
```

#### nltk

Used specifically for **sentence tokenization** — splitting a paragraph into individual sentences before chunking.

```python
import nltk
nltk.download('punkt_tab')  # One-time download (~2 MB)

from nltk.tokenize import sent_tokenize

text = "The budget is $500K. The timeline is 10 months. We need 3 vendors."
sentences = sent_tokenize(text)
# ['The budget is $500K.', 'The timeline is 10 months.', 'We need 3 vendors.']
```

**Why nltk over simple `.split('.')`?** It handles abbreviations ("Dr.", "U.S."), decimal numbers ("$500.00"), and other edge cases that naive splitting gets wrong.

#### tiktoken

OpenAI's byte-pair encoding tokenizer. Counts how many tokens a text chunk will use, which is critical for:
- Keeping chunks within embedding model limits
- Estimating LLM prompt sizes
- Billing calculations if using OpenAI API

```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 / GPT-3.5 encoding

tokens = enc.encode("The project budget is $500,000")
print(len(tokens))  # 7 tokens

# Truncate text to a token limit
def truncate_to_tokens(text, max_tokens=512):
    tokens = enc.encode(text)
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
        return enc.decode(tokens)
    return text
```

---

## 4. Database Schema

### 4.1 UploadedFile Model

Tracks uploaded documents and their RAG processing state.

```python
class UploadedFile(db.Model):
    __tablename__ = "uploaded_files"

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.String(36), unique=True, nullable=False)     # UUID
    original_filename = db.Column(db.String(256), nullable=False)
    stored_filename = db.Column(db.String(256), nullable=False)          # UUID_originalname
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)                    # Bytes
    mime_type = db.Column(db.String(128))
    file_extension = db.Column(db.String(10))
    document_type = db.Column(db.String(255))                            # Category label
    description = db.Column(db.Text)

    # --- RAG-specific fields ---
    processing_status = db.Column(db.String(32), default="pending")      # pending | processing | completed | failed
    text_extracted = db.Column(db.Boolean, default=False)
    embeddings_created = db.Column(db.Boolean, default=False)
    chunk_count = db.Column(db.Integer, default=0)
    processing_error = db.Column(db.Text)
    processed_at = db.Column(db.DateTime)

    # --- Associations ---
    rfpo_id = db.Column(db.Integer, db.ForeignKey("rfpos.id"), nullable=False, index=True)
    uploaded_by = db.Column(db.String(64), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Relationship to chunks ---
    chunks = db.relationship("DocumentChunk", backref="file", lazy=True,
                              cascade="all, delete-orphan")
```

**Processing status state machine:**
```
pending → processing → completed
                    ↘ failed
```

When a file is uploaded, `processing_status` starts as `"pending"`. The processor sets it to `"processing"`, and on success sets `"completed"` with `text_extracted=True`, `embeddings_created=True`, and `chunk_count=N`. On failure, it sets `"failed"` with `processing_error` containing the error message.

### 4.2 DocumentChunk Model

Stores individual text chunks with their vector embeddings.

```python
class DocumentChunk(db.Model):
    __tablename__ = "document_chunks"

    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(db.String(36), unique=True, nullable=False)     # UUID
    text_content = db.Column(db.Text, nullable=False)                    # The actual text
    chunk_index = db.Column(db.Integer, nullable=False)                  # Order in document
    chunk_size = db.Column(db.Integer, nullable=False)                   # Character count

    # --- Metadata ---
    page_number = db.Column(db.Integer)                                  # For PDFs
    section_title = db.Column(db.String(256))                            # If extractable
    metadata_json = db.Column(db.Text)                                   # Additional JSON blob

    # --- Vector embedding ---
    embedding_vector = db.Column(db.Text)                                # JSON-serialized float array
    embedding_model = db.Column(db.String(128))                          # e.g. "all-MiniLM-L6-v2"

    # --- Associations ---
    file_id = db.Column(db.Integer, db.ForeignKey("uploaded_files.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Helper methods on DocumentChunk:**

```python
def set_embedding(self, vector):
    """Store embedding vector as JSON. Handles both numpy arrays and plain lists."""
    if vector is not None:
        self.embedding_vector = json.dumps(
            vector.tolist() if hasattr(vector, "tolist") else vector
        )

def get_embedding(self):
    """Retrieve embedding vector from JSON as a Python list."""
    if self.embedding_vector:
        return json.loads(self.embedding_vector)
    return None

def set_metadata(self, metadata_dict):
    """Store arbitrary metadata as JSON."""
    if metadata_dict:
        self.metadata_json = json.dumps(metadata_dict)

def get_metadata(self):
    """Retrieve metadata dict from JSON."""
    if self.metadata_json:
        return json.loads(self.metadata_json)
    return {}
```

**Why JSON for embeddings instead of a native vector column?**
- SQLite has no native vector type — JSON text is the only option
- PostgreSQL has `pgvector` extension (see Section 10), but JSON works everywhere
- Trade-off: JSON is slower for large-scale search but simpler and portable

### 4.3 SQL Schema (for recreating without SQLAlchemy)

```sql
CREATE TABLE uploaded_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id VARCHAR(36) NOT NULL UNIQUE,
    original_filename VARCHAR(256) NOT NULL,
    stored_filename VARCHAR(256) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(128),
    file_extension VARCHAR(10),
    document_type VARCHAR(255),
    description TEXT,
    processing_status VARCHAR(32) DEFAULT 'pending',
    text_extracted BOOLEAN DEFAULT 0,
    embeddings_created BOOLEAN DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    processing_error TEXT,
    rfpo_id INTEGER NOT NULL REFERENCES rfpos(id),
    uploaded_by VARCHAR(64) NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME
);

CREATE INDEX ix_uploaded_files_rfpo_id ON uploaded_files(rfpo_id);

CREATE TABLE document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id VARCHAR(36) NOT NULL UNIQUE,
    text_content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    page_number INTEGER,
    section_title VARCHAR(256),
    metadata_json TEXT,
    embedding_vector TEXT,
    embedding_model VARCHAR(128),
    file_id INTEGER NOT NULL REFERENCES uploaded_files(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. Pipeline: Upload → Extract → Chunk → Embed → Store

### 5.1 Step 1: Text Extraction

Extract raw text from each file type using the appropriate library.

```python
import PyPDF2
import fitz  # pymupdf
from docx import Document as DocxDocument
from pptx import Presentation
import openpyxl
import pandas as pd
import markdown
import os


def extract_text(file_path: str, file_extension: str) -> str:
    """Extract text content from a file based on its type.
    
    Args:
        file_path: Absolute path to the file on disk
        file_extension: Lowercase extension without dot (e.g., "pdf", "docx")
    
    Returns:
        Extracted text as a single string
    
    Raises:
        ValueError: If the file type is not supported
        FileNotFoundError: If the file doesn't exist
    """
    ext = file_extension.lower().lstrip('.')
    
    if ext == 'pdf':
        return _extract_pdf(file_path)
    elif ext == 'docx':
        return _extract_docx(file_path)
    elif ext == 'xlsx':
        return _extract_xlsx(file_path)
    elif ext == 'pptx':
        return _extract_pptx(file_path)
    elif ext == 'md':
        return _extract_markdown(file_path)
    elif ext in ('txt', 'csv'):
        return _extract_text_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def _extract_pdf(file_path: str) -> str:
    """Extract text from PDF using pymupdf (fitz) for better quality.
    Falls back to PyPDF2 if fitz fails."""
    try:
        doc = fitz.open(file_path)
        pages = []
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append(f"[Page {page_num + 1}]\n{text}")
        doc.close()
        return "\n\n".join(pages)
    except Exception:
        # Fallback to PyPDF2
        reader = PyPDF2.PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i + 1}]\n{text}")
        return "\n\n".join(pages)


def _extract_docx(file_path: str) -> str:
    """Extract text from Word documents, including tables."""
    doc = DocxDocument(file_path)
    parts = []
    
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    
    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    
    return "\n".join(parts)


def _extract_xlsx(file_path: str) -> str:
    """Extract text from Excel spreadsheets — all sheets."""
    parts = []
    
    xls = pd.ExcelFile(file_path)
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        parts.append(f"[Sheet: {sheet_name}]")
        parts.append(df.to_string(index=False))
    
    return "\n\n".join(parts)


def _extract_pptx(file_path: str) -> str:
    """Extract text from PowerPoint presentations."""
    prs = Presentation(file_path)
    slides = []
    
    for slide_num, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text)
        if texts:
            slides.append(f"[Slide {slide_num}]\n" + "\n".join(texts))
    
    return "\n\n".join(slides)


def _extract_markdown(file_path: str) -> str:
    """Extract text from Markdown — strip formatting, return plain text."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Convert to HTML then strip tags for clean text
    import re
    html = markdown.markdown(content)
    clean = re.sub(r'<[^>]+>', '', html)
    return clean


def _extract_text_file(file_path: str) -> str:
    """Read plain text and CSV files."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()
```

### 5.2 Step 2: Text Chunking

Split extracted text into overlapping chunks sized for the embedding model.

```python
import uuid
import nltk
import tiktoken

# Download nltk sentence tokenizer data (run once at startup)
nltk.download('punkt_tab', quiet=True)

from nltk.tokenize import sent_tokenize


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    tokenizer_name: str = "cl100k_base"
) -> list[dict]:
    """Split text into overlapping chunks based on token count.
    
    Strategy:
    1. Split text into sentences (preserves semantic boundaries)
    2. Group sentences into chunks up to `chunk_size` tokens
    3. Overlap by `chunk_overlap` tokens between consecutive chunks
    
    Args:
        text: Full extracted text from a document
        chunk_size: Maximum tokens per chunk (512 is good for most embedding models)
        chunk_overlap: Number of overlapping tokens between consecutive chunks
        tokenizer_name: tiktoken encoding name for token counting
    
    Returns:
        List of dicts: [{"text": str, "index": int, "char_count": int, "token_count": int}, ...]
    """
    if not text or not text.strip():
        return []
    
    enc = tiktoken.get_encoding(tokenizer_name)
    sentences = sent_tokenize(text)
    
    chunks = []
    current_sentences = []
    current_token_count = 0
    
    for sentence in sentences:
        sentence_tokens = len(enc.encode(sentence))
        
        # If a single sentence exceeds chunk_size, split it by character
        if sentence_tokens > chunk_size:
            # Flush current buffer first
            if current_sentences:
                chunk_text_content = " ".join(current_sentences)
                chunks.append({
                    "text": chunk_text_content,
                    "index": len(chunks),
                    "char_count": len(chunk_text_content),
                    "token_count": current_token_count
                })
                current_sentences = []
                current_token_count = 0
            
            # Split the long sentence into smaller pieces
            tokens = enc.encode(sentence)
            for i in range(0, len(tokens), chunk_size - chunk_overlap):
                piece = enc.decode(tokens[i:i + chunk_size])
                chunks.append({
                    "text": piece,
                    "index": len(chunks),
                    "char_count": len(piece),
                    "token_count": min(chunk_size, len(tokens) - i)
                })
            continue
        
        # If adding this sentence exceeds the limit, save current chunk
        if current_token_count + sentence_tokens > chunk_size and current_sentences:
            chunk_text_content = " ".join(current_sentences)
            chunks.append({
                "text": chunk_text_content,
                "index": len(chunks),
                "char_count": len(chunk_text_content),
                "token_count": current_token_count
            })
            
            # Keep overlap: re-include the last few sentences
            overlap_sentences = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                s_tokens = len(enc.encode(s))
                if overlap_tokens + s_tokens > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += s_tokens
            
            current_sentences = overlap_sentences
            current_token_count = overlap_tokens
        
        current_sentences.append(sentence)
        current_token_count += sentence_tokens
    
    # Don't forget the last chunk
    if current_sentences:
        chunk_text_content = " ".join(current_sentences)
        chunks.append({
            "text": chunk_text_content,
            "index": len(chunks),
            "char_count": len(chunk_text_content),
            "token_count": current_token_count
        })
    
    return chunks
```

**Why overlapping chunks?** Without overlap, a question about "budget timeline" might miss the answer if "budget" is at the end of chunk 5 and "timeline" is at the start of chunk 6. Overlap ensures context isn't split at chunk boundaries.

**Chunk size guidance:**
- `all-MiniLM-L6-v2` has a 256-token input limit, but works well with 512-token chunks (it truncates internally)
- For OpenAI `text-embedding-ada-002`: up to 8,191 tokens
- General rule: 256-512 tokens works well for most models

### 5.3 Step 3: Generate Embeddings

Convert each text chunk into a vector using sentence-transformers.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# Load model ONCE at module level (expensive operation)
_model = None
_model_name = "all-MiniLM-L6-v2"


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load the embedding model (singleton pattern)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(_model_name)
    return _model


def generate_embeddings(texts: list[str]) -> np.ndarray:
    """Generate embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
    
    Returns:
        numpy array of shape (len(texts), embedding_dim)
        For all-MiniLM-L6-v2: shape is (N, 384)
    """
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True  # L2-normalize for cosine similarity
    )
    return embeddings.astype('float32')


def generate_single_embedding(text: str) -> np.ndarray:
    """Generate embedding for a single text (used for queries)."""
    model = get_embedding_model()
    embedding = model.encode(
        text,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    return embedding.astype('float32')
```

**Performance note:** `model.encode()` with a list of texts uses batching internally and is much faster than encoding one-by-one. Always batch when possible.

**`normalize_embeddings=True`:** This L2-normalizes all vectors so that dot product equals cosine similarity. Makes FAISS `IndexFlatIP` (inner product) equivalent to cosine similarity, which is the standard similarity metric for text.

### 5.4 Step 4: Store Chunks and Embeddings

Tie it all together — process a file and persist everything.

```python
import uuid
import logging
from datetime import datetime
from models import db, UploadedFile, DocumentChunk

logger = logging.getLogger(__name__)


def process_uploaded_file(uploaded_file: UploadedFile) -> bool:
    """Full processing pipeline for a single uploaded file.
    
    1. Update status to 'processing'
    2. Extract text from the file
    3. Chunk the text
    4. Generate embeddings for all chunks
    5. Create DocumentChunk records
    6. Update UploadedFile status to 'completed'
    
    Args:
        uploaded_file: SQLAlchemy UploadedFile instance (must be in a session)
    
    Returns:
        True if processing succeeded, False if it failed
    """
    try:
        # Mark as processing
        uploaded_file.processing_status = "processing"
        db.session.commit()
        
        # Step 1: Extract text
        text = extract_text(uploaded_file.file_path, uploaded_file.file_extension)
        if not text or not text.strip():
            uploaded_file.processing_status = "failed"
            uploaded_file.processing_error = "No text content extracted"
            db.session.commit()
            return False
        
        uploaded_file.text_extracted = True
        
        # Step 2: Chunk the text
        chunks = chunk_text(text, chunk_size=512, chunk_overlap=50)
        if not chunks:
            uploaded_file.processing_status = "failed"
            uploaded_file.processing_error = "Text chunking produced no chunks"
            db.session.commit()
            return False
        
        # Step 3: Generate embeddings for all chunks at once (batched)
        chunk_texts = [c["text"] for c in chunks]
        embeddings = generate_embeddings(chunk_texts)
        
        # Step 4: Create DocumentChunk records
        for chunk_data, embedding in zip(chunks, embeddings):
            chunk = DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                text_content=chunk_data["text"],
                chunk_index=chunk_data["index"],
                chunk_size=chunk_data["char_count"],
                file_id=uploaded_file.id,
            )
            chunk.set_embedding(embedding)
            chunk.embedding_model = _model_name
            
            # Store additional metadata
            chunk.set_metadata({
                "token_count": chunk_data["token_count"],
                "source_filename": uploaded_file.original_filename,
            })
            
            db.session.add(chunk)
        
        # Step 5: Update file record
        uploaded_file.embeddings_created = True
        uploaded_file.chunk_count = len(chunks)
        uploaded_file.processing_status = "completed"
        uploaded_file.processed_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(
            f"Processed {uploaded_file.original_filename}: "
            f"{len(chunks)} chunks, embeddings created"
        )
        return True
        
    except Exception as e:
        db.session.rollback()
        uploaded_file.processing_status = "failed"
        uploaded_file.processing_error = str(e)
        db.session.commit()
        logger.error(f"Failed to process {uploaded_file.original_filename}: {e}")
        return False
```

---

## 6. Search and Retrieval

### 6.1 Building a FAISS Index

At query time, load all chunk embeddings for the relevant scope (e.g., a specific RFPO) into a FAISS index.

```python
import faiss
import numpy as np
from models import db, DocumentChunk, UploadedFile


def build_faiss_index(rfpo_id: int) -> tuple:
    """Build a FAISS index from all chunks belonging to an RFPO.
    
    Args:
        rfpo_id: ID of the RFPO to index
    
    Returns:
        Tuple of (faiss.Index, list[DocumentChunk]) — the index and the chunks
        in the same order so indices map correctly
    """
    # Get all chunks for this RFPO's files
    chunks = (
        db.session.query(DocumentChunk)
        .join(UploadedFile, DocumentChunk.file_id == UploadedFile.id)
        .filter(UploadedFile.rfpo_id == rfpo_id)
        .filter(UploadedFile.embeddings_created == True)
        .order_by(DocumentChunk.id)
        .all()
    )
    
    if not chunks:
        return None, []
    
    # Collect embeddings into a numpy array
    vectors = []
    valid_chunks = []
    for chunk in chunks:
        embedding = chunk.get_embedding()
        if embedding:
            vectors.append(embedding)
            valid_chunks.append(chunk)
    
    if not vectors:
        return None, []
    
    vectors_np = np.array(vectors, dtype='float32')
    
    # Build FAISS index
    dimension = vectors_np.shape[1]  # 384 for MiniLM
    index = faiss.IndexFlatIP(dimension)  # Inner product = cosine sim (if normalized)
    index.add(vectors_np)
    
    return index, valid_chunks
```

### 6.2 Searching Similar Chunks

```python
def search_similar_chunks(
    query: str,
    rfpo_id: int,
    top_k: int = 5,
    similarity_threshold: float = 0.3
) -> list[dict]:
    """Find the most relevant document chunks for a query.
    
    Args:
        query: Natural language question from the user
        rfpo_id: RFPO to search within
        top_k: Maximum number of results to return
        similarity_threshold: Minimum cosine similarity (0-1) to include

    Returns:
        List of dicts with keys: chunk_id, text_content, similarity_score,
        file_name, page_number, section_title
    """
    # Build index for this RFPO
    index, chunks = build_faiss_index(rfpo_id)
    if index is None:
        return []
    
    # Embed the query
    query_embedding = generate_single_embedding(query)
    query_vector = np.array([query_embedding], dtype='float32')
    
    # Search
    scores, indices = index.search(query_vector, min(top_k, len(chunks)))
    
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or score < similarity_threshold:
            continue
        
        chunk = chunks[idx]
        results.append({
            "chunk_id": chunk.chunk_id,
            "text_content": chunk.text_content,
            "similarity_score": float(score),
            "file_name": chunk.file.original_filename if chunk.file else "Unknown",
            "page_number": chunk.page_number,
            "section_title": chunk.section_title,
            "chunk_index": chunk.chunk_index,
        })
    
    return results
```

### 6.3 Caching the FAISS Index

Re-building the index on every query is wasteful. Cache it per RFPO:

```python
from functools import lru_cache
from datetime import datetime

_index_cache = {}  # rfpo_id -> (index, chunks, built_at)
INDEX_TTL_SECONDS = 300  # Rebuild every 5 minutes


def get_or_build_index(rfpo_id: int) -> tuple:
    """Get cached FAISS index or build a new one."""
    now = datetime.utcnow()
    
    if rfpo_id in _index_cache:
        index, chunks, built_at = _index_cache[rfpo_id]
        age = (now - built_at).total_seconds()
        if age < INDEX_TTL_SECONDS:
            return index, chunks
    
    index, chunks = build_faiss_index(rfpo_id)
    if index is not None:
        _index_cache[rfpo_id] = (index, chunks, now)
    
    return index, chunks


def invalidate_index(rfpo_id: int):
    """Call this after processing new files for an RFPO."""
    _index_cache.pop(rfpo_id, None)
```

---

## 7. AI Assistant Integration

This layer sits between the user's question and the LLM, injecting relevant document context.

### 7.1 RAG-Enhanced Prompting

```python
def build_rag_prompt(query: str, context_chunks: list[dict]) -> str:
    """Build a prompt that includes retrieved document context.
    
    Args:
        query: The user's original question
        context_chunks: Results from search_similar_chunks()
    
    Returns:
        A prompt string ready to send to an LLM
    """
    if not context_chunks:
        return query  # No context available, pass through
    
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        source = chunk.get("file_name", "Unknown")
        page = chunk.get("page_number")
        page_str = f" (Page {page})" if page else ""
        context_parts.append(
            f"[Source {i}: {source}{page_str}]\n{chunk['text_content']}"
        )
    
    context_text = "\n\n---\n\n".join(context_parts)
    
    prompt = f"""Answer the following question based on the provided document excerpts.
If the answer is not found in the documents, say so — do not make up information.
Cite the source number (e.g., [Source 1]) when referencing specific information.

DOCUMENT EXCERPTS:
{context_text}

QUESTION: {query}

ANSWER:"""
    
    return prompt
```

### 7.2 Full RAG Assistant Class

```python
import logging

logger = logging.getLogger(__name__)


class RAGAssistant:
    """Orchestrates RAG: retrieval + prompt construction + response."""
    
    def __init__(self, top_k: int = 5, similarity_threshold: float = 0.3):
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
    
    def enhance_message_with_rag(
        self, message: str, user_context: dict
    ) -> dict:
        """Enhance a user message with document context.
        
        Args:
            message: The user's question
            user_context: Dict with at least 'current_rfpo_id'
        
        Returns:
            Dict with keys:
            - enhanced_prompt: str — the prompt with context injected
            - context_source: str — "rag" or "none"
            - rag_context: dict — metadata about the retrieval
        """
        rfpo_id = user_context.get("current_rfpo_id")
        if not rfpo_id:
            return {
                "enhanced_prompt": message,
                "context_source": "none",
                "rag_context": None
            }
        
        # Retrieve relevant chunks
        chunks = search_similar_chunks(
            query=message,
            rfpo_id=rfpo_id,
            top_k=self.top_k,
            similarity_threshold=self.similarity_threshold
        )
        
        if not chunks:
            return {
                "enhanced_prompt": message,
                "context_source": "none",
                "rag_context": {"chunks_found": 0, "sources": [], "avg_similarity": 0}
            }
        
        # Build enhanced prompt
        enhanced = build_rag_prompt(message, chunks)
        
        # Collect metadata
        sources = list({c["file_name"] for c in chunks})
        avg_sim = sum(c["similarity_score"] for c in chunks) / len(chunks)
        
        return {
            "enhanced_prompt": enhanced,
            "context_source": "rag",
            "rag_context": {
                "chunks_found": len(chunks),
                "sources": sources,
                "avg_similarity": round(avg_sim, 3),
                "chunks": chunks  # Include for transparency/debugging
            }
        }
    
    def suggest_questions(self, rfpo_id: int, limit: int = 5) -> list[str]:
        """Suggest questions a user could ask about an RFPO's documents.
        
        Generates suggestions by looking at the most common section titles
        and document types across the RFPO's chunks.
        """
        files = (
            UploadedFile.query
            .filter_by(rfpo_id=rfpo_id, processing_status="completed")
            .all()
        )
        
        if not files:
            return ["No processed documents available for this RFPO."]
        
        suggestions = []
        doc_types = {f.document_type for f in files if f.document_type}
        filenames = [f.original_filename for f in files]
        
        # Generate contextual suggestions based on what's uploaded
        if doc_types:
            suggestions.append(f"What types of documents are attached to this RFPO?")
        
        for filename in filenames[:limit - 1]:
            suggestions.append(f"Summarize the contents of {filename}")
        
        suggestions.append("What are the key financial figures mentioned in the documents?")
        suggestions.append("Are there any risk factors mentioned across the documents?")
        
        return suggestions[:limit]
    
    def get_rfpo_summary(self, rfpo_id: int) -> dict:
        """Get a summary of RAG readiness for an RFPO."""
        files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()
        completed = [f for f in files if f.processing_status == "completed"]
        total_chunks = sum(f.chunk_count for f in completed)
        
        return {
            "file_count": len(files),
            "processed_count": len(completed),
            "ready_for_rag": len(completed),
            "failed_count": len([f for f in files if f.processing_status == "failed"]),
            "pending_count": len([f for f in files if f.processing_status == "pending"]),
            "total_chunks": total_chunks,
        }


# Singleton instance
rag_assistant = RAGAssistant()
```

---

## 8. Flask Integration Patterns

### 8.1 Background Processing on Upload

Process files asynchronously so the upload endpoint returns immediately.

```python
from threading import Thread


def process_file_background(app, file_id: int):
    """Process a file in a background thread with app context."""
    with app.app_context():
        uploaded_file = UploadedFile.query.get(file_id)
        if uploaded_file:
            process_uploaded_file(uploaded_file)


# In your upload route:
@app.route('/api/rfpo/<int:rfpo_id>/upload', methods=['POST'])
@jwt_required()
def upload_file(rfpo_id):
    file = request.files['file']
    
    # Save file, create UploadedFile record...
    uploaded_file = UploadedFile(
        file_id=str(uuid.uuid4()),
        original_filename=secure_filename(file.filename),
        # ... other fields ...
        processing_status="pending"
    )
    db.session.add(uploaded_file)
    db.session.commit()
    
    # Start background processing
    thread = Thread(
        target=process_file_background,
        args=(current_app._get_current_object(), uploaded_file.id)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "file": uploaded_file.to_dict(),
        "message": "File uploaded, processing started"
    }), 201
```

**For production at scale**, replace `Thread` with a task queue:
- **Celery** with Redis/RabbitMQ broker
- **RQ (Redis Queue)** — simpler than Celery
- **Huey** — lightweight alternative

### 8.2 Search Endpoint

```python
@app.route('/api/rfpo/<int:rfpo_id>/search', methods=['POST'])
@jwt_required()
def search_documents(rfpo_id):
    data = request.get_json()
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"success": False, "error": "Query is required"}), 400
    
    top_k = min(data.get("top_k", 5), 20)  # Cap at 20
    
    results = search_similar_chunks(
        query=query,
        rfpo_id=rfpo_id,
        top_k=top_k
    )
    
    return jsonify({
        "success": True,
        "query": query,
        "results": results,
        "result_count": len(results)
    })
```

### 8.3 Processing Status Endpoint

```python
@app.route('/api/rfpo/<int:rfpo_id>/files/status', methods=['GET'])
@jwt_required()
def file_processing_status(rfpo_id):
    files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()
    
    return jsonify({
        "success": True,
        "files": [
            {
                "file_id": f.file_id,
                "filename": f.original_filename,
                "status": f.processing_status,
                "chunk_count": f.chunk_count,
                "error": f.processing_error
            }
            for f in files
        ]
    })
```

### 8.4 Model Preloading

Load the embedding model at startup (not on first request) to avoid a 5-10 second delay:

```python
# In your Flask app factory or __init__
def create_app():
    app = Flask(__name__)
    
    # ... config ...
    
    with app.app_context():
        # Preload the embedding model
        try:
            get_embedding_model()
            app.logger.info("Embedding model loaded successfully")
        except Exception as e:
            app.logger.warning(f"Could not preload embedding model: {e}")
    
    return app
```

---

## 9. Configuration and Environment Variables

```env
# --- RAG Configuration ---

# Embedding model (must match a sentence-transformers model name)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Embedding dimension (must match the model's output)
EMBEDDING_DIMENSION=384

# Chunking parameters
CHUNK_SIZE=512           # Max tokens per chunk
CHUNK_OVERLAP=50         # Overlap tokens between chunks

# Search parameters
RAG_TOP_K=5              # Default number of results to return
RAG_SIMILARITY_THRESHOLD=0.3  # Minimum similarity score (0.0-1.0)

# FAISS index cache TTL (seconds)
RAG_INDEX_TTL=300

# Enable/disable RAG processing (set to false to skip processing on upload)
RAG_ENABLED=true

# NLTK data directory (optional — defaults to ~/nltk_data)
NLTK_DATA=/app/nltk_data
```

**Config class integration:**
```python
import os

class RAGConfig:
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
    RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))
    RAG_INDEX_TTL = int(os.getenv("RAG_INDEX_TTL", "300"))
    RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
```

---

## 10. PostgreSQL vs SQLite Considerations

### SQLite (Local Development)

- Embeddings stored as JSON text in `embedding_vector` column
- Search requires loading ALL vectors into Python/FAISS
- Works fine for small datasets (< 10K chunks)
- No extensions needed

### PostgreSQL with pgvector (Production)

For production workloads, PostgreSQL's **pgvector** extension provides native vector storage and similarity search directly in SQL.

**Setup:**
```sql
-- Enable the extension (requires superuser or rds_superuser)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add a native vector column (instead of JSON text)
ALTER TABLE document_chunks ADD COLUMN embedding vector(384);

-- Create an index for fast similarity search
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**SQLAlchemy integration with pgvector:**
```python
# pip install pgvector

from pgvector.sqlalchemy import Vector

class DocumentChunk(db.Model):
    __tablename__ = "document_chunks"
    
    # ... other columns ...
    
    # Native vector column (PostgreSQL only)
    embedding = db.Column(Vector(384))  # Replace embedding_vector Text column
```

**Search directly in SQL (no FAISS needed):**
```python
from sqlalchemy import text

def search_chunks_pgvector(query_embedding, rfpo_id, top_k=5):
    """Search using pgvector's cosine distance operator."""
    embedding_str = str(query_embedding.tolist())
    
    results = db.session.execute(text("""
        SELECT dc.*, uf.original_filename,
               1 - (dc.embedding <=> :query_vec) AS similarity
        FROM document_chunks dc
        JOIN uploaded_files uf ON dc.file_id = uf.id
        WHERE uf.rfpo_id = :rfpo_id
          AND uf.embeddings_created = true
        ORDER BY dc.embedding <=> :query_vec
        LIMIT :top_k
    """), {
        "query_vec": embedding_str,
        "rfpo_id": rfpo_id,
        "top_k": top_k
    })
    
    return results.fetchall()
```

**When to use pgvector vs FAISS:**

| Factor | FAISS (in-memory) | pgvector (in-database) |
|---|---|---|
| Setup complexity | No extensions needed | Requires pgvector extension |
| < 10K vectors | Identical performance | Identical performance |
| 10K-1M vectors | Faster search | Slightly slower, but no memory issues |
| > 1M vectors | Needs disk-backed index | Handles natively with IVFFlat index |
| Portability | Works with any DB | PostgreSQL only |
| Persistence | Must rebuild index on restart | Index persists in DB |
| Filtering | Must filter in Python after search | Can filter in WHERE clause during search |
| Transactions | No ACID | Full ACID compliance |

**Recommendation:** Start with FAISS + JSON storage (works everywhere). Migrate to pgvector when you exceed ~50K chunks or need SQL-level filtering during search.

### Dual-Mode Pattern

Support both backends transparently:

```python
def search_similar_chunks(query, rfpo_id, top_k=5, similarity_threshold=0.3):
    """Auto-selects search backend based on database type."""
    db_url = os.getenv("DATABASE_URL", "")
    
    if db_url.startswith("postgresql") and _pgvector_available():
        return _search_pgvector(query, rfpo_id, top_k, similarity_threshold)
    else:
        return _search_faiss(query, rfpo_id, top_k, similarity_threshold)
```

---

## 11. Docker and Deployment Impact

### Image Size

The RAG dependencies add significant weight to Docker images:

| Component | Size |
|---|---|
| PyTorch (pulled by sentence-transformers) | ~300 MB |
| sentence-transformers + models | ~100 MB |
| faiss-cpu | ~15 MB |
| scikit-learn | ~50 MB |
| nltk + data | ~20 MB |
| **Total RAG overhead** | **~500 MB** |

A typical Flask API image is ~200 MB. Adding RAG makes it ~700 MB.

### Dockerfile Additions

```dockerfile
# Install nltk data at build time (not runtime)
RUN python -c "import nltk; nltk.download('punkt_tab', download_dir='/app/nltk_data')"
ENV NLTK_DATA=/app/nltk_data

# Pre-download the embedding model at build time (optional but recommended)
# This avoids a ~90 MB download on first request
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Selective Installation

Only install RAG deps where needed. In a 3-service architecture:

| Service | Needs RAG deps? | Why |
|---|---|---|
| API | Yes | Processes uploads, handles search queries |
| Admin Panel | No | Direct DB access, no RAG operations |
| User App | No | Calls API for everything |

Create a separate requirements file:

```
# requirements-rag.txt
sentence-transformers==2.2.2
faiss-cpu==1.7.4
numpy==1.24.3
scikit-learn==1.3.2
nltk==3.8.1
tiktoken==0.5.2
```

In Dockerfile.api:
```dockerfile
COPY requirements-azure.txt .
COPY requirements-rag.txt .
RUN pip install --no-cache-dir -r requirements-azure.txt -r requirements-rag.txt
```

### Memory Requirements

- Loading `all-MiniLM-L6-v2`: ~200 MB RAM
- FAISS index: ~1.5 KB per vector (so 10K chunks ≈ 15 MB)
- Background processing: 1 file at a time uses ~500 MB peak during embedding generation

**Container memory limits:** Set at least **1 GB** for the API container if RAG is active. 2 GB recommended for safety.

---

## 12. Existing Scaffold in This Project

### What's Already Built

| Component | Location | Status |
|---|---|---|
| `UploadedFile` model with RAG fields | [models.py](../models.py) lines 406-462 | Complete |
| `DocumentChunk` model | [models.py](../models.py) lines 466-530 | Complete |
| Test file showing intended API | [tests/test_rag_functionality.py](../tests/test_rag_functionality.py) | Complete (but tests can't run) |
| Document extraction deps | `requirements-azure.txt` | Installed |
| RAG/embedding deps | `requirements.txt` | Listed but NOT in production |
| File upload + UploadedFile creation | Admin panel + API routes | Working |

### What's NOT Built

| Component | Planned Location | Description |
|---|---|---|
| `document_processor.py` | Root directory | Text extraction + chunking + embedding pipeline |
| `ai_assistant_integration.py` | Root directory | RAG search + prompt enhancement + LLM integration |
| API search endpoint | `api/rfpo_routes.py` | `POST /api/rfpo/<id>/search` |
| Processing status endpoint | `api/rfpo_routes.py` | `GET /api/rfpo/<id>/files/status` |
| Background processing trigger | Upload routes | Thread/queue to process files after upload |
| NLTK data download in Docker | `Dockerfile.api` | `RUN python -c "import nltk; ..."` |
| Model pre-download in Docker | `Dockerfile.api` | `RUN python -c "from sentence_transformers ..."` |
| RAG environment variables | `.env` | `EMBEDDING_MODEL`, `CHUNK_SIZE`, etc. |
| Frontend search UI | Templates | A search box and results display |

### Current State of Production Data

Production files exist in `uploaded_files` with:
- `processing_status = 'pending'`
- `embeddings_created = False`
- `chunk_count = 0`

No `document_chunks` records exist. Files are uploaded and tracked, but never processed for RAG.

---

## 13. Complete Implementation Reference

### Putting It All Together: `document_processor.py`

This is a complete, ready-to-use module that you can drop into the project:

```python
#!/usr/bin/env python3
"""
Document Processor for RAG Pipeline

Handles: text extraction → chunking → embedding → storage
Uses: sentence-transformers, FAISS, nltk, tiktoken, PyPDF2, pymupdf, python-docx, etc.

Usage:
    from document_processor import document_processor
    
    # Process a file (call within Flask app context)
    success = document_processor.process_uploaded_file(uploaded_file)
    
    # Search for relevant chunks
    results = document_processor.search_similar_chunks("What is the budget?", rfpo_id=1)
"""
import json
import logging
import os
import uuid
from datetime import datetime

import faiss
import numpy as np
import nltk
import tiktoken

nltk.download('punkt_tab', quiet=True)
from nltk.tokenize import sent_tokenize
from sentence_transformers import SentenceTransformer

from models import db, UploadedFile, DocumentChunk

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document processing and RAG search."""
    
    def __init__(self):
        self._model = None
        self._model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
        self._chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        self._top_k = int(os.getenv("RAG_TOP_K", "5"))
        self._threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))
        self._tokenizer = tiktoken.get_encoding("cl100k_base")
        self._index_cache = {}
        self._index_ttl = int(os.getenv("RAG_INDEX_TTL", "300"))
    
    # ── Model Management ──────────────────────────────────────────────
    
    def get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            logger.info(f"Loaded embedding model: {self._model_name}")
        return self._model
    
    # ── Text Extraction ───────────────────────────────────────────────
    
    def extract_text(self, file_path: str, extension: str) -> str:
        ext = extension.lower().lstrip('.')
        extractors = {
            'pdf': self._extract_pdf,
            'docx': self._extract_docx,
            'xlsx': self._extract_xlsx,
            'pptx': self._extract_pptx,
            'md': self._extract_markdown,
            'txt': self._extract_text,
            'csv': self._extract_text,
        }
        extractor = extractors.get(ext)
        if not extractor:
            raise ValueError(f"Unsupported file type: .{ext}")
        return extractor(file_path)
    
    def _extract_pdf(self, path):
        try:
            import fitz
            doc = fitz.open(path)
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append(f"[Page {i+1}]\n{text}")
            doc.close()
            return "\n\n".join(pages)
        except ImportError:
            import PyPDF2
            reader = PyPDF2.PdfReader(path)
            return "\n\n".join(
                f"[Page {i+1}]\n{p.extract_text() or ''}"
                for i, p in enumerate(reader.pages)
                if (p.extract_text() or '').strip()
            )
    
    def _extract_docx(self, path):
        from docx import Document
        doc = Document(path)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                t = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                if t:
                    parts.append(t)
        return "\n".join(parts)
    
    def _extract_xlsx(self, path):
        import pandas as pd
        parts = []
        for sheet in pd.ExcelFile(path).sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            parts.append(f"[Sheet: {sheet}]\n{df.to_string(index=False)}")
        return "\n\n".join(parts)
    
    def _extract_pptx(self, path):
        from pptx import Presentation
        prs = Presentation(path)
        slides = []
        for i, slide in enumerate(prs.slides, 1):
            texts = [s.text for s in slide.shapes if hasattr(s, 'text') and s.text.strip()]
            if texts:
                slides.append(f"[Slide {i}]\n" + "\n".join(texts))
        return "\n\n".join(slides)
    
    def _extract_markdown(self, path):
        import re, markdown
        with open(path, 'r', encoding='utf-8') as f:
            html = markdown.markdown(f.read())
        return re.sub(r'<[^>]+>', '', html)
    
    def _extract_text(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # ── Chunking ──────────────────────────────────────────────────────
    
    def chunk_text(self, text: str) -> list[dict]:
        if not text or not text.strip():
            return []
        
        sentences = sent_tokenize(text)
        chunks = []
        current = []
        current_tokens = 0
        
        for sentence in sentences:
            stokens = len(self._tokenizer.encode(sentence))
            
            if stokens > self._chunk_size:
                if current:
                    t = " ".join(current)
                    chunks.append({"text": t, "index": len(chunks),
                                   "char_count": len(t), "token_count": current_tokens})
                    current, current_tokens = [], 0
                
                tokens = self._tokenizer.encode(sentence)
                for j in range(0, len(tokens), self._chunk_size - self._chunk_overlap):
                    piece = self._tokenizer.decode(tokens[j:j + self._chunk_size])
                    chunks.append({"text": piece, "index": len(chunks),
                                   "char_count": len(piece),
                                   "token_count": min(self._chunk_size, len(tokens) - j)})
                continue
            
            if current_tokens + stokens > self._chunk_size and current:
                t = " ".join(current)
                chunks.append({"text": t, "index": len(chunks),
                               "char_count": len(t), "token_count": current_tokens})
                
                overlap, otokens = [], 0
                for s in reversed(current):
                    st = len(self._tokenizer.encode(s))
                    if otokens + st > self._chunk_overlap:
                        break
                    overlap.insert(0, s)
                    otokens += st
                current, current_tokens = overlap, otokens
            
            current.append(sentence)
            current_tokens += stokens
        
        if current:
            t = " ".join(current)
            chunks.append({"text": t, "index": len(chunks),
                           "char_count": len(t), "token_count": current_tokens})
        
        return chunks
    
    # ── Embedding ─────────────────────────────────────────────────────
    
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        model = self.get_model()
        return model.encode(texts, show_progress_bar=False,
                            convert_to_numpy=True,
                            normalize_embeddings=True).astype('float32')
    
    def embed_query(self, text: str) -> np.ndarray:
        model = self.get_model()
        return model.encode(text, show_progress_bar=False,
                            convert_to_numpy=True,
                            normalize_embeddings=True).astype('float32')
    
    # ── Processing Pipeline ───────────────────────────────────────────
    
    def process_uploaded_file(self, uploaded_file: UploadedFile) -> bool:
        try:
            uploaded_file.processing_status = "processing"
            db.session.commit()
            
            text = self.extract_text(uploaded_file.file_path,
                                     uploaded_file.file_extension)
            if not text.strip():
                uploaded_file.processing_status = "failed"
                uploaded_file.processing_error = "No text content extracted"
                db.session.commit()
                return False
            
            uploaded_file.text_extracted = True
            chunks = self.chunk_text(text)
            
            if not chunks:
                uploaded_file.processing_status = "failed"
                uploaded_file.processing_error = "Chunking produced no output"
                db.session.commit()
                return False
            
            embeddings = self.embed_texts([c["text"] for c in chunks])
            
            for chunk_data, emb in zip(chunks, embeddings):
                dc = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    text_content=chunk_data["text"],
                    chunk_index=chunk_data["index"],
                    chunk_size=chunk_data["char_count"],
                    file_id=uploaded_file.id,
                )
                dc.set_embedding(emb)
                dc.embedding_model = self._model_name
                dc.set_metadata({
                    "token_count": chunk_data["token_count"],
                    "source_filename": uploaded_file.original_filename,
                })
                db.session.add(dc)
            
            uploaded_file.embeddings_created = True
            uploaded_file.chunk_count = len(chunks)
            uploaded_file.processing_status = "completed"
            uploaded_file.processed_at = datetime.utcnow()
            db.session.commit()
            
            self._index_cache.pop(uploaded_file.rfpo_id, None)
            logger.info(f"Processed {uploaded_file.original_filename}: "
                        f"{len(chunks)} chunks")
            return True
        
        except Exception as e:
            db.session.rollback()
            uploaded_file.processing_status = "failed"
            uploaded_file.processing_error = str(e)
            db.session.commit()
            logger.error(f"Processing failed for "
                         f"{uploaded_file.original_filename}: {e}")
            return False
    
    # ── Search ────────────────────────────────────────────────────────
    
    def _build_index(self, rfpo_id: int):
        chunks = (
            db.session.query(DocumentChunk)
            .join(UploadedFile)
            .filter(UploadedFile.rfpo_id == rfpo_id,
                    UploadedFile.embeddings_created == True)
            .order_by(DocumentChunk.id)
            .all()
        )
        
        vectors, valid = [], []
        for c in chunks:
            e = c.get_embedding()
            if e:
                vectors.append(e)
                valid.append(c)
        
        if not vectors:
            return None, []
        
        arr = np.array(vectors, dtype='float32')
        index = faiss.IndexFlatIP(arr.shape[1])
        index.add(arr)
        return index, valid
    
    def _get_index(self, rfpo_id: int):
        now = datetime.utcnow()
        if rfpo_id in self._index_cache:
            idx, chunks, built = self._index_cache[rfpo_id]
            if (now - built).total_seconds() < self._index_ttl:
                return idx, chunks
        
        idx, chunks = self._build_index(rfpo_id)
        if idx is not None:
            self._index_cache[rfpo_id] = (idx, chunks, now)
        return idx, chunks
    
    def search_similar_chunks(self, query: str, rfpo_id: int,
                               top_k: int = None,
                               threshold: float = None) -> list[dict]:
        top_k = top_k or self._top_k
        threshold = threshold or self._threshold
        
        index, chunks = self._get_index(rfpo_id)
        if index is None:
            return []
        
        qvec = np.array([self.embed_query(query)], dtype='float32')
        scores, indices = index.search(qvec, min(top_k, len(chunks)))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < threshold:
                continue
            c = chunks[idx]
            results.append({
                "chunk_id": c.chunk_id,
                "text_content": c.text_content,
                "similarity_score": round(float(score), 4),
                "file_name": c.file.original_filename if c.file else "Unknown",
                "page_number": c.page_number,
                "section_title": c.section_title,
                "chunk_index": c.chunk_index,
            })
        return results


# Singleton
document_processor = DocumentProcessor()
```

---

## 14. Testing

### Test Document Processing

```python
def test_text_extraction():
    """Verify text extraction works for each file type."""
    from document_processor import document_processor
    
    # Create a temp text file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("The project budget is $500,000.")
        path = f.name
    
    text = document_processor.extract_text(path, "txt")
    assert "budget" in text
    assert "$500,000" in text
    os.unlink(path)


def test_chunking():
    """Verify chunking produces reasonable output."""
    from document_processor import document_processor
    
    text = "First sentence. " * 200  # Long text
    chunks = document_processor.chunk_text(text)
    
    assert len(chunks) > 1
    assert all(c["char_count"] > 0 for c in chunks)
    assert all(c["token_count"] > 0 for c in chunks)
    # Verify chunks are ordered
    assert all(chunks[i]["index"] == i for i in range(len(chunks)))


def test_embedding_generation():
    """Verify embeddings have correct shape and are normalized."""
    from document_processor import document_processor
    
    texts = ["Hello world", "Test document"]
    embeddings = document_processor.embed_texts(texts)
    
    assert embeddings.shape == (2, 384)  # 2 texts, 384 dimensions
    # Check normalization (L2 norm should be ~1.0)
    norms = np.linalg.norm(embeddings, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-5)


def test_similarity_search():
    """Verify similar texts score higher than dissimilar ones."""
    from document_processor import document_processor
    
    budget_text = "The total project budget is $500,000 over 10 months."
    timeline_text = "Phase 1 starts in January and ends in March."
    query = "How much does the project cost?"
    
    embeddings = document_processor.embed_texts([budget_text, timeline_text])
    query_emb = document_processor.embed_query(query)
    
    # Budget text should be more similar to cost query
    sim_budget = np.dot(query_emb, embeddings[0])
    sim_timeline = np.dot(query_emb, embeddings[1])
    
    assert sim_budget > sim_timeline
```

### Integration Test (Requires Flask App Context)

See the existing [tests/test_rag_functionality.py](../tests/test_rag_functionality.py) for a full integration test that:
1. Creates test documents (text and markdown files)
2. Creates `UploadedFile` records
3. Processes files through the pipeline
4. Runs similarity searches
5. Tests the RAG assistant integration

---

## 15. Performance and Scaling Notes

### Embedding Generation Speed

| Hardware | Texts/Second (all-MiniLM-L6-v2) |
|---|---|
| CPU (modern x86) | ~50-100 |
| GPU (NVIDIA T4) | ~500-1000 |
| Apple M1/M2 | ~80-150 |

A 50-page PDF typically produces 50-200 chunks. Processing takes 1-4 seconds on CPU.

### FAISS Search Speed

| Vectors | IndexFlatIP | IndexIVFFlat |
|---|---|---|
| 1,000 | < 1 ms | N/A (too few) |
| 10,000 | ~1 ms | < 1 ms |
| 100,000 | ~10 ms | ~1 ms |
| 1,000,000 | ~100 ms | ~5 ms |

For this application (likely < 50K chunks total), `IndexFlatIP` is more than sufficient.

### Storage Requirements

| Component | Size per chunk |
|---|---|
| Text content | ~1 KB (avg 500 chars) |
| Embedding (384-dim, JSON) | ~3 KB |
| Metadata | ~200 bytes |
| **Total per chunk** | **~4 KB** |

10,000 chunks ≈ 40 MB of database storage.

### Scaling Beyond a Single Server

When you outgrow the single-server FAISS approach:

1. **pgvector** — Move vector search into PostgreSQL (see Section 10)
2. **Pinecone / Weaviate / Qdrant** — Managed vector databases with built-in scaling
3. **Redis + RediSearch** — If you already use Redis, it supports vector search
4. **Celery task queue** — Replace background threads with distributed workers
5. **GPU embedding service** — Run sentence-transformers on a GPU node and call it as a microservice

---

## Glossary

| Term | Definition |
|---|---|
| **Embedding** | A fixed-length numeric vector (e.g., 384 floats) that represents the meaning of a text |
| **Chunk** | A portion of a document (typically 256-512 tokens) small enough for embedding |
| **Vector index** | A data structure optimized for finding the nearest vectors to a query vector |
| **Cosine similarity** | Measures the angle between two vectors (1.0 = identical direction, 0.0 = orthogonal) |
| **Top-k** | The number of most-similar results to return from a search |
| **Token** | A sub-word unit used by language models (roughly 4 characters per token in English) |
| **FAISS** | Facebook AI Similarity Search — a library for efficient vector similarity search |
| **pgvector** | PostgreSQL extension that adds native vector column type and similarity operators |
| **Retrieval** | Finding relevant document chunks for a given query |
| **Augmentation** | Adding retrieved context to a prompt before sending to an LLM |
| **Generation** | The LLM producing an answer based on the augmented prompt |
