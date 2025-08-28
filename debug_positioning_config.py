#!/usr/bin/env python3
"""
Debug the positioning configuration in the database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from custom_admin import create_app
from models import PDFPositioning, Consortium

def debug_positioning_config():
    """Debug positioning configuration"""
    app = create_app()
    
    with app.app_context():
        print("🔍 DEBUGGING POSITIONING CONFIGURATION")
        print("=" * 60)
        
        # Check all consortiums
        consortiums = Consortium.query.all()
        print(f"\n📋 Found {len(consortiums)} consortiums:")
        for consortium in consortiums:
            print(f"   {consortium.consort_id}: {consortium.abbrev}")
        
        # Check positioning configs
        configs = PDFPositioning.query.all()
        print(f"\n⚙️  Found {len(configs)} positioning configurations:")
        for config in configs:
            print(f"   ID {config.id}: {config.consortium_id}:{config.template_name} active={config.active}")
            if config.positioning_data:
                try:
                    import json
                    data = json.loads(config.positioning_data)
                    print(f"      Fields: {list(data.keys())}")
                except:
                    print(f"      Data: {config.positioning_data[:100]}...")
            else:
                print(f"      No positioning data")
        
        # Check specifically for the test consortium (00000014)
        test_consortium_id = "00000014"
        test_config = PDFPositioning.query.filter_by(
            consortium_id=test_consortium_id,
            template_name='po_template',
            active=True
        ).first()
        
        print(f"\n🎯 TEST CONSORTIUM ({test_consortium_id}) CONFIG:")
        if test_config:
            print(f"   ✅ Found config ID {test_config.id}")
            print(f"   Template: {test_config.template_name}")
            print(f"   Active: {test_config.active}")
            
            if test_config.positioning_data:
                try:
                    import json
                    data = json.loads(test_config.positioning_data)
                    print(f"   Positioning data ({len(data)} fields):")
                    for field_name, field_data in data.items():
                        if isinstance(field_data, dict):
                            x = field_data.get('x', 'N/A')
                            y = field_data.get('y', 'N/A')
                            visible = field_data.get('visible', 'N/A')
                            print(f"      {field_name}: x={x}, y={y}, visible={visible}")
                        else:
                            print(f"      {field_name}: {field_data}")
                except Exception as e:
                    print(f"   ❌ Error parsing positioning data: {e}")
                    print(f"   Raw data: {test_config.positioning_data}")
            else:
                print(f"   ⚠️  No positioning data found")
        else:
            print(f"   ❌ No active config found for consortium {test_consortium_id}")
            
            # Check if there are any configs for this consortium (inactive)
            all_configs = PDFPositioning.query.filter_by(
                consortium_id=test_consortium_id,
                template_name='po_template'
            ).all()
            
            print(f"   Checking all configs for {test_consortium_id}:")
            for config in all_configs:
                print(f"      ID {config.id}: active={config.active}")

if __name__ == "__main__":
    debug_positioning_config()
