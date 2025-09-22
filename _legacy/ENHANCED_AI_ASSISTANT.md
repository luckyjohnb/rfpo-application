# Enhanced AI Assistant with RAG Integration

## 🚀 Overview

The AI Assistant has been completely redesigned to provide a sophisticated, context-aware conversational experience with full RAG (Retrieval-Augmented Generation) integration and OpenAI API support.

## ✨ New Features

### 🎯 **Context Selection System**
- **Team Selector**: Choose which team's context to use
- **RFPO Selector**: Select specific RFPO within the chosen team
- **Hierarchical Selection**: Must select Team first, then RFPO becomes available
- **Smart Filtering**: RFPOs are filtered by selected team

### 🧠 **RAG Integration Indicators**
- **Brain Emoji**: 🧠 appears next to GPT model badge when RAG is active
- **Context Banner**: Green alert showing active Team → RFPO context
- **Document Stats**: Shows number of files and chunks available
- **Clear Context**: Easy button to reset all context

### 🔗 **OpenAI Integration**
- **Real Conversations**: Uses OpenAI GPT-3.5-turbo for actual AI responses
- **RAG Enhancement**: Automatically includes relevant document context
- **Fallback System**: Falls back to Langflow if OpenAI is unavailable
- **Usage Tracking**: Monitors token usage and costs

### 📝 **Thread Management**
- **Unique Threads**: Each user + team + RFPO combination gets its own thread
- **Thread IDs**: Format: `userId_TteamId_RrfpoId_timestamp`
- **New Thread**: Button to start fresh conversations
- **Thread Persistence**: Maintains conversation history per context

## 🎨 **UI Enhancements**

### **Header Section**
```
AI Assistant                    🧠 GPT-3.5    [ℹ️] [⚙️]
Online
```
- Brain emoji only shows when RAG context is active
- Model badge clearly indicates AI model being used

### **Context Selection**
```
Team Context: [Select Team...        ▼]
RFPO Context: [Select Team first...  ▼] (disabled until team selected)
```

### **Active Context Display**
```
🧠 RAG Context Active - AI has access to documents from 
Engineering Team (ENG) → RFPO-003 - CT02                    [✕ Clear]

2 files, 2 ready for RAG, 17 chunks
```

### **Thread Management**
```
💬 Thread: userId_T1_R3_1724251765... [+ New] [💡 Suggestions]
```

## 🔧 **Technical Implementation**

### **Frontend JavaScript**
- `loadTeamsForAI()`: Loads available teams
- `updateTeamContext()`: Handles team selection and loads RFPOs
- `updateRFPOContext()`: Activates RAG and creates thread
- `startNewThread()`: Generates unique thread IDs
- `sendMessage()`: Enhanced to use OpenAI API with RAG context

### **Backend API Endpoints**
- `GET /api/teams`: List available teams
- `GET /api/v1/rag/rfpos`: List RFPOs (filtered by team)
- `POST /api/v1/ai/chat`: New OpenAI chat endpoint with RAG
- `GET /api/v1/ai/suggest-questions/<rfpo_id>`: Generate contextual questions

### **OpenAI Integration**
```python
# Example request to OpenAI
{
    "model": "gpt-3.5-turbo",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful AI assistant. When provided with document context, base your responses primarily on that context and cite your sources."
        },
        {
            "role": "user", 
            "content": "Enhanced message with RAG context..."
        }
    ],
    "max_tokens": 1000,
    "temperature": 0.7
}
```

### **RAG Context Enhancement**
When a user asks a question with RFPO context selected:

1. **Query Enhancement**: User question is enhanced with relevant document chunks
2. **Context Injection**: Top 5 most relevant document chunks are included
3. **Source Attribution**: AI response includes source citations
4. **Relevance Scoring**: Shows average relevance score of retrieved context

## 🔐 **Security & Authentication**

- **JWT Authentication**: All API calls require valid JWT tokens
- **User Context**: Requests include user ID for personalization
- **Team-based Access**: Users can only access teams they belong to
- **RFPO Permissions**: Access controlled by team membership

## 🌟 **User Experience Flow**

### **Starting a RAG-Enhanced Conversation**

1. **Select Team**: Choose from dropdown (e.g., "Engineering Team (ENG)")
2. **Select RFPO**: Choose specific RFPO (e.g., "RFPO-003 - CT02")
3. **RAG Activates**: 
   - 🧠 Brain emoji appears next to GPT-3.5
   - Green context banner shows active context
   - Thread management section appears
   - New conversation thread is created
4. **Ask Questions**: Questions are automatically enhanced with document context
5. **Get Enhanced Responses**: AI responses include relevant citations and context

### **Example Conversation**

**User**: "What vulnerabilities were found in the security assessment?"

**System**: 🧠 Using context from 3 document chunks (USCAR_Vulnerability_Report.docx) - Avg relevance: 0.456

**AI**: "Based on the security assessment document, several critical vulnerabilities were identified:

1. **Public File Exposure**: The secure.uscarteams.org server has confirmed exploit vulnerabilities with directory listing enabled under /secure/vroom1_folder/
2. **Apache Server Security**: Multiple security configuration issues were found...

*Sources: USCAR_072825-Vulnerability_and_Exploit_Report.docx*"

## 📊 **Benefits**

### **For Users**
- **Contextual Conversations**: AI understands your specific documents and projects
- **Team Collaboration**: Separate conversations per team/project context
- **Source Citations**: Always know where information comes from
- **Smart Suggestions**: Get relevant questions based on your documents

### **For Organizations**
- **Knowledge Management**: Centralized access to document knowledge
- **Team Isolation**: Conversations and context separated by team
- **Audit Trail**: Thread tracking for compliance and review
- **Cost Control**: OpenAI usage monitoring and fallback systems

## 🚀 **Getting Started**

1. **Upload Documents**: Use the File Upload feature to add documents to RFPOs
2. **Select Context**: Choose Team and RFPO in the AI Assistant
3. **Start Chatting**: Ask questions about your documents
4. **Use Suggestions**: Click the suggestions button for relevant questions

## 🔧 **Configuration Requirements**

### **Environment Variables**
```bash
OPENAI_API_KEY=sk-...                    # Required for OpenAI integration
OPENAI_ORG_ID=org-...                   # Optional organization ID
```

### **Dependencies**
- `requests>=2.25.1`: For OpenAI API calls
- `sentence-transformers`: For RAG embeddings
- `numpy`, `scikit-learn`: For vector similarity

## 🎯 **Future Enhancements**

- **GPT-4 Support**: Upgrade to more powerful models
- **Conversation Export**: Download chat histories
- **Advanced Threading**: Branch conversations and merge contexts
- **Multi-RFPO Context**: Ask questions across multiple RFPOs
- **Voice Integration**: Speech-to-text and text-to-speech
- **Real-time Collaboration**: Shared team conversations

---

**The Enhanced AI Assistant transforms document interaction from simple file storage to intelligent, contextual conversations that understand your business context and provide actionable insights.**
