# RAG Implementation Guide

## Overview

This document describes the enhanced file upload and RAG (Retrieval-Augmented Generation) system implemented for the RFPO application. The system allows users to upload various file types, processes them for text extraction and chunking, generates embeddings, and enables intelligent document search and chat functionality.

## 🚀 Features

### File Processing Pipeline
- **Multi-format support**: PDF, DOCX, XLSX, CSV, TXT, MD, PPTX, and more
- **Intelligent text extraction**: Format-specific extractors for optimal content retrieval
- **Document chunking**: Smart text segmentation with overlap for better context preservation
- **Local embeddings**: Uses sentence-transformers for privacy-preserving vector generation
- **Async processing**: Background processing to avoid blocking uploads

### RAG Capabilities
- **Semantic search**: Find relevant document chunks using vector similarity
- **RFPO-scoped search**: Search within specific RFPO contexts
- **AI assistant integration**: Enhanced chat with document context
- **Question suggestions**: Auto-generated questions based on document content

### Database Schema
- **RFPO**: Request for Purchase Orders with team associations
- **UploadedFile**: File metadata and processing status
- **DocumentChunk**: Text chunks with embeddings and metadata

## 🔧 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The new dependencies include:
- Document processing: `PyPDF2`, `python-docx`, `openpyxl`, `python-pptx`, `markdown`
- RAG: `sentence-transformers`, `faiss-cpu`, `scikit-learn`
- Text processing: `nltk`, `tiktoken`

### 2. Initialize Database

```bash
python init_rag_db.py
```

This will:
- Create new database tables (RFPO, UploadedFile, DocumentChunk)
- Set up a default team if none exists
- Show current database status

### 3. Optional: Create Sample Data

```bash
python init_rag_db.py --sample
```

## 📊 API Endpoints

### RAG API (`/api/v1/rag/`)

#### RFPO Management
- `GET /api/v1/rag/rfpos` - List all RFPOs
- `POST /api/v1/rag/rfpos` - Create new RFPO
- `GET /api/v1/rag/rfpos/{rfpo_id}` - Get RFPO details with files

#### File Upload & Management
- `POST /api/v1/rag/rfpos/{rfpo_id}/files` - Upload files to RFPO
- `GET /api/v1/rag/files/{file_id}/status` - Check processing status
- `POST /api/v1/rag/files/{file_id}/reprocess` - Reprocess failed files
- `DELETE /api/v1/rag/files/{file_id}` - Delete file and chunks

#### Search & Chat
- `POST /api/v1/rag/rfpos/{rfpo_id}/search` - Search documents
- `POST /api/v1/rag/rfpos/{rfpo_id}/chat` - Chat with documents

### AI Assistant Integration (`/api/v1/ai/`)

- `POST /api/v1/ai/enhance-message` - Enhance message with RAG context
- `GET /api/v1/ai/rfpo-summary/{rfpo_id}` - Get RFPO processing summary
- `GET /api/v1/ai/suggest-questions/{rfpo_id}` - Get suggested questions

### Legacy Endpoints

- `POST /upload` - Legacy CSV/Excel upload (backward compatible)
- `POST /api/v2/files/` - Redirects to new RAG API

## 🔄 Processing Workflow

### 1. File Upload
```
User uploads file → File saved to disk → Database record created → Async processing started
```

### 2. Document Processing
```
Text extraction → Document chunking → Embedding generation → Database storage
```

### 3. RAG Search
```
User query → Query embedding → Vector similarity search → Ranked results
```

### 4. AI Integration
```
User message → RAG context retrieval → Enhanced prompt → AI response
```

## 📝 Usage Examples

### Upload Files to RFPO

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@document.pdf" \
  -F "files=@requirements.docx" \
  http://localhost:5000/api/v1/rag/rfpos/1/files
```

### Search Documents

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the technical requirements?", "top_k": 5}' \
  http://localhost:5000/api/v1/rag/rfpos/1/search
```

### Enhanced AI Chat

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize the project timeline", "rfpo_id": 1}' \
  http://localhost:5000/api/v1/ai/enhance-message
```

## 🏗️ Architecture

### Components

1. **Document Processor** (`document_processor.py`)
   - Text extraction for multiple formats
   - Intelligent chunking with overlap
   - Local embedding generation
   - Processing status tracking

2. **RAG API** (`rag_api.py`)
   - RESTful endpoints for file management
   - RFPO-scoped operations
   - Search and chat functionality
   - Authentication integration

3. **AI Assistant Integration** (`ai_assistant_integration.py`)
   - RAG-enhanced message processing
   - Context determination logic
   - Question suggestion system
   - RFPO summary generation

4. **Database Models** (`models.py`)
   - RFPO, UploadedFile, DocumentChunk models
   - Relationship management
   - JSON serialization helpers

### Data Flow

```
Frontend → RAG API → Document Processor → Database
                                      ↓
AI Assistant ← Enhanced Context ← Vector Search
```

## 🔒 Security Considerations

- **Authentication**: All RAG endpoints require valid JWT tokens
- **File validation**: Strict file type and size limits
- **Secure storage**: Files stored with UUID-based names
- **Access control**: RFPO-scoped access (can be extended)
- **Local processing**: Embeddings generated locally (privacy-preserving)

## 🚨 Troubleshooting

### Common Issues

1. **Dependencies not installed**
   ```
   Error: RAG functionality not available
   Solution: pip install -r requirements.txt
   ```

2. **Database not initialized**
   ```
   Error: Table doesn't exist
   Solution: python init_rag_db.py
   ```

3. **Processing stuck in 'pending'**
   ```
   Check: File processing status endpoint
   Solution: Reprocess file or check logs
   ```

4. **No search results**
   ```
   Check: File processing completed
   Check: Similarity threshold (default 0.3)
   ```

### Monitoring

- Check processing status: `GET /api/v1/rag/files/{file_id}/status`
- View RFPO summary: `GET /api/v1/ai/rfpo-summary/{rfpo_id}`
- Database info: `python init_rag_db.py --info`

## 🔮 Future Enhancements

### Planned Features
- **Advanced chunking**: Semantic-aware chunking strategies
- **Multi-modal support**: Image and table extraction
- **Hybrid search**: Combine semantic and keyword search
- **Fine-tuned embeddings**: Domain-specific embedding models
- **Vector database**: Migration to dedicated vector stores (Pinecone, Weaviate)
- **Advanced RAG**: Query expansion, re-ranking, citation tracking

### Configuration Options
- Chunk size and overlap settings
- Embedding model selection
- Similarity thresholds
- Processing parallelization
- Cache management

## 📚 Integration with Existing Features

### AI Assistant
The RAG system seamlessly integrates with your existing Langflow-based AI assistant:

1. **Context Enhancement**: User messages are automatically enhanced with relevant document context
2. **RFPO Awareness**: The system can determine which RFPO context to use
3. **Source Attribution**: AI responses can cite specific documents
4. **Question Suggestions**: Auto-generated questions help users explore their documents

### File Upload UI
The existing file upload interface continues to work:

1. **Backward Compatibility**: CSV/Excel uploads work as before
2. **Enhanced Support**: New file types are supported via the RAG API
3. **Processing Status**: Users can track document processing progress
4. **Error Handling**: Clear feedback on processing failures

### Configuration System
RAG settings integrate with your existing configuration:

1. **File Type Settings**: Configure allowed file types
2. **Size Limits**: Set upload size restrictions
3. **Processing Options**: Control chunking and embedding parameters

## 🤝 Contributing

When contributing to the RAG system:

1. **Test thoroughly**: Ensure backward compatibility
2. **Document changes**: Update this README for new features
3. **Consider performance**: Monitor processing times and resource usage
4. **Maintain security**: Follow authentication and validation patterns

## 📄 License

This RAG implementation follows the same license as the main application.

---

**Need Help?** Check the troubleshooting section or review the API documentation for detailed endpoint specifications.
