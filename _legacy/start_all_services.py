#!/usr/bin/env python3
"""
Start All RFPO Services
Simple script to start all three services for development
"""

import subprocess
import sys
import time
import threading
from pathlib import Path

def start_service(name, command, port):
    """Start a service in a separate thread"""
    print(f"🚀 Starting {name} on port {port}...")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        for line in iter(process.stdout.readline, ''):
            print(f"[{name}] {line.strip()}")
            
    except Exception as e:
        print(f"❌ Error starting {name}: {e}")

def main():
    """Start all services"""
    print("=" * 60)
    print("🚀 STARTING ALL RFPO SERVICES")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("custom_admin.py").exists():
        print("❌ Error: Please run this script from the rfpo-application directory")
        sys.exit(1)
    
    # Start services in separate threads
    services = [
        ("API Server", "python3 api/api_server.py", 5002),
        ("Admin Panel", "python3 custom_admin.py", 5111),
        ("User App", "python3 app.py", 5000)
    ]
    
    threads = []
    for name, command, port in services:
        thread = threading.Thread(target=start_service, args=(name, command, port))
        thread.daemon = True
        thread.start()
        threads.append(thread)
        time.sleep(2)  # Stagger startup
    
    print("\n" + "=" * 60)
    print("✅ ALL SERVICES STARTED")
    print("=" * 60)
    print("🌐 User Application:  http://localhost:5000")
    print("⚙️  Admin Panel:      http://localhost:5111")
    print("🔌 API Server:       http://localhost:5002/api")
    print("=" * 60)
    print("Press Ctrl+C to stop all services")
    print("=" * 60)
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all services...")
        sys.exit(0)

if __name__ == '__main__':
    main()


