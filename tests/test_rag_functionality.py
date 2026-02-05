#!/usr/bin/env python3
"""
Test RAG functionality
Quick test to demonstrate file processing and search capabilities
"""
import os
import sys
import tempfile
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, RFPO, UploadedFile, DocumentChunk
from document_processor import document_processor


def create_test_files():
    """Create some test files for processing"""
    test_files = []

    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    # Test file 1: Text file
    txt_content = """
    Project Requirements Document
    
    This document outlines the technical requirements for the IT Infrastructure Modernization project.
    
    Objectives:
    1. Upgrade server infrastructure to cloud-based solutions
    2. Implement modern security protocols
    3. Establish disaster recovery procedures
    4. Migrate legacy applications to containerized environments
    
    Timeline:
    - Phase 1: Planning and assessment (2 months)
    - Phase 2: Infrastructure setup (3 months)
    - Phase 3: Application migration (4 months)
    - Phase 4: Testing and optimization (1 month)
    
    Budget: $500,000 - $750,000
    
    Key deliverables include network architecture diagrams, security implementation plans,
    and comprehensive documentation for all systems.
    """

    txt_file = os.path.join(temp_dir, "requirements.txt")
    with open(txt_file, "w") as f:
        f.write(txt_content)
    test_files.append(txt_file)

    # Test file 2: Markdown file
    md_content = """
    # Vendor Evaluation Report
    
    ## Executive Summary
    
    This report evaluates three potential vendors for the IT infrastructure project.
    
    ## Vendor Analysis
    
    ### Vendor A: CloudTech Solutions
    - **Strengths**: Extensive cloud experience, competitive pricing
    - **Weaknesses**: Limited local support
    - **Cost**: $450,000
    
    ### Vendor B: Enterprise Systems Inc
    - **Strengths**: Strong local presence, proven track record
    - **Weaknesses**: Higher costs, longer timeline
    - **Cost**: $680,000
    
    ### Vendor C: Modern IT Partners
    - **Strengths**: Innovative solutions, fast deployment
    - **Weaknesses**: Newer company, limited references
    - **Cost**: $520,000
    
    ## Recommendation
    
    Based on the analysis, we recommend **Vendor A (CloudTech Solutions)** for the following reasons:
    1. Best value proposition
    2. Strong technical capabilities
    3. Alignment with project timeline
    
    ## Risk Mitigation
    
    To address the limited local support concern:
    - Establish dedicated remote support channel
    - Include on-site visits in contract
    - Implement comprehensive documentation requirements
    """

    md_file = os.path.join(temp_dir, "vendor_evaluation.md")
    with open(md_file, "w") as f:
        f.write(md_content)
    test_files.append(md_file)

    return test_files, temp_dir


def test_document_processing():
    """Test document processing pipeline"""
    print("🧪 Testing Document Processing Pipeline")
    print("=" * 50)

    with app.app_context():
        # Get the sample RFPO
        rfpo = RFPO.query.filter_by(rfpo_id="RFPO-SAMPLE").first()
        if not rfpo:
            print("❌ Sample RFPO not found. Run init_rag_db.py --sample first")
            return False

        print(f"✅ Using RFPO: {rfpo.rfpo_id} - {rfpo.title}")

        # Create test files
        test_files, temp_dir = create_test_files()
        print(f"✅ Created {len(test_files)} test files")

        processed_files = []

        for file_path in test_files:
            filename = os.path.basename(file_path)
            print(f"\n📄 Processing: {filename}")

            try:
                # Create UploadedFile record
                import uuid
                import mimetypes

                file_id = str(uuid.uuid4())
                file_size = os.path.getsize(file_path)
                mime_type, _ = mimetypes.guess_type(filename)

                uploaded_file = UploadedFile(
                    file_id=file_id,
                    original_filename=filename,
                    stored_filename=f"{file_id}_{filename}",
                    file_path=file_path,
                    file_size=file_size,
                    mime_type=mime_type or "text/plain",
                    file_extension=filename.split(".")[-1].lower(),
                    rfpo_id=rfpo.id,
                    uploaded_by="test_user",
                    processing_status="pending",
                )

                db.session.add(uploaded_file)
                db.session.commit()

                # Process the file
                success = document_processor.process_uploaded_file(uploaded_file)

                if success:
                    print(f"  ✅ Processing successful")
                    print(f"  📊 Chunks created: {uploaded_file.chunk_count}")
                    processed_files.append(uploaded_file)
                else:
                    print(f"  ❌ Processing failed: {uploaded_file.processing_error}")

            except Exception as e:
                print(f"  ❌ Error processing {filename}: {str(e)}")

        print(f"\n✅ Successfully processed {len(processed_files)} files")
        return processed_files, rfpo


def test_rag_search(rfpo):
    """Test RAG search functionality"""
    print("\n🔍 Testing RAG Search Functionality")
    print("=" * 50)

    with app.app_context():
        # Refresh the RFPO object in the current session
        rfpo = db.session.merge(rfpo)

        test_queries = [
            "What is the project budget?",
            "Which vendor is recommended?",
            "What are the project phases?",
            "What are the key deliverables?",
            "What are the risks mentioned?",
        ]

        for query in test_queries:
            print(f"\n❓ Query: {query}")

            try:
                results = document_processor.search_similar_chunks(
                    query, rfpo.id, top_k=3
                )

                if results:
                    print(f"  📊 Found {len(results)} relevant chunks:")
                    for i, result in enumerate(results, 1):
                        score = result.get("similarity_score", 0)
                        file_name = result.get("file_name", "Unknown")
                        content = result.get("text_content", "")[:100] + "..."
                        print(f"    {i}. [{file_name}] (Score: {score:.3f})")
                        print(f"       {content}")
                else:
                    print("  ❌ No relevant results found")

            except Exception as e:
                print(f"  ❌ Search error: {str(e)}")


def test_ai_integration(rfpo):
    """Test AI assistant integration"""
    print("\n🤖 Testing AI Assistant Integration")
    print("=" * 50)

    with app.app_context():
        # Refresh the RFPO object in the current session
        rfpo = db.session.merge(rfpo)

        try:
            from ai_assistant_integration import rag_assistant

            test_message = (
                "Can you summarize the project requirements and vendor recommendations?"
            )
            user_context = {"current_rfpo_id": rfpo.id}

            print(f"💬 Test message: {test_message}")

            enhanced_data = rag_assistant.enhance_message_with_rag(
                test_message, user_context
            )

            print(
                f"🔧 Context source: {enhanced_data.get('context_source', 'unknown')}"
            )

            if enhanced_data.get("rag_context"):
                context = enhanced_data["rag_context"]
                print(f"📊 RAG Context:")
                print(f"  - Chunks found: {context.get('chunks_found', 0)}")
                print(f"  - Sources: {', '.join(context.get('sources', []))}")
                print(f"  - Avg similarity: {context.get('avg_similarity', 0):.3f}")

            # Test question suggestions
            suggestions = rag_assistant.suggest_questions(rfpo.id, limit=3)
            print(f"\n💡 Suggested questions ({len(suggestions)}):")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. {suggestion}")

            # Test RFPO summary
            summary = rag_assistant.get_rfpo_summary(rfpo.id)
            print(f"\n📋 RFPO Summary:")
            print(f"  - Files: {summary.get('file_count', 0)}")
            print(f"  - Ready for RAG: {summary.get('ready_for_rag', 0)}")
            print(f"  - Total chunks: {summary.get('total_chunks', 0)}")

        except Exception as e:
            print(f"❌ AI integration test failed: {str(e)}")


def cleanup_test_data():
    """Clean up test data"""
    print("\n🧹 Cleaning up test data...")

    with app.app_context():
        try:
            # Delete chunks
            chunks_deleted = DocumentChunk.query.filter(
                DocumentChunk.file.has(UploadedFile.uploaded_by == "test_user")
            ).delete(synchronize_session=False)

            # Delete files
            files_deleted = UploadedFile.query.filter_by(
                uploaded_by="test_user"
            ).delete()

            db.session.commit()

            print(f"✅ Cleaned up {files_deleted} files and {chunks_deleted} chunks")

        except Exception as e:
            print(f"❌ Cleanup error: {str(e)}")


def main():
    """Main test function"""
    print("🚀 RAG Functionality Test Suite")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Test document processing
        processed_files, rfpo = test_document_processing()

        if not processed_files:
            print("❌ No files were processed successfully. Exiting.")
            return False

        # Test RAG search
        test_rag_search(rfpo)

        # Test AI integration
        test_ai_integration(rfpo)

        print("\n🎉 All tests completed!")

        # Ask if user wants to clean up
        response = input("\n🗑️  Clean up test data? (y/N): ").strip().lower()
        if response in ["y", "yes"]:
            cleanup_test_data()
        else:
            print("💾 Test data preserved for inspection")

        return True

    except Exception as e:
        print(f"❌ Test suite failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
