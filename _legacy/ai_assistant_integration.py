"""
AI Assistant Integration with RAG System
Enhances the existing AI assistant to use RAG context from uploaded documents
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from models import db, RFPO, UploadedFile, DocumentChunk
from document_processor import document_processor

logger = logging.getLogger(__name__)

class RAGEnhancedAssistant:
    """Enhanced AI Assistant with RAG capabilities"""
    
    def __init__(self):
        self.max_context_chunks = 5
        self.context_similarity_threshold = 0.3
    
    def enhance_message_with_rag(self, message: str, user_context: Dict) -> Dict:
        """
        Enhance a user message with RAG context from their documents
        
        Args:
            message: The user's message/question
            user_context: Context about the user (e.g., current RFPO, preferences)
            
        Returns:
            Enhanced message data with RAG context
        """
        try:
            # Determine which RFPO to search (could be from user context, session, or explicit)
            rfpo_id = self._determine_rfpo_context(message, user_context)
            
            if not rfpo_id:
                return {
                    'enhanced_message': message,
                    'rag_context': None,
                    'context_source': 'none',
                    'message': 'No RFPO context available for RAG search'
                }
            
            # Search for relevant document chunks
            relevant_chunks = document_processor.search_similar_chunks(
                message, rfpo_id, top_k=self.max_context_chunks
            )
            
            # Filter chunks by similarity threshold
            filtered_chunks = [
                chunk for chunk in relevant_chunks 
                if chunk.get('similarity_score', 0) >= self.context_similarity_threshold
            ]
            
            if not filtered_chunks:
                return {
                    'enhanced_message': message,
                    'rag_context': None,
                    'context_source': 'no_relevant_docs',
                    'message': f'No relevant documents found in RFPO for this query'
                }
            
            # Build enhanced message with context
            enhanced_message = self._build_enhanced_message(message, filtered_chunks, rfpo_id)
            
            return {
                'enhanced_message': enhanced_message,
                'rag_context': {
                    'rfpo_id': rfpo_id,
                    'chunks_found': len(filtered_chunks),
                    'chunks_used': len(filtered_chunks),
                    'sources': list(set([chunk['file_name'] for chunk in filtered_chunks])),
                    'avg_similarity': sum(c['similarity_score'] for c in filtered_chunks) / len(filtered_chunks)
                },
                'context_source': 'rag_documents',
                'context_chunks': filtered_chunks
            }
            
        except Exception as e:
            logger.error(f"Error enhancing message with RAG: {str(e)}")
            return {
                'enhanced_message': message,
                'rag_context': None,
                'context_source': 'error',
                'error': str(e)
            }
    
    def _determine_rfpo_context(self, message: str, user_context: Dict) -> Optional[int]:
        """
        Determine which RFPO to use for context based on message and user context
        """
        # Priority 1: Explicit RFPO mentioned in user context
        if user_context.get('current_rfpo_id'):
            return user_context['current_rfpo_id']
        
        # Priority 2: RFPO mentioned in the message (e.g., "RFPO-001")
        rfpo_mention = self._extract_rfpo_from_message(message)
        if rfpo_mention:
            rfpo = RFPO.query.filter_by(rfpo_id=rfpo_mention).first()
            if rfpo:
                return rfpo.id
        
        # Priority 3: User's most recent RFPO (if available in user context)
        if user_context.get('recent_rfpo_id'):
            return user_context['recent_rfpo_id']
        
        # Priority 4: RFPO with most recent activity (fallback)
        recent_rfpo = RFPO.query.order_by(RFPO.updated_at.desc()).first()
        if recent_rfpo:
            return recent_rfpo.id
        
        return None
    
    def _extract_rfpo_from_message(self, message: str) -> Optional[str]:
        """Extract RFPO ID from message text"""
        import re
        
        # Look for patterns like "RFPO-001", "RFPO-123", etc.
        pattern = r'RFPO-\d{3,}'
        matches = re.findall(pattern, message.upper())
        
        return matches[0] if matches else None
    
    def _build_enhanced_message(self, original_message: str, chunks: List[Dict], rfpo_id: int) -> str:
        """
        Build an enhanced message with RAG context for the AI
        """
        # Get RFPO info
        rfpo = RFPO.query.get(rfpo_id)
        rfpo_info = f"RFPO {rfpo.rfpo_id}: {rfpo.title}" if rfpo else f"RFPO ID {rfpo_id}"
        
        # Build context section
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            similarity = chunk.get('similarity_score', 0)
            file_name = chunk.get('file_name', 'Unknown file')
            content = chunk.get('text_content', '')
            
            # Truncate very long content
            if len(content) > 800:
                content = content[:800] + "..."
            
            context_parts.append(
                f"Document {i} (from {file_name}, relevance: {similarity:.2f}):\n{content}"
            )
        
        context_text = "\n\n".join(context_parts)
        
        # Build the enhanced prompt
        enhanced_message = f"""You are an AI assistant helping with {rfpo_info}. A user has asked a question, and I've found some relevant context from documents uploaded to this RFPO.

User's Question: {original_message}

Relevant Document Context:
{context_text}

Instructions:
1. Answer the user's question primarily based on the document context provided above
2. If the context doesn't contain enough information to fully answer the question, say so clearly
3. Always cite which documents you're referencing in your answer
4. Be concise but thorough
5. If you notice any inconsistencies in the documents, mention them

Please provide a helpful response based on the document context."""

        return enhanced_message
    
    def get_rfpo_summary(self, rfpo_id: int) -> Dict:
        """
        Get a summary of documents and processing status for an RFPO
        """
        try:
            rfpo = RFPO.query.get(rfpo_id)
            if not rfpo:
                return {'error': 'RFPO not found'}
            
            files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()
            
            summary = {
                'rfpo_info': rfpo.to_dict(),
                'file_count': len(files),
                'files_by_status': {},
                'total_chunks': 0,
                'processing_errors': [],
                'file_types': {},
                'ready_for_rag': 0
            }
            
            for file in files:
                # Count by processing status
                status = file.processing_status
                summary['files_by_status'][status] = summary['files_by_status'].get(status, 0) + 1
                
                # Count file types
                ext = file.file_extension
                summary['file_types'][ext] = summary['file_types'].get(ext, 0) + 1
                
                # Count chunks
                summary['total_chunks'] += file.chunk_count or 0
                
                # Track processing errors
                if file.processing_error:
                    summary['processing_errors'].append({
                        'file': file.original_filename,
                        'error': file.processing_error
                    })
                
                # Count files ready for RAG
                if file.processing_status == 'completed' and file.embeddings_created:
                    summary['ready_for_rag'] += 1
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting RFPO summary: {str(e)}")
            return {'error': str(e)}
    
    def suggest_questions(self, rfpo_id: int, limit: int = 5) -> List[str]:
        """
        Suggest questions based on the documents in an RFPO
        """
        try:
            # Get some sample chunks to analyze
            chunks = db.session.query(DocumentChunk).join(UploadedFile).filter(
                UploadedFile.rfpo_id == rfpo_id,
                DocumentChunk.text_content.isnot(None)
            ).limit(20).all()
            
            if not chunks:
                return []
            
            # Simple keyword-based question suggestions
            # In a production system, you might use NLP to generate better questions
            suggestions = []
            
            # Look for common patterns in the text
            text_samples = [chunk.text_content[:200] for chunk in chunks[:10]]
            combined_text = " ".join(text_samples).lower()
            
            # Suggest questions based on content patterns
            if "cost" in combined_text or "price" in combined_text or "$" in combined_text:
                suggestions.append("What are the costs mentioned in the documents?")
            
            if "requirement" in combined_text or "spec" in combined_text:
                suggestions.append("What are the key requirements outlined?")
            
            if "timeline" in combined_text or "schedule" in combined_text or "date" in combined_text:
                suggestions.append("What is the project timeline?")
            
            if "vendor" in combined_text or "supplier" in combined_text:
                suggestions.append("Who are the vendors or suppliers mentioned?")
            
            if "risk" in combined_text or "issue" in combined_text:
                suggestions.append("What risks or issues are identified?")
            
            # Generic questions
            suggestions.extend([
                "What is the main purpose of this RFPO?",
                "Can you summarize the key points from the documents?",
                "What are the deliverables mentioned?"
            ])
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Error suggesting questions: {str(e)}")
            return []

# Global instance
rag_assistant = RAGEnhancedAssistant()
