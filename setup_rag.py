#!/usr/bin/env python3
"""
Setup script for RAG functionality
Installs dependencies, initializes database, and runs basic tests
"""
import os
import sys
import subprocess
import importlib

def install_dependencies(missing_packages=None):
    """Install required dependencies"""
    print("🔧 Installing RAG dependencies...")
    
    try:
        if missing_packages:
            # Install specific missing packages
            print(f"Installing missing packages: {', '.join(missing_packages)}")
            for package in missing_packages:
                print(f"  Installing {package}...")
                result = subprocess.run([
                    sys.executable, '-m', 'pip', 'install', package, '--upgrade'
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"  ❌ Failed to install {package}: {result.stderr}")
                    return False
                else:
                    print(f"  ✅ {package} installed successfully")
        else:
            # Install all requirements
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '--upgrade'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Error installing dependencies: {result.stderr}")
                return False
        
        print("✅ Dependencies installed successfully")
        return True
            
    except Exception as e:
        print(f"❌ Error during installation: {str(e)}")
        return False

def check_dependencies():
    """Check if all required dependencies are available"""
    print("🔍 Checking RAG dependencies...")
    
    # Core packages with their import names
    required_packages = {
        'pandas': 'pandas',
        'numpy': 'numpy', 
        'PyPDF2': 'PyPDF2',
        'python-docx': 'docx',
        'openpyxl': 'openpyxl',
        'sentence-transformers': 'sentence_transformers',
        'nltk': 'nltk',
        'tiktoken': 'tiktoken',
        'faiss-cpu': 'faiss',
        'scikit-learn': 'sklearn',
        'markdown': 'markdown'
    }
    
    missing = []
    available = []
    
    for package_name, import_name in required_packages.items():
        try:
            importlib.import_module(import_name)
            available.append(package_name)
        except ImportError as e:
            print(f"  ❌ {package_name} ({import_name}): {str(e)}")
            missing.append(package_name)
    
    print(f"✅ Available packages ({len(available)}): {', '.join(available)}")
    
    if missing:
        print(f"⚠️  Missing packages ({len(missing)}): {', '.join(missing)}")
        return False, missing
    else:
        print("🎉 All dependencies are available!")
        return True, []

def initialize_database():
    """Initialize the RAG database"""
    print("🗄️  Initializing RAG database...")
    
    try:
        from init_rag_db import init_rag_database
        success = init_rag_database()
        
        if success:
            print("✅ Database initialized successfully")
        else:
            print("❌ Database initialization failed")
        
        return success
        
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")
        return False

def run_basic_tests():
    """Run basic functionality tests"""
    print("🧪 Running basic tests...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Import RAG modules
    total_tests += 1
    try:
        from document_processor import document_processor
        from rag_api import rag_bp
        from ai_assistant_integration import rag_assistant
        print("✅ RAG modules import successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ RAG module import failed: {str(e)}")
    
    # Test 2: Database models
    total_tests += 1
    try:
        from models import RFPO, UploadedFile, DocumentChunk
        print("✅ Database models loaded successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Database models failed: {str(e)}")
    
    # Test 3: Text extraction
    total_tests += 1
    try:
        test_text = "This is a test document with some content."
        chunks = document_processor.chunk_text(test_text, chunk_size=50)
        if chunks and len(chunks) > 0:
            print("✅ Text chunking works")
            tests_passed += 1
        else:
            print("❌ Text chunking returned no chunks")
    except Exception as e:
        print(f"❌ Text chunking failed: {str(e)}")
    
    # Test 4: Embedding model loading (optional, as it downloads model)
    total_tests += 1
    try:
        # Just check if we can initialize without loading
        processor = document_processor.__class__()
        print("✅ Document processor initializes")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Document processor initialization failed: {str(e)}")
    
    print(f"\n🎯 Test Results: {tests_passed}/{total_tests} tests passed")
    return tests_passed == total_tests

def main():
    """Main setup function"""
    print("🚀 Setting up RAG functionality for RFPO application")
    print("=" * 60)
    
    # Step 1: Check current dependencies
    deps_available, missing = check_dependencies()
    
    # Step 2: Install if needed
    if not deps_available:
        print("\n📦 Installing missing dependencies...")
        if not install_dependencies(missing):
            print("❌ Setup failed - could not install dependencies")
            print("💡 Try installing manually:")
            for package in missing:
                print(f"   pip install {package}")
            return False
        
        print("\n🔄 Rechecking dependencies after installation...")
        # Recheck after installation
        deps_available, still_missing = check_dependencies()
        
        if still_missing:
            print(f"\n⚠️  Some packages still missing: {', '.join(still_missing)}")
            print("💡 This might be due to:")
            print("   - Network connectivity issues")
            print("   - Package name variations")
            print("   - System-specific requirements")
            print("\n🔧 Try manual installation:")
            for package in still_missing:
                print(f"   pip install {package} --upgrade --no-cache-dir")
            
            # Continue anyway if most dependencies are available
            if len(still_missing) <= 2:  # Allow up to 2 missing packages
                print("\n⚡ Continuing setup with available packages...")
                deps_available = True
            else:
                return False
    
    if not deps_available:
        print("❌ Setup failed - too many dependencies missing")
        return False
    
    # Step 3: Initialize database
    print("\n" + "=" * 60)
    if not initialize_database():
        print("❌ Setup failed - database initialization failed")
        return False
    
    # Step 4: Run tests
    print("\n" + "=" * 60)
    if not run_basic_tests():
        print("⚠️  Setup completed with some test failures")
        print("💡 The system should still work, but check the errors above")
    else:
        print("🎉 Setup completed successfully!")
    
    # Step 5: Show next steps
    print("\n" + "=" * 60)
    print("📋 Next Steps:")
    print("1. Start the application: python app.py")
    print("2. Create an RFPO using the web interface")
    print("3. Upload files to the RFPO using the new API")
    print("4. Test the RAG search functionality")
    print("5. Try the enhanced AI assistant")
    
    print("\n📚 Documentation:")
    print("- Read RAG_IMPLEMENTATION.md for detailed usage")
    print("- Check init_rag_db.py --info for database status")
    print("- Use the RAG API endpoints for file operations")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
