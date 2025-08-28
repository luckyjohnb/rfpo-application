#!/usr/bin/env python3
"""
DEBUG RFPO DATA
Check what RFPO data exists in the database
"""
import sqlite3

def debug_rfpo_data():
    print("🔍 DEBUG RFPO DATA")
    print("="*50)
    
    try:
        # Connect to database
        conn = sqlite3.connect('instance/rfpo.db')
        cursor = conn.cursor()
        
        # Check RFPO table
        print("📋 Checking RFPO records...")
        cursor.execute("SELECT COUNT(*) FROM rfpo")
        rfpo_count = cursor.fetchone()[0]
        print(f"   Total RFPOs: {rfpo_count}")
        
        if rfpo_count > 0:
            # Get first few RFPOs
            cursor.execute("SELECT rfpo_id, consortium_id, requester_id FROM rfpo LIMIT 5")
            rfpos = cursor.fetchall()
            print("   First few RFPOs:")
            for rfpo in rfpos:
                print(f"     ID: {rfpo[0]}, Consortium: {rfpo[1]}, Requester: {rfpo[2]}")
        
        # Check specific RFPO ID 1
        print("\n📋 Checking RFPO ID 1...")
        cursor.execute("SELECT rfpo_id, consortium_id, requester_id, po_reference FROM rfpo WHERE id = 1")
        rfpo_1 = cursor.fetchone()
        
        if rfpo_1:
            print(f"   RFPO 1 found: ID={rfpo_1[0]}, Consortium={rfpo_1[1]}, Requester={rfpo_1[2]}, Reference={rfpo_1[3]}")
        else:
            print("   ❌ RFPO ID 1 not found!")
        
        # Check positioning data
        print("\n📋 Checking positioning data...")
        cursor.execute("SELECT COUNT(*) FROM pdf_positioning")
        pos_count = cursor.fetchone()[0]
        print(f"   Total positioning records: {pos_count}")
        
        if pos_count > 0:
            cursor.execute("SELECT id, consortium_id, template_name FROM pdf_positioning LIMIT 5")
            pos_records = cursor.fetchall()
            print("   Positioning records:")
            for pos in pos_records:
                print(f"     ID: {pos[0]}, Consortium: {pos[1]}, Template: {pos[2]}")
        
        # Check specific positioning record ID 1
        print("\n📋 Checking positioning record ID 1...")
        cursor.execute("SELECT id, consortium_id, template_name, positioning_data FROM pdf_positioning WHERE id = 1")
        pos_1 = cursor.fetchone()
        
        if pos_1:
            print(f"   Positioning 1 found: ID={pos_1[0]}, Consortium={pos_1[1]}, Template={pos_1[2]}")
            pos_data = pos_1[3]
            print(f"   Positioning data length: {len(pos_data) if pos_data else 0} chars")
            if pos_data and len(pos_data) > 0:
                print(f"   Positioning data preview: {pos_data[:200]}...")
        else:
            print("   ❌ Positioning record ID 1 not found!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    debug_rfpo_data()
