#!/usr/bin/env python3
"""
Demo script to show email template rendering without sending actual emails
This demonstrates how the templates will look when rendered
"""
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

def demo_email_templates():
    """Demonstrate email template rendering"""
    print("=" * 60)
    print("RFPO Email Templates Demo")
    print("=" * 60)
    
    # Setup Jinja2 environment
    template_dir = os.path.join(os.path.dirname(__file__), 'templates', 'email')
    jinja_env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )
    
    print(f"Template directory: {template_dir}")
    print(f"Available templates: {jinja_env.list_templates()}")
    
    # Demo data
    demo_data = {
        'user_name': 'John Doe',
        'user_email': 'john.doe@example.com',
        'temp_password': 'TempPass123!',
        'login_url': 'http://localhost:5000/login',
        'support_email': 'support@rfpo.com',
        'current_date': datetime.now().strftime('%Y-%m-%d'),
        'current_year': datetime.now().year,
        'rfpo_id': 'RFPO-TestProj-2025-01-15-N01',
        'approval_type': 'Technical Review',
        'rfpo_url': 'http://localhost:5000/admin/rfpo/123/edit',
        'project_name': 'Advanced Materials Research',
        'role': 'Project Member',
        'projects_url': 'http://localhost:5000/admin/projects'
    }
    
    templates_to_demo = [
        ('welcome.html', 'Welcome Email'),
        ('approval_notification.html', 'Approval Notification'),
        ('user_added_to_project.html', 'User Added to Project')
    ]
    
    for template_name, description in templates_to_demo:
        print(f"\n{'-' * 60}")
        print(f"📧 {description} ({template_name})")
        print(f"{'-' * 60}")
        
        try:
            template = jinja_env.get_template(template_name)
            rendered_html = template.render(**demo_data)
            
            # Save rendered template to file for viewing
            output_file = f"demo_output_{template_name}"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rendered_html)
            
            print(f"✅ Template rendered successfully!")
            print(f"📄 Output saved to: {output_file}")
            print(f"🌐 Open in browser to preview the email")
            
            # Show a snippet of the rendered content
            if 'John Doe' in rendered_html:
                print("✅ User name correctly inserted")
            if demo_data['temp_password'] in rendered_html:
                print("✅ Temporary password correctly inserted")
            if demo_data['rfpo_id'] in rendered_html:
                print("✅ RFPO ID correctly inserted")
            if demo_data['project_name'] in rendered_html:
                print("✅ Project name correctly inserted")
                
        except Exception as e:
            print(f"❌ Error rendering template: {str(e)}")
    
    print(f"\n{'=' * 60}")
    print("🎉 Email template demo completed!")
    print("=" * 60)
    print("\nTo use the email service:")
    print("1. Configure email settings in your .env file")
    print("2. Run: python3 test_email_service.py")
    print("3. Create users in the admin panel to trigger welcome emails")
    print("\nTemplate files can be customized in templates/email/")

if __name__ == '__main__':
    demo_email_templates()

