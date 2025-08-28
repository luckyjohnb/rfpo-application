#!/usr/bin/env python3
"""
Custom RFPO Admin Panel - NO Flask-Admin Dependencies
Built from scratch to avoid WTForms compatibility issues.
"""

from flask import Flask, request, redirect, url_for, flash, render_template, jsonify, send_file, Response
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import desc
import json
import os
from datetime import datetime

# Import your models
from models import db, User, Consortium, Team, RFPO, RFPOLineItem, UploadedFile, DocumentChunk, Project, Vendor, VendorSite, List, UserTeam, PDFPositioning
from pdf_generator import RFPOPDFGenerator

def create_app():
    """Create Flask application with custom admin panel"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'rfpo-admin-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rfpo_admin.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Helper functions
    def format_json_field(value):
        """Format JSON field for display"""
        if not value:
            return 'None'
        try:
            if isinstance(value, str):
                data = json.loads(value)
            else:
                data = value
            return ', '.join(data) if isinstance(data, list) else str(data)
        except:
            return str(value)
    
    def parse_comma_list(value):
        """Parse comma-separated string to list"""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def generate_next_id(model_class, id_field, prefix='', length=8):
        """Generate next auto-incremented ID for external ID fields"""
        try:
            # Get the highest existing ID and increment
            max_record = db.session.query(model_class).order_by(getattr(model_class, id_field).desc()).first()
            if max_record:
                current_id = getattr(max_record, id_field)
                try:
                    # Extract numeric part and increment
                    current_num = int(current_id.replace(prefix, '').lstrip('0') or '0')
                    next_num = current_num + 1
                except (ValueError, AttributeError):
                    # If parsing fails, use count + 1
                    next_num = db.session.query(model_class).count() + 1
            else:
                next_num = 1
            
            # Keep trying until we find a unique ID
            for attempt in range(100):  # Prevent infinite loop
                candidate_id = f"{prefix}{(next_num + attempt):0{length}d}" if prefix else f"{(next_num + attempt):0{length}d}"
                existing = db.session.query(model_class).filter(getattr(model_class, id_field) == candidate_id).first()
                if not existing:
                    return candidate_id
            
            # Final fallback to timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            return f"{prefix}{timestamp}" if prefix else timestamp
            
        except Exception as e:
            # Fallback to timestamp-based ID
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            return f"{prefix}{timestamp}" if prefix else timestamp
    
    def handle_file_upload(file, upload_folder):
        """Handle file upload and return filename"""
        if file and file.filename and file.filename != '':
            try:
                # Secure the filename
                filename = secure_filename(file.filename)
                
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = f"{timestamp}{filename}"
                
                # Ensure upload folder exists
                os.makedirs(upload_folder, exist_ok=True)
                
                # Save file
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                
                return filename
            except Exception as e:
                print(f"File upload error: {e}")
                return None
        return None
    
    def _process_vendor_site_id(vendor_site_id_str):
        """Process vendor_site_id which could be a regular ID or special 'vendor_X' format"""
        if not vendor_site_id_str:
            return None
        
        # If it's the special vendor primary contact format (vendor_123), 
        # we'll store None since the vendor's primary contact info is already in the vendor record
        if vendor_site_id_str.startswith('vendor_'):
            return None
        
        # Otherwise, convert to integer for regular vendor site IDs
        try:
            return int(vendor_site_id_str)
        except (ValueError, TypeError):
            return None
    
    # Authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            user = User.query.filter_by(email=email, active=True).first()
            
            if user and check_password_hash(user.password_hash, password):
                if user.is_super_admin() or user.is_rfpo_admin():
                    login_user(user)
                    flash(f'Welcome {user.get_display_name()}! 🎉', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('❌ You do not have admin privileges.', 'error')
            else:
                flash('❌ Invalid email or password.', 'error')
        
        return render_template('admin/login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('👋 You have been logged out.', 'info')
        return redirect(url_for('login'))
    
    @app.route('/')
    @login_required
    def dashboard():
        """Main dashboard"""
        stats = {
            'consortiums': Consortium.query.filter_by(active=True).count(),
            'teams': Team.query.filter_by(active=True).count(),
            'rfpos': RFPO.query.count(),
            'users': User.query.filter_by(active=True).count(),
            'vendors': Vendor.query.filter_by(active=True).count(),
            'projects': Project.query.filter_by(active=True).count(),
            'uploaded_files': UploadedFile.query.count(),
        }
        
        recent_rfpos = RFPO.query.order_by(desc(RFPO.created_at)).limit(5).all()
        recent_files = UploadedFile.query.order_by(desc(UploadedFile.uploaded_at)).limit(5).all()
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             recent_rfpos=recent_rfpos, 
                             recent_files=recent_files)
    
    # Consortium routes
    @app.route('/consortiums')
    @login_required
    def consortiums():
        """List all consortiums with counts"""
        consortiums = Consortium.query.all()
        
        # Calculate counts for each consortium
        for consortium in consortiums:
            # Count projects associated with this consortium
            consortium.project_count = Project.query.filter(
                Project.consortium_ids.like(f'%{consortium.consort_id}%'),
                Project.active == True
            ).count()
            
            # Count RFPOs through teams associated with this consortium
            consortium.rfpo_count = RFPO.query.join(Team).filter(
                Team.consortium_consort_id == consortium.consort_id
            ).count()
            
            # Count viewers and admins
            consortium.viewer_count = len(consortium.get_rfpo_viewer_users())
            consortium.admin_count = len(consortium.get_rfpo_admin_users())
        
        return render_template('admin/consortiums.html', consortiums=consortiums, format_json=format_json_field)
    
    @app.route('/consortium/new', methods=['GET', 'POST'])
    @login_required
    def consortium_new():
        """Create new consortium"""
        if request.method == 'POST':
            try:
                # Auto-generate consortium ID
                consort_id = generate_next_id(Consortium, 'consort_id', '', 8)
                
                # Handle logo upload
                logo_filename = None
                if 'logo_file' in request.files:
                    logo_file = request.files['logo_file']
                    if logo_file.filename and logo_file.filename != '':
                        logo_filename = handle_file_upload(logo_file, 'uploads/logos')
                        if logo_filename:
                            flash(f'📷 Logo uploaded: {logo_filename}', 'info')
                
                # Handle terms PDF upload
                terms_pdf_filename = None
                if 'terms_pdf_file' in request.files:
                    terms_pdf_file = request.files['terms_pdf_file']
                    if terms_pdf_file.filename and terms_pdf_file.filename != '':
                        # Validate it's a PDF file
                        if terms_pdf_file.filename.lower().endswith('.pdf'):
                            terms_pdf_filename = handle_file_upload(terms_pdf_file, 'uploads/terms')
                            if terms_pdf_filename:
                                flash(f'📄 Terms PDF uploaded: {terms_pdf_filename}', 'info')
                        else:
                            flash('❌ Terms file must be a PDF', 'error')
                
                # Build invoicing address from structured inputs
                invoicing_parts = []
                if request.form.get('invoicing_street'):
                    invoicing_parts.append(request.form.get('invoicing_street'))
                
                city_state_zip = []
                if request.form.get('invoicing_city'):
                    city_state_zip.append(request.form.get('invoicing_city'))
                if request.form.get('invoicing_state'):
                    city_state_zip[-1] = f"{city_state_zip[-1]}, {request.form.get('invoicing_state')}" if city_state_zip else request.form.get('invoicing_state')
                if request.form.get('invoicing_zip'):
                    city_state_zip[-1] = f"{city_state_zip[-1]} {request.form.get('invoicing_zip')}" if city_state_zip else request.form.get('invoicing_zip')
                
                if city_state_zip:
                    invoicing_parts.extend(city_state_zip)
                if request.form.get('invoicing_country'):
                    invoicing_parts.append(request.form.get('invoicing_country'))
                
                invoicing_address = '\n'.join(invoicing_parts)
                
                consortium = Consortium(
                    consort_id=consort_id,
                    name=request.form.get('name'),
                    abbrev=request.form.get('abbrev'),
                    logo=logo_filename,
                    terms_pdf=terms_pdf_filename,
                    require_approved_vendors=bool(request.form.get('require_approved_vendors')),
                    non_government_project_id=request.form.get('non_government_project_id') or None,
                    invoicing_address=invoicing_address,
                    doc_fax_name=request.form.get('doc_fax_name'),
                    doc_fax_number=request.form.get('doc_fax_number'),
                    doc_email_name=request.form.get('doc_email_name'),
                    doc_email_address=request.form.get('doc_email_address'),
                    doc_post_name=request.form.get('doc_post_name'),
                    doc_post_address=request.form.get('doc_post_address'),
                    po_email=request.form.get('po_email'),
                    active=bool(request.form.get('active', True)),
                    created_by=current_user.get_display_name()
                )
                
                # Handle JSON fields from user selection interface
                viewer_users = parse_comma_list(request.form.get('rfpo_viewer_user_ids'))
                admin_users = parse_comma_list(request.form.get('rfpo_admin_user_ids'))
                
                if viewer_users:
                    consortium.set_rfpo_viewer_users(viewer_users)
                if admin_users:
                    consortium.set_rfpo_admin_users(admin_users)
                
                db.session.add(consortium)
                db.session.commit()
                
                flash('✅ Consortium created successfully!', 'success')
                return redirect(url_for('consortiums'))
                
            except Exception as e:
                db.session.rollback()  # Important: rollback the failed transaction
                flash(f'❌ Error creating consortium: {str(e)}', 'error')
        
        # Get non-government projects for dropdown
        non_gov_projects = Project.query.filter_by(gov_funded=False, active=True).all()
        return render_template('admin/consortium_form.html', consortium=None, action='Create', non_gov_projects=non_gov_projects)
    
    @app.route('/consortium/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def consortium_edit(id):
        """Edit consortium"""
        consortium = Consortium.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                # Handle logo upload
                if 'logo_file' in request.files:
                    logo_file = request.files['logo_file']
                    if logo_file.filename:
                        # Delete old logo if exists
                        if consortium.logo:
                            old_logo_path = os.path.join('uploads/logos', consortium.logo)
                            if os.path.exists(old_logo_path):
                                os.remove(old_logo_path)
                        
                        # Upload new logo
                        consortium.logo = handle_file_upload(logo_file, 'uploads/logos')
                
                # Handle terms PDF upload
                if 'terms_pdf_file' in request.files:
                    terms_pdf_file = request.files['terms_pdf_file']
                    if terms_pdf_file.filename:
                        # Validate it's a PDF file
                        if terms_pdf_file.filename.lower().endswith('.pdf'):
                            # Delete old terms PDF if exists
                            if consortium.terms_pdf:
                                old_terms_path = os.path.join('uploads/terms', consortium.terms_pdf)
                                if os.path.exists(old_terms_path):
                                    os.remove(old_terms_path)
                            
                            # Upload new terms PDF
                            consortium.terms_pdf = handle_file_upload(terms_pdf_file, 'uploads/terms')
                            if consortium.terms_pdf:
                                flash(f'📄 Terms PDF updated: {consortium.terms_pdf}', 'info')
                        else:
                            flash('❌ Terms file must be a PDF', 'error')
                
                # Build invoicing address from structured inputs
                invoicing_parts = []
                if request.form.get('invoicing_street'):
                    invoicing_parts.append(request.form.get('invoicing_street'))
                
                city_state_zip = []
                if request.form.get('invoicing_city'):
                    city_state_zip.append(request.form.get('invoicing_city'))
                if request.form.get('invoicing_state'):
                    city_state_zip[-1] = f"{city_state_zip[-1]}, {request.form.get('invoicing_state')}" if city_state_zip else request.form.get('invoicing_state')
                if request.form.get('invoicing_zip'):
                    city_state_zip[-1] = f"{city_state_zip[-1]} {request.form.get('invoicing_zip')}" if city_state_zip else request.form.get('invoicing_zip')
                
                if city_state_zip:
                    invoicing_parts.extend(city_state_zip)
                if request.form.get('invoicing_country'):
                    invoicing_parts.append(request.form.get('invoicing_country'))
                
                consortium.name = request.form.get('name')
                consortium.abbrev = request.form.get('abbrev')
                consortium.require_approved_vendors = bool(request.form.get('require_approved_vendors'))
                consortium.non_government_project_id = request.form.get('non_government_project_id') or None
                consortium.invoicing_address = '\n'.join(invoicing_parts)
                consortium.doc_fax_name = request.form.get('doc_fax_name')
                consortium.doc_fax_number = request.form.get('doc_fax_number')
                consortium.doc_email_name = request.form.get('doc_email_name')
                consortium.doc_email_address = request.form.get('doc_email_address')
                consortium.doc_post_name = request.form.get('doc_post_name')
                consortium.doc_post_address = request.form.get('doc_post_address')
                consortium.po_email = request.form.get('po_email')
                consortium.active = bool(request.form.get('active'))
                consortium.updated_by = current_user.get_display_name()
                
                # Handle JSON fields from user selection interface
                viewer_users = parse_comma_list(request.form.get('rfpo_viewer_user_ids'))
                admin_users = parse_comma_list(request.form.get('rfpo_admin_user_ids'))
                
                consortium.set_rfpo_viewer_users(viewer_users)
                consortium.set_rfpo_admin_users(admin_users)
                
                db.session.commit()
                
                flash('✅ Consortium updated successfully!', 'success')
                return redirect(url_for('consortiums'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error updating consortium: {str(e)}', 'error')
        
        # Pre-populate JSON fields for editing
        consortium.rfpo_viewer_user_ids_display = ', '.join(consortium.get_rfpo_viewer_users())
        consortium.rfpo_admin_user_ids_display = ', '.join(consortium.get_rfpo_admin_users())
        
        # Parse invoicing address for structured inputs
        if consortium.invoicing_address:
            address_lines = consortium.invoicing_address.split('\n')
            consortium.invoicing_street = address_lines[0] if len(address_lines) > 0 else ''
            if len(address_lines) > 1:
                # Parse city, state, zip from second line
                city_state_zip = address_lines[1]
                parts = city_state_zip.split(',')
                consortium.invoicing_city = parts[0].strip() if len(parts) > 0 else ''
                if len(parts) > 1:
                    state_zip = parts[1].strip().split(' ')
                    consortium.invoicing_state = state_zip[0] if len(state_zip) > 0 else ''
                    consortium.invoicing_zip = state_zip[1] if len(state_zip) > 1 else ''
            consortium.invoicing_country = address_lines[2] if len(address_lines) > 2 else 'United States'
        
        non_gov_projects = Project.query.filter_by(gov_funded=False, active=True).all()
        return render_template('admin/consortium_form.html', consortium=consortium, action='Edit', non_gov_projects=non_gov_projects)
    
    @app.route('/consortium/<int:id>/delete', methods=['POST'])
    @login_required
    def consortium_delete(id):
        """Delete consortium"""
        consortium = Consortium.query.get_or_404(id)
        try:
            db.session.delete(consortium)
            db.session.commit()
            flash('✅ Consortium deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting consortium: {str(e)}', 'error')
        return redirect(url_for('consortiums'))
    
    @app.route('/uploads/logos/<filename>')
    def uploaded_logo(filename):
        """Serve uploaded logo files"""
        from flask import send_from_directory
        return send_from_directory('uploads/logos', filename)
    
    @app.route('/uploads/terms/<filename>')
    def uploaded_terms(filename):
        """Serve uploaded terms PDF files"""
        from flask import send_from_directory
        return send_from_directory('uploads/terms', filename)
    
    # Teams routes
    @app.route('/teams')
    @login_required
    def teams():
        """List all teams with counts and consortium info"""
        teams = Team.query.all()
        
        # Calculate counts and consortium info for each team
        for team in teams:
            # Count projects associated with this team
            team.project_count = Project.query.filter_by(
                team_record_id=team.record_id,
                active=True
            ).count()
            
            # Count viewers and admins
            team.viewer_count = len(team.get_rfpo_viewer_users())
            team.admin_count = len(team.get_rfpo_admin_users())
            
            # Get consortium info for badge display
            if team.consortium_consort_id:
                consortium = Consortium.query.filter_by(consort_id=team.consortium_consort_id).first()
                if consortium:
                    team.consortium_name = consortium.name
                    team.consortium_abbrev = consortium.abbrev
                else:
                    team.consortium_name = team.consortium_consort_id
                    team.consortium_abbrev = team.consortium_consort_id
            else:
                team.consortium_name = None
                team.consortium_abbrev = None
        
        return render_template('admin/teams.html', teams=teams, format_json=format_json_field)
    
    @app.route('/team/new', methods=['GET', 'POST'])
    @login_required
    def team_new():
        """Create new team"""
        if request.method == 'POST':
            try:
                # Auto-generate team record ID
                record_id = generate_next_id(Team, 'record_id', '', 8)
                
                team = Team(
                    record_id=record_id,
                    name=request.form.get('name'),
                    abbrev=request.form.get('abbrev'),
                    description=request.form.get('description'),
                    consortium_consort_id=request.form.get('consortium_consort_id') or None,
                    active=bool(request.form.get('active', True)),
                    created_by=current_user.get_display_name()
                )
                
                # Handle JSON fields
                viewer_users = parse_comma_list(request.form.get('rfpo_viewer_user_ids'))
                admin_users = parse_comma_list(request.form.get('rfpo_admin_user_ids'))
                
                if viewer_users:
                    team.set_rfpo_viewer_users(viewer_users)
                if admin_users:
                    team.set_rfpo_admin_users(admin_users)
                
                db.session.add(team)
                db.session.commit()
                
                flash('✅ Team created successfully!', 'success')
                return redirect(url_for('teams'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error creating team: {str(e)}', 'error')
        
        consortiums = Consortium.query.filter_by(active=True).all()
        return render_template('admin/team_form.html', team=None, action='Create', consortiums=consortiums)
    
    @app.route('/team/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def team_edit(id):
        """Edit team"""
        team = Team.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                team.record_id = request.form.get('record_id')
                team.name = request.form.get('name')
                team.abbrev = request.form.get('abbrev')
                team.description = request.form.get('description')
                team.consortium_consort_id = request.form.get('consortium_consort_id') or None
                team.active = bool(request.form.get('active'))
                team.updated_by = current_user.get_display_name()
                
                # Handle JSON fields
                viewer_users = parse_comma_list(request.form.get('rfpo_viewer_user_ids'))
                admin_users = parse_comma_list(request.form.get('rfpo_admin_user_ids'))
                
                team.set_rfpo_viewer_users(viewer_users)
                team.set_rfpo_admin_users(admin_users)
                
                db.session.commit()
                
                flash('✅ Team updated successfully!', 'success')
                return redirect(url_for('teams'))
                
            except Exception as e:
                flash(f'❌ Error updating team: {str(e)}', 'error')
        
        # Pre-populate JSON fields for editing
        team.rfpo_viewer_user_ids_display = ', '.join(team.get_rfpo_viewer_users())
        team.rfpo_admin_user_ids_display = ', '.join(team.get_rfpo_admin_users())
        
        consortiums = Consortium.query.filter_by(active=True).all()
        return render_template('admin/team_form.html', team=team, action='Edit', consortiums=consortiums)
    
    @app.route('/team/<int:id>/delete', methods=['POST'])
    @login_required
    def team_delete(id):
        """Delete team"""
        team = Team.query.get_or_404(id)
        try:
            db.session.delete(team)
            db.session.commit()
            flash('✅ Team deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting team: {str(e)}', 'error')
        return redirect(url_for('teams'))
    
    # Users routes
    @app.route('/users')
    @login_required
    def users():
        """List all users"""
        users = User.query.all()
        return render_template('admin/users.html', users=users, format_json=format_json_field)
    
    @app.route('/user/new', methods=['GET', 'POST'])
    @login_required
    def user_new():
        """Create new user"""
        if request.method == 'POST':
            try:
                from werkzeug.security import generate_password_hash
                
                # Auto-generate user record ID
                record_id = generate_next_id(User, 'record_id', '', 8)
                
                user = User(
                    record_id=record_id,
                    fullname=request.form.get('fullname'),
                    email=request.form.get('email'),
                    password_hash=generate_password_hash(request.form.get('password', 'changeme123')),
                    sex=request.form.get('sex'),
                    company_code=request.form.get('company_code'),
                    company=request.form.get('company'),
                    position=request.form.get('position'),
                    department=request.form.get('department'),
                    phone=request.form.get('phone'),
                    active=bool(request.form.get('active', True)),
                    agreed_to_terms=bool(request.form.get('agreed_to_terms')),
                    created_by=current_user.get_display_name()
                )
                
                # Handle permissions from checkboxes
                permissions = request.form.getlist('permissions')  # Get all checked permission values
                if permissions:
                    user.set_permissions(permissions)
                
                db.session.add(user)
                db.session.commit()
                
                flash('✅ User created successfully!', 'success')
                return redirect(url_for('users'))
                
            except Exception as e:
                flash(f'❌ Error creating user: {str(e)}', 'error')
        
        return render_template('admin/user_form.html', user=None, action='Create')
    
    @app.route('/user/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def user_edit(id):
        """Edit user"""
        user = User.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                user.fullname = request.form.get('fullname')
                user.email = request.form.get('email')
                user.sex = request.form.get('sex')
                user.company_code = request.form.get('company_code')
                user.company = request.form.get('company')
                user.position = request.form.get('position')
                user.department = request.form.get('department')
                user.phone = request.form.get('phone')
                user.active = bool(request.form.get('active'))
                user.agreed_to_terms = bool(request.form.get('agreed_to_terms'))
                user.updated_by = current_user.get_display_name()
                
                # Handle permissions from checkboxes
                permissions = request.form.getlist('permissions')
                user.set_permissions(permissions)
                
                db.session.commit()
                
                flash('✅ User updated successfully!', 'success')
                return redirect(url_for('users'))
                
            except Exception as e:
                flash(f'❌ Error updating user: {str(e)}', 'error')
        
        return render_template('admin/user_form.html', user=user, action='Edit')
    
    @app.route('/user/<int:id>/delete', methods=['POST'])
    @login_required
    def user_delete(id):
        """Delete user"""
        user = User.query.get_or_404(id)
        try:
            db.session.delete(user)
            db.session.commit()
            flash('✅ User deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting user: {str(e)}', 'error')
        return redirect(url_for('users'))
    
    # RFPOs routes
    @app.route('/rfpos')
    @login_required
    def rfpos():
        """List all RFPOs"""
        rfpos = RFPO.query.all()
        return render_template('admin/rfpos.html', rfpos=rfpos)
    
    @app.route('/rfpo/new', methods=['GET'])
    @login_required
    def rfpo_new():
        """Start RFPO creation process - redirect to stage 1"""
        return redirect(url_for('rfpo_create_stage1'))
    
    @app.route('/rfpo/create/stage1', methods=['GET', 'POST'])
    @login_required
    def rfpo_create_stage1():
        """RFPO Creation Stage 1: Select Consortium and Project"""
        if request.method == 'POST':
            try:
                consortium_id = request.form.get('consortium_id')
                project_id = request.form.get('project_id')
                
                if not consortium_id or not project_id:
                    flash('❌ Please select both consortium and project.', 'error')
                    return redirect(url_for('rfpo_create_stage1'))
                
                # Store selections in session for next stage
                from flask import session
                session['rfpo_consortium_id'] = consortium_id
                session['rfpo_project_id'] = project_id
                
                return redirect(url_for('rfpo_create_stage2'))
                
            except Exception as e:
                flash(f'❌ Error in stage 1: {str(e)}', 'error')
        
        consortiums = Consortium.query.filter_by(active=True).all()
        return render_template('admin/rfpo_stage1.html', consortiums=consortiums)
    
    @app.route('/rfpo/create/stage2', methods=['GET', 'POST'])
    @login_required
    def rfpo_create_stage2():
        """RFPO Creation Stage 2: Basic Information and Vendor Selection"""
        from flask import session
        
        consortium_id = session.get('rfpo_consortium_id')
        project_id = session.get('rfpo_project_id')
        
        if not consortium_id or not project_id:
            flash('❌ Please start from stage 1.', 'error')
            return redirect(url_for('rfpo_create_stage1'))
        
        consortium = Consortium.query.filter_by(consort_id=consortium_id).first()
        project = Project.query.filter_by(project_id=project_id).first()
        
        if request.method == 'POST':
            try:
                # Generate RFPO ID based on project
                today = datetime.now()
                date_str = today.strftime('%Y-%m-%d')
                existing_count = RFPO.query.filter(
                    RFPO.rfpo_id.like(f'RFPO-{project.ref}-%{date_str}%')
                ).count()
                rfpo_id = f"RFPO-{project.ref}-{date_str}-N{existing_count + 1:02d}"
                
                # Get team from project or use default
                team = Team.query.filter_by(record_id=project.team_record_id).first() if project.team_record_id else None
                if not team:
                    team = Team.query.filter_by(active=True).first()
                
                if not team:
                    flash('❌ No active teams available.', 'error')
                    return redirect(url_for('rfpo_create_stage1'))
                
                # Create RFPO with enhanced model
                rfpo = RFPO(
                    rfpo_id=rfpo_id,
                    title=request.form.get('title'),
                    description=request.form.get('description'),
                    project_id=project.project_id,
                    consortium_id=consortium.consort_id,
                    team_id=team.id,
                    government_agreement_number=request.form.get('government_agreement_number'),
                    requestor_id=current_user.record_id,
                    requestor_tel=request.form.get('requestor_tel'),
                    requestor_location=request.form.get('requestor_location'),
                    shipto_name=request.form.get('shipto_name'),
                    shipto_tel=request.form.get('shipto_tel'),
                    shipto_address=request.form.get('shipto_address'),
                    invoice_address=consortium.invoicing_address or """United States Council for Automotive 
Research LLC
Attn: Accounts Payable
3000 Town Center Building, Suite 35
Southfield, MI  48075""",
                    delivery_date=datetime.strptime(request.form.get('delivery_date'), '%Y-%m-%d').date() if request.form.get('delivery_date') else None,
                    delivery_type=request.form.get('delivery_type'),
                    delivery_payment=request.form.get('delivery_payment'),
                    delivery_routing=request.form.get('delivery_routing'),
                    payment_terms=request.form.get('payment_terms', 'Net 30'),
                    vendor_id=int(request.form.get('vendor_id')) if request.form.get('vendor_id') else None,
                    vendor_site_id=_process_vendor_site_id(request.form.get('vendor_site_id')),
                    created_by=current_user.get_display_name()
                )
                
                db.session.add(rfpo)
                db.session.commit()
                
                # Clear session data
                session.pop('rfpo_consortium_id', None)
                session.pop('rfpo_project_id', None)
                
                flash('✅ RFPO created successfully! You can now add line items.', 'success')
                return redirect(url_for('rfpo_edit', id=rfpo.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error creating RFPO: {str(e)}', 'error')
        
        teams = Team.query.filter_by(active=True).all()
        vendors = Vendor.query.filter_by(active=True).all()
        
        # Pre-fill form with current user data
        current_user_data = {
            'requestor_tel': current_user.phone,
            'requestor_location': f"{current_user.company or 'USCAR'}, {current_user.state or 'MI'}",
            'shipto_name': current_user.get_display_name(),
            'shipto_address': f"{current_user.company or 'USCAR'}, {current_user.state or 'MI'}"
        }
        
        return render_template('admin/rfpo_stage2.html', 
                             consortium=consortium, 
                             project=project,
                             teams=teams,
                             vendors=vendors,
                             current_user_data=current_user_data)
    
    @app.route('/rfpo/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def rfpo_edit(id):
        """Edit RFPO with line items"""
        rfpo = RFPO.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                # Update RFPO information - only update fields that are provided
                # This allows partial updates from different tabs
                
                # Basic Information fields (only update if provided)
                if 'title' in request.form and request.form.get('title') is not None:
                    rfpo.title = request.form.get('title')
                if 'description' in request.form:
                    rfpo.description = request.form.get('description')
                if 'government_agreement_number' in request.form:
                    rfpo.government_agreement_number = request.form.get('government_agreement_number')
                if 'requestor_tel' in request.form:
                    rfpo.requestor_tel = request.form.get('requestor_tel')
                if 'requestor_location' in request.form:
                    rfpo.requestor_location = request.form.get('requestor_location')
                if 'status' in request.form:
                    rfpo.status = request.form.get('status', 'Draft')
                if 'comments' in request.form:
                    rfpo.comments = request.form.get('comments')
                
                # Shipping Information fields
                if 'shipto_name' in request.form:
                    rfpo.shipto_name = request.form.get('shipto_name')
                if 'shipto_tel' in request.form:
                    rfpo.shipto_tel = request.form.get('shipto_tel')
                if 'shipto_address' in request.form:
                    rfpo.shipto_address = request.form.get('shipto_address')
                if 'delivery_date' in request.form:
                    rfpo.delivery_date = datetime.strptime(request.form.get('delivery_date'), '%Y-%m-%d').date() if request.form.get('delivery_date') else None
                if 'delivery_type' in request.form:
                    rfpo.delivery_type = request.form.get('delivery_type')
                if 'delivery_payment' in request.form:
                    rfpo.delivery_payment = request.form.get('delivery_payment')
                if 'delivery_routing' in request.form:
                    rfpo.delivery_routing = request.form.get('delivery_routing')
                if 'payment_terms' in request.form:
                    rfpo.payment_terms = request.form.get('payment_terms', 'Net 30')
                
                # Vendor Information fields
                if 'vendor_id' in request.form:
                    rfpo.vendor_id = int(request.form.get('vendor_id')) if request.form.get('vendor_id') else None
                if 'vendor_site_id' in request.form:
                    rfpo.vendor_site_id = _process_vendor_site_id(request.form.get('vendor_site_id'))
                
                # Always update audit fields
                rfpo.updated_by = current_user.get_display_name()
                
                # Handle cost sharing (only update if provided)
                if 'cost_share_description' in request.form:
                    rfpo.cost_share_description = request.form.get('cost_share_description')
                if 'cost_share_type' in request.form:
                    rfpo.cost_share_type = request.form.get('cost_share_type', 'total')
                if 'cost_share_amount' in request.form:
                    cost_share_amount = request.form.get('cost_share_amount')
                    if cost_share_amount:
                        try:
                            rfpo.cost_share_amount = float(cost_share_amount)
                        except ValueError:
                            rfpo.cost_share_amount = 0.00
                
                # Recalculate totals
                subtotal = sum(float(item.total_price) for item in rfpo.line_items)
                rfpo.subtotal = subtotal
                rfpo.total_amount = subtotal - float(rfpo.cost_share_amount or 0)
                
                db.session.commit()
                
                flash('✅ RFPO updated successfully!', 'success')
                return redirect(url_for('rfpo_edit', id=rfpo.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error updating RFPO: {str(e)}', 'error')
        
        teams = Team.query.filter_by(active=True).all()
        vendors = Vendor.query.filter_by(active=True).all()
        
        # Get project and consortium info
        project = Project.query.filter_by(project_id=rfpo.project_id).first()
        consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
        
        return render_template('admin/rfpo_edit.html', 
                             rfpo=rfpo, 
                             teams=teams, 
                             vendors=vendors,
                             project=project,
                             consortium=consortium)
    
    @app.route('/rfpo/<int:rfpo_id>/line-item/add', methods=['POST'])
    @login_required
    def rfpo_add_line_item(rfpo_id):
        """Add line item to RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        try:
            # Get next line number
            max_line = db.session.query(db.func.max(RFPOLineItem.line_number)).filter_by(rfpo_id=rfpo.id).scalar()
            next_line_number = (max_line or 0) + 1
            
            # Create line item
            line_item = RFPOLineItem(
                rfpo_id=rfpo.id,
                line_number=next_line_number,
                quantity=int(request.form.get('quantity', 1)),
                description=request.form.get('description', ''),
                unit_price=float(request.form.get('unit_price', 0.00)),
                is_capital_equipment=bool(request.form.get('is_capital_equipment')),
                capital_description=request.form.get('capital_description'),
                capital_serial_id=request.form.get('capital_serial_id'),
                capital_location=request.form.get('capital_location'),
                capital_condition=request.form.get('capital_condition')
            )
            
            # Handle capital equipment date
            capital_date = request.form.get('capital_acquisition_date')
            if capital_date:
                try:
                    line_item.capital_acquisition_date = datetime.strptime(capital_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            # Handle capital cost
            capital_cost = request.form.get('capital_acquisition_cost')
            if capital_cost:
                try:
                    line_item.capital_acquisition_cost = float(capital_cost)
                except ValueError:
                    pass
            
            line_item.calculate_total()
            
            db.session.add(line_item)
            db.session.flush()  # Flush to get the line item in the session
            
            # Update RFPO totals (recalculate from all line items)
            subtotal = sum(float(item.total_price) for item in rfpo.line_items)
            rfpo.subtotal = subtotal
            rfpo.total_amount = subtotal - float(rfpo.cost_share_amount or 0)
            
            db.session.commit()
            
            flash(f'✅ Line item #{next_line_number} added successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error adding line item: {str(e)}', 'error')
        
        return redirect(url_for('rfpo_edit', id=rfpo_id))
    
    @app.route('/rfpo/<int:rfpo_id>/line-item/<int:line_item_id>/delete', methods=['POST'])
    @login_required
    def rfpo_delete_line_item(rfpo_id, line_item_id):
        """Delete line item from RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_item = RFPOLineItem.query.get_or_404(line_item_id)
        
        if line_item.rfpo_id != rfpo.id:
            flash('❌ Line item does not belong to this RFPO.', 'error')
            return redirect(url_for('rfpo_edit', id=rfpo_id))
        
        try:
            db.session.delete(line_item)
            
            # Update RFPO totals
            subtotal = sum(float(item.total_price) for item in rfpo.line_items if item.id != line_item_id)
            rfpo.subtotal = subtotal
            rfpo.total_amount = subtotal - float(rfpo.cost_share_amount or 0)
            
            db.session.commit()
            
            flash(f'✅ Line item #{line_item.line_number} deleted successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error deleting line item: {str(e)}', 'error')
        
        return redirect(url_for('rfpo_edit', id=rfpo_id))
    
    @app.route('/rfpo/<int:rfpo_id>/generate-po-proof')
    @login_required
    def rfpo_generate_po_proof(rfpo_id):
        """Generate PO Proof PDF for RFPO using legacy template approach"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        try:
            # Get related data
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
            vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
            
            # Handle vendor_site_id - regular VendorSite ID or None (uses vendor primary contact)
            vendor_site = None
            if rfpo.vendor_site_id:
                try:
                    vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
                except (ValueError, TypeError):
                    vendor_site = None
                
            if not project or not consortium:
                flash('❌ Missing project or consortium information for PO Proof generation.', 'error')
                return redirect(url_for('rfpo_edit', id=rfpo_id))
            
            # Get positioning configuration for this consortium (if available)
            positioning_config = PDFPositioning.query.filter_by(
                consortium_id=consortium.consort_id,
                template_name='po_template',
                active=True
            ).first()
            
            # Generate PO Proof PDF following legacy pattern:
            # 1. Use po.pdf as background
            # 2. Add consortium logo
            # 3. Use po_page2.pdf for additional line items if needed  
            # 4. Merge consortium terms PDF
            pdf_generator = RFPOPDFGenerator(positioning_config=positioning_config)
            pdf_buffer = pdf_generator.generate_po_pdf(rfpo, consortium, project, vendor, vendor_site)
            
            # Prepare filename following legacy naming pattern
            date_str = datetime.now().strftime('%Y%m%d')
            filename = f"PO_PROOF_{rfpo.rfpo_id}_{date_str}.pdf"
            
            # Return PDF as response
            return Response(
                pdf_buffer.getvalue(),
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename="{filename}"',
                    'Content-Type': 'application/pdf'
                }
            )
            
        except Exception as e:
            print(f"PO Proof generation error: {e}")
            flash(f'❌ Error generating PO Proof: {str(e)}', 'error')
            return redirect(url_for('rfpo_edit', id=rfpo_id))
    
    @app.route('/rfpo/<int:rfpo_id>/generate-po')
    @login_required
    def rfpo_generate_po(rfpo_id):
        """Generate PO PDF for RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        try:
            # Get related data
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
            vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
            
            # Handle vendor_site_id - regular VendorSite ID or None (uses vendor primary contact)
            vendor_site = None
            if rfpo.vendor_site_id:
                try:
                    vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
                except (ValueError, TypeError):
                    vendor_site = None
                
            if not project or not consortium:
                flash('❌ Missing project or consortium information for PDF generation.', 'error')
                return redirect(url_for('rfpo_edit', id=rfpo_id))
            
            # Get positioning configuration for this consortium
            positioning_config = PDFPositioning.query.filter_by(
                consortium_id=consortium.consort_id,
                template_name='po_template',
                active=True
            ).first()
            
            # Generate PDF with positioning configuration
            pdf_generator = RFPOPDFGenerator(positioning_config=positioning_config)
            pdf_buffer = pdf_generator.generate_po_pdf(rfpo, consortium, project, vendor, vendor_site)
            
            # Prepare filename
            filename = f"PO_{rfpo.rfpo_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            # Return PDF as response
            return Response(
                pdf_buffer.getvalue(),
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename="{filename}"',
                    'Content-Type': 'application/pdf'
                }
            )
            
        except Exception as e:
            print(f"PDF generation error: {e}")
            flash(f'❌ Error generating PDF: {str(e)}', 'error')
            return redirect(url_for('rfpo_edit', id=rfpo_id))
    
    @app.route('/rfpo/<int:rfpo_id>/generate-rfpo')
    @login_required
    def rfpo_generate_rfpo(rfpo_id):
        """Generate RFPO HTML preview for viewing and printing"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        try:
            # Get related data
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
            vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
            vendor_site = None
            
            # Handle vendor_site_id - regular VendorSite ID or None (uses vendor primary contact)
            if rfpo.vendor_site_id:
                try:
                    vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
                except (ValueError, TypeError):
                    vendor_site = None
            
            # Get requestor user information
            requestor = User.query.filter_by(record_id=rfpo.requestor_id).first() if rfpo.requestor_id else None
            
            # Render the RFPO HTML template
            return render_template('admin/rfpo_preview.html',
                                 rfpo=rfpo,
                                 project=project,
                                 consortium=consortium,
                                 vendor=vendor,
                                 vendor_site=vendor_site,
                                 requestor=requestor)
            
        except Exception as e:
            print(f"RFPO generation error: {e}")
            flash(f'❌ Error generating RFPO: {str(e)}', 'error')
            return redirect(url_for('rfpo_edit', id=rfpo_id))
    
    @app.route('/rfpo/<int:id>/delete', methods=['POST'])
    @login_required
    def rfpo_delete(id):
        """Delete RFPO"""
        rfpo = RFPO.query.get_or_404(id)
        try:
            db.session.delete(rfpo)
            db.session.commit()
            flash('✅ RFPO deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting RFPO: {str(e)}', 'error')
        return redirect(url_for('rfpos'))
    
    # Projects routes
    @app.route('/projects')
    @login_required
    def projects():
        """List all projects with consortium and team info"""
        projects = Project.query.all()
        
        # Populate consortium and team info for each project
        for project in projects:
            # Get consortium information for badges
            project.consortium_info = []
            consortium_ids = project.get_consortium_ids()
            for consortium_id in consortium_ids:
                consortium = Consortium.query.filter_by(consort_id=consortium_id).first()
                if consortium:
                    project.consortium_info.append({
                        'id': consortium.consort_id,
                        'name': consortium.name,
                        'abbrev': consortium.abbrev
                    })
            
            # Get team information for badge
            if project.team_record_id:
                team = Team.query.filter_by(record_id=project.team_record_id).first()
                if team:
                    project.team_info = {
                        'id': team.record_id,
                        'name': team.name,
                        'abbrev': team.abbrev
                    }
                else:
                    project.team_info = None
            else:
                project.team_info = None
        
        return render_template('admin/projects.html', projects=projects, format_json=format_json_field)
    
    @app.route('/project/new', methods=['GET', 'POST'])
    @login_required
    def project_new():
        """Create new project"""
        if request.method == 'POST':
            try:
                # Auto-generate project ID
                project_id = generate_next_id(Project, 'project_id', '', 8)
                
                project = Project(
                    project_id=project_id,
                    ref=request.form.get('ref'),
                    name=request.form.get('name'),
                    description=request.form.get('description'),
                    team_record_id=request.form.get('team_record_id') or None,
                    gov_funded=bool(request.form.get('gov_funded')),
                    uni_project=bool(request.form.get('uni_project')),
                    active=bool(request.form.get('active', True)),
                    created_by=current_user.get_display_name()
                )
                
                # Handle JSON fields
                consortium_ids = parse_comma_list(request.form.get('consortium_ids'))
                viewer_users = parse_comma_list(request.form.get('rfpo_viewer_user_ids'))
                
                if consortium_ids:
                    project.set_consortium_ids(consortium_ids)
                if viewer_users:
                    project.set_rfpo_viewer_users(viewer_users)
                
                db.session.add(project)
                db.session.commit()
                
                flash('✅ Project created successfully!', 'success')
                return redirect(url_for('projects'))
                
            except Exception as e:
                flash(f'❌ Error creating project: {str(e)}', 'error')
        
        teams = Team.query.filter_by(active=True).all()
        return render_template('admin/project_form.html', project=None, action='Create', teams=teams)
    
    @app.route('/project/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def project_edit(id):
        """Edit project"""
        project = Project.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                project.ref = request.form.get('ref')
                project.name = request.form.get('name')
                project.description = request.form.get('description')
                project.team_record_id = request.form.get('team_record_id') or None
                project.gov_funded = bool(request.form.get('gov_funded'))
                project.uni_project = bool(request.form.get('uni_project'))
                project.active = bool(request.form.get('active'))
                project.updated_by = current_user.get_display_name()
                
                # Handle JSON fields
                consortium_ids = parse_comma_list(request.form.get('consortium_ids'))
                viewer_users = parse_comma_list(request.form.get('rfpo_viewer_user_ids'))
                
                project.set_consortium_ids(consortium_ids)
                project.set_rfpo_viewer_users(viewer_users)
                
                db.session.commit()
                
                flash('✅ Project updated successfully!', 'success')
                return redirect(url_for('projects'))
                
            except Exception as e:
                flash(f'❌ Error updating project: {str(e)}', 'error')
        
        # Pre-populate JSON fields for editing
        project.consortium_ids_display = ', '.join(project.get_consortium_ids())
        project.rfpo_viewer_user_ids_display = ', '.join(project.get_rfpo_viewer_users())
        
        teams = Team.query.filter_by(active=True).all()
        return render_template('admin/project_form.html', project=project, action='Edit', teams=teams)
    
    @app.route('/project/<int:id>/delete', methods=['POST'])
    @login_required
    def project_delete(id):
        """Delete project"""
        project = Project.query.get_or_404(id)
        try:
            db.session.delete(project)
            db.session.commit()
            flash('✅ Project deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting project: {str(e)}', 'error')
        return redirect(url_for('projects'))
    
    # Vendors routes
    @app.route('/vendors')
    @login_required
    def vendors():
        """List all vendors with consortium info"""
        vendors = Vendor.query.all()
        
        # Populate consortium info for each vendor
        for vendor in vendors:
            # Get consortium information for badges
            vendor.consortium_info = []
            approved_consortiums = vendor.get_approved_consortiums()
            for consortium_abbrev in approved_consortiums:
                consortium = Consortium.query.filter_by(abbrev=consortium_abbrev).first()
                if consortium:
                    vendor.consortium_info.append({
                        'abbrev': consortium.abbrev,
                        'name': consortium.name,
                        'id': consortium.consort_id
                    })
                else:
                    # If consortium not found, still show the abbreviation
                    vendor.consortium_info.append({
                        'abbrev': consortium_abbrev,
                        'name': consortium_abbrev,
                        'id': consortium_abbrev
                    })
        
        return render_template('admin/vendors.html', vendors=vendors, format_json=format_json_field)
    
    @app.route('/vendor/new', methods=['GET', 'POST'])
    @login_required
    def vendor_new():
        """Create new vendor"""
        if request.method == 'POST':
            try:
                # Auto-generate vendor ID
                vendor_id = generate_next_id(Vendor, 'vendor_id', '', 8)
                
                vendor = Vendor(
                    vendor_id=vendor_id,
                    company_name=request.form.get('company_name'),
                    status=request.form.get('status', 'live'),
                    vendor_type=int(request.form.get('vendor_type', 0)),
                    certs_reps=bool(request.form.get('certs_reps')),
                    cert_date=datetime.strptime(request.form.get('cert_date'), '%Y-%m-%d').date() if request.form.get('cert_date') else None,
                    cert_expire_date=datetime.strptime(request.form.get('cert_expire_date'), '%Y-%m-%d').date() if request.form.get('cert_expire_date') else None,
                    is_university=bool(request.form.get('is_university')),
                    onetime_project_id=request.form.get('onetime_project_id') or None,
                    contact_name=request.form.get('contact_name'),
                    contact_dept=request.form.get('contact_dept'),
                    contact_tel=request.form.get('contact_tel'),
                    contact_fax=request.form.get('contact_fax'),
                    contact_address=request.form.get('contact_address'),
                    contact_city=request.form.get('contact_city'),
                    contact_state=request.form.get('contact_state'),
                    contact_zip=request.form.get('contact_zip'),
                    contact_country=request.form.get('contact_country'),
                    active=bool(request.form.get('active', True)),
                    created_by=current_user.get_display_name()
                )
                
                # Handle approved consortiums from selection interface
                approved_consortiums = parse_comma_list(request.form.get('approved_consortiums'))
                if approved_consortiums:
                    vendor.set_approved_consortiums(approved_consortiums)
                
                db.session.add(vendor)
                db.session.commit()
                
                flash('✅ Vendor created successfully!', 'success')
                return redirect(url_for('vendors'))
                
            except Exception as e:
                flash(f'❌ Error creating vendor: {str(e)}', 'error')
        
        return render_template('admin/vendor_form.html', vendor=None, action='Create')
    
    @app.route('/vendor/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def vendor_edit(id):
        """Edit vendor"""
        vendor = Vendor.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                vendor.company_name = request.form.get('company_name')
                vendor.status = request.form.get('status', 'live')
                vendor.vendor_type = int(request.form.get('vendor_type', 0))
                vendor.certs_reps = bool(request.form.get('certs_reps'))
                vendor.cert_date = datetime.strptime(request.form.get('cert_date'), '%Y-%m-%d').date() if request.form.get('cert_date') else None
                vendor.cert_expire_date = datetime.strptime(request.form.get('cert_expire_date'), '%Y-%m-%d').date() if request.form.get('cert_expire_date') else None
                vendor.onetime_project_id = request.form.get('onetime_project_id') or None
                vendor.contact_name = request.form.get('contact_name')
                vendor.contact_dept = request.form.get('contact_dept')
                vendor.contact_tel = request.form.get('contact_tel')
                vendor.contact_fax = request.form.get('contact_fax')
                vendor.contact_address = request.form.get('contact_address')
                vendor.contact_city = request.form.get('contact_city')
                vendor.contact_state = request.form.get('contact_state')
                vendor.contact_zip = request.form.get('contact_zip')
                vendor.contact_country = request.form.get('contact_country')
                vendor.active = bool(request.form.get('active'))
                vendor.updated_by = current_user.get_display_name()
                
                # Handle approved consortiums
                approved_consortiums = parse_comma_list(request.form.get('approved_consortiums'))
                vendor.set_approved_consortiums(approved_consortiums)
                
                db.session.commit()
                
                flash('✅ Vendor updated successfully!', 'success')
                return redirect(url_for('vendors'))
                
            except Exception as e:
                flash(f'❌ Error updating vendor: {str(e)}', 'error')
        
        # Pre-populate JSON fields for editing
        vendor.approved_consortiums_display = ', '.join(vendor.get_approved_consortiums())
        
        return render_template('admin/vendor_form.html', vendor=vendor, action='Edit')
    
    @app.route('/vendor/<int:id>/delete', methods=['POST'])
    @login_required
    def vendor_delete(id):
        """Delete vendor"""
        vendor = Vendor.query.get_or_404(id)
        try:
            db.session.delete(vendor)
            db.session.commit()
            flash('✅ Vendor deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting vendor: {str(e)}', 'error')
        return redirect(url_for('vendors'))
    
    # Vendor Sites (Contacts) routes
    @app.route('/vendor-site/new', methods=['GET', 'POST'])
    @login_required
    def vendor_site_new():
        """Create new vendor site/contact"""
        vendor_id = request.args.get('vendor_id')
        vendor = Vendor.query.get_or_404(vendor_id) if vendor_id else None
        
        if request.method == 'POST':
            try:
                # Auto-generate vendor site ID
                vendor_site_id = generate_next_id(VendorSite, 'vendor_site_id', '', 8)
                
                vendor_site = VendorSite(
                    vendor_site_id=vendor_site_id,
                    vendor_id=int(request.form.get('vendor_id')),
                    contact_name=request.form.get('contact_name'),
                    contact_dept=request.form.get('contact_dept'),
                    contact_tel=request.form.get('contact_tel'),
                    contact_fax=request.form.get('contact_fax'),
                    contact_address=request.form.get('contact_address'),
                    contact_city=request.form.get('contact_city'),
                    contact_state=request.form.get('contact_state'),
                    contact_zip=request.form.get('contact_zip'),
                    contact_country=request.form.get('contact_country'),
                    active=bool(request.form.get('active', True)),
                    created_by=current_user.get_display_name()
                )
                
                db.session.add(vendor_site)
                db.session.commit()
                
                flash('✅ Vendor contact created successfully!', 'success')
                return redirect(url_for('vendor_edit', id=vendor_site.vendor_id))
                
            except Exception as e:
                flash(f'❌ Error creating vendor contact: {str(e)}', 'error')
        
        vendors = Vendor.query.filter_by(active=True).all()
        return render_template('admin/vendor_site_form.html', vendor_site=None, action='Create', 
                             vendors=vendors, selected_vendor=vendor)
    
    @app.route('/vendor-site/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def vendor_site_edit(id):
        """Edit vendor site/contact"""
        vendor_site = VendorSite.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                vendor_site.contact_name = request.form.get('contact_name')
                vendor_site.contact_dept = request.form.get('contact_dept')
                vendor_site.contact_tel = request.form.get('contact_tel')
                vendor_site.contact_fax = request.form.get('contact_fax')
                vendor_site.contact_address = request.form.get('contact_address')
                vendor_site.contact_city = request.form.get('contact_city')
                vendor_site.contact_state = request.form.get('contact_state')
                vendor_site.contact_zip = request.form.get('contact_zip')
                vendor_site.contact_country = request.form.get('contact_country')
                vendor_site.active = bool(request.form.get('active'))
                vendor_site.updated_by = current_user.get_display_name()
                
                db.session.commit()
                
                flash('✅ Vendor contact updated successfully!', 'success')
                return redirect(url_for('vendor_edit', id=vendor_site.vendor_id))
                
            except Exception as e:
                flash(f'❌ Error updating vendor contact: {str(e)}', 'error')
        
        vendors = Vendor.query.filter_by(active=True).all()
        return render_template('admin/vendor_site_form.html', vendor_site=vendor_site, action='Edit', 
                             vendors=vendors, selected_vendor=vendor_site.vendor)
    
    @app.route('/vendor-site/<int:id>/delete', methods=['POST'])
    @login_required
    def vendor_site_delete(id):
        """Delete vendor site/contact"""
        vendor_site = VendorSite.query.get_or_404(id)
        vendor_id = vendor_site.vendor_id
        try:
            db.session.delete(vendor_site)
            db.session.commit()
            flash('✅ Vendor contact deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting vendor contact: {str(e)}', 'error')
        return redirect(url_for('vendor_edit', id=vendor_id))
    
    # Lists routes (Configuration Management)
    @app.route('/lists')
    @login_required
    def lists():
        """List all configuration lists grouped by type"""
        # Group lists by type
        list_types = db.session.query(List.type).distinct().all()
        grouped_lists = {}
        
        for (list_type,) in list_types:
            grouped_lists[list_type] = List.query.filter_by(type=list_type, active=True).order_by(List.key).all()
        
        return render_template('admin/lists.html', grouped_lists=grouped_lists)
    
    @app.route('/list/new', methods=['GET', 'POST'])
    @login_required
    def list_new():
        """Create new list item"""
        if request.method == 'POST':
            try:
                # Auto-generate list ID
                list_id = generate_next_id(List, 'list_id', '', 10)
                
                list_item = List(
                    list_id=list_id,
                    type=request.form.get('type'),
                    key=request.form.get('key'),
                    value=request.form.get('value'),
                    active=bool(request.form.get('active', True)),
                    created_by=current_user.get_display_name()
                )
                
                db.session.add(list_item)
                db.session.commit()
                
                flash('✅ List item created successfully!', 'success')
                return redirect(url_for('lists'))
                
            except Exception as e:
                flash(f'❌ Error creating list item: {str(e)}', 'error')
        
        # Get existing types for dropdown
        existing_types = [t[0] for t in db.session.query(List.type).distinct().all()]
        return render_template('admin/list_form.html', list_item=None, action='Create', existing_types=existing_types)
    
    @app.route('/list/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def list_edit(id):
        """Edit list item"""
        list_item = List.query.get_or_404(id)
        
        if request.method == 'POST':
            try:
                list_item.type = request.form.get('type')
                list_item.key = request.form.get('key')
                list_item.value = request.form.get('value')
                list_item.active = bool(request.form.get('active'))
                list_item.updated_by = current_user.get_display_name()
                
                db.session.commit()
                
                flash('✅ List item updated successfully!', 'success')
                return redirect(url_for('lists'))
                
            except Exception as e:
                flash(f'❌ Error updating list item: {str(e)}', 'error')
        
        existing_types = [t[0] for t in db.session.query(List.type).distinct().all()]
        return render_template('admin/list_form.html', list_item=list_item, action='Edit', existing_types=existing_types)
    
    @app.route('/list/<int:id>/delete', methods=['POST'])
    @login_required
    def list_delete(id):
        """Delete list item"""
        list_item = List.query.get_or_404(id)
        try:
            db.session.delete(list_item)
            db.session.commit()
            flash('✅ List item deleted successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error deleting list item: {str(e)}', 'error')
        return redirect(url_for('lists'))
    
    @app.route('/seed-lists', methods=['POST'])
    @login_required
    def seed_lists():
        """Seed the database with required list configurations"""
        try:
            # Configuration data as specified
            config_data = [
                # Admin levels
                ('adminlevel', 'CAL_MEET_USER', 'Meeting Calendar User'),
                ('adminlevel', 'GOD', 'Super Admin'),
                ('adminlevel', 'RFPO_ADMIN', 'RFPO Full Admin'),
                ('adminlevel', 'RFPO_USER', 'RFPO User'),
                ('adminlevel', 'VROOM_ADMIN', 'VROOM Full Admin'),
                ('adminlevel', 'VROOM_USER', 'VROOM User'),
                
                # Meeting IT
                ('meeting_it', 'AV', 'Projector/VCR/TV'),
                ('meeting_it', 'PC', 'PC/Laptop'),
                ('meeting_it', 'ROOM', 'Meeting Room'),
                ('meeting_it', 'TEL', 'Video/Tele Conference'),
                ('meeting_it', 'XXX', 'Misc'),
                
                # RFPO Approval levels
                ('rfpo_appro', '5', 'Vendor Review'),
                ('rfpo_appro', '8', 'Management Review'),
                ('rfpo_appro', '10', 'Technical Approval'),
                ('rfpo_appro', '12', 'Project Manager Approval'),
                ('rfpo_appro', '20', 'Board Approval'),
                ('rfpo_appro', '21', 'Executive Director Approval'),
                ('rfpo_appro', '22', 'Management Committee Approval'),
                ('rfpo_appro', '23', 'Technical Leadership Council'),
                ('rfpo_appro', '25', 'Steering Approval'),
                ('rfpo_appro', '26', 'Finance Approval'),
                ('rfpo_appro', '28', 'USCAR Leadership Group Approval'),
                ('rfpo_appro', '29', 'USCAR Internal Approval'),
                ('rfpo_appro', '30', 'Treasurer\'s Review'),
                ('rfpo_appro', '35', 'Partnership Chair'),
                ('rfpo_appro', '36', 'TLC Oversight'),
                ('rfpo_appro', '40', 'Vice President Approval'),
                ('rfpo_appro', '99', 'PO Release Approval'),
                
                # RFPO Brackets
                ('rfpo_brack', '10', '5000'),
                ('rfpo_brack', '20', '15000'),
                ('rfpo_brack', '30', '100000'),
                ('rfpo_brack', '40', '150000'),
                ('rfpo_brack', '50', '999999999'),
                
                # RFPO Status
                ('rfpo_statu', '10', 'draft'),
                ('rfpo_statu', '15', 'waiting'),
                ('rfpo_statu', '20', 'conditional'),
                ('rfpo_statu', '30', 'approved'),
                ('rfpo_statu', '40', 'refused'),
            ]
            
            created_count = 0
            for list_type, key, value in config_data:
                # Check if already exists
                existing = List.query.filter_by(type=list_type, key=key).first()
                if not existing:
                    list_id = generate_next_id(List, 'list_id', '', 10)
                    list_item = List(
                        list_id=list_id,
                        type=list_type,
                        key=key,
                        value=value,
                        active=True,
                        created_by=current_user.get_display_name()
                    )
                    db.session.add(list_item)
                    created_count += 1
            
            db.session.commit()
            flash(f'✅ Seeded {created_count} list configuration items!', 'success')
            
        except Exception as e:
            flash(f'❌ Error seeding lists: {str(e)}', 'error')
        
        return redirect(url_for('lists'))
    
    @app.route('/seed-consortiums', methods=['POST'])
    @login_required
    def seed_consortiums():
        """Seed the database with standard consortium data"""
        try:
            # Standard consortium data as specified
            consortium_data = [
                ('APT', 'Advanced Powertrain'),
                ('EETLC', 'EETLC'),
                ('MAT', 'Materials TLC'),
                ('Non-USCAR', 'Non-USCAR'),
                ('OSRP', 'Occupant Safety Research Partnership'),
                ('USABC', 'United States Advanced Battery Consortium'),
                ('USAMP', 'United States Automotive Materials Partnership'),
                ('USCAR', 'United States Council for Automotive Research LLC'),
                ('HFC', 'USCAR Hydrogen & Fuel Cell TLC'),
                ('MFG', 'USCAR LLC Manufacturing Technical Leadership Council'),
            ]
            
            created_count = 0
            for abbrev, name in consortium_data:
                # Check if already exists by abbreviation
                existing = Consortium.query.filter_by(abbrev=abbrev).first()
                if not existing:
                    # Auto-generate consortium ID
                    consort_id = generate_next_id(Consortium, 'consort_id', '', 8)
                    
                    consortium = Consortium(
                        consort_id=consort_id,
                        name=name,
                        abbrev=abbrev,
                        require_approved_vendors=True,  # Default to requiring approved vendors
                        active=True,
                        created_by=current_user.get_display_name()
                    )
                    db.session.add(consortium)
                    created_count += 1
                else:
                    # Update existing consortium to ensure it's active and has correct name
                    existing.name = name
                    existing.active = True
                    existing.updated_by = current_user.get_display_name()
            
            db.session.commit()
            
            if created_count > 0:
                flash(f'✅ Seeded {created_count} new consortiums!', 'success')
            else:
                flash('ℹ️  All standard consortiums already exist and have been updated.', 'info')
            
        except Exception as e:
            flash(f'❌ Error seeding consortiums: {str(e)}', 'error')
        
        return redirect(url_for('consortiums'))
    
    # API endpoints for quick data
    @app.route('/api/stats')
    @login_required
    def api_stats():
        """Get dashboard statistics"""
        stats = {
            'consortiums': Consortium.query.filter_by(active=True).count(),
            'teams': Team.query.filter_by(active=True).count(),
            'rfpos': RFPO.query.count(),
            'users': User.query.filter_by(active=True).count(),
            'vendors': Vendor.query.filter_by(active=True).count(),
            'projects': Project.query.filter_by(active=True).count(),
            'uploaded_files': UploadedFile.query.count(),
        }
        return jsonify(stats)
    
    @app.route('/api/users')
    @login_required
    def api_users():
        """Get all active users for dropdowns and selection"""
        users = User.query.filter_by(active=True).all()
        user_data = []
        for user in users:
            user_data.append({
                'id': user.record_id,
                'name': user.get_display_name(),
                'email': user.email,
                'company': user.company or 'N/A'
            })
        return jsonify(user_data)
    
    @app.route('/api/consortiums')
    @login_required
    def api_consortiums():
        """Get all active consortiums for dropdowns"""
        consortiums = Consortium.query.filter_by(active=True).all()
        consortium_data = []
        for consortium in consortiums:
            consortium_data.append({
                'id': consortium.consort_id,
                'name': consortium.name,
                'abbrev': consortium.abbrev
            })
        return jsonify(consortium_data)
    
    @app.route('/api/projects/<consortium_id>')
    @login_required
    def api_projects_for_consortium(consortium_id):
        """Get projects for a specific consortium"""
        projects = Project.query.filter(
            Project.consortium_ids.like(f'%{consortium_id}%'),
            Project.active == True
        ).all()
        
        project_data = []
        for project in projects:
            project_data.append({
                'id': project.project_id,
                'ref': project.ref,
                'name': project.name,
                'description': project.description,
                'gov_funded': project.gov_funded,
                'uni_project': project.uni_project
            })
        return jsonify(project_data)
    
    @app.route('/api/vendor-sites/<int:vendor_id>')
    @login_required
    def api_vendor_sites(vendor_id):
        """Get sites for a specific vendor, including vendor's primary contact"""
        vendor = Vendor.query.get_or_404(vendor_id)
        site_data = []
        
        # Add vendor's primary contact as first option if it has contact info
        if vendor.contact_name:
            site_data.append({
                'id': f'vendor_{vendor.id}',  # Special ID to indicate this is the vendor's primary contact
                'contact_name': vendor.contact_name,
                'contact_dept': vendor.contact_dept,
                'contact_tel': vendor.contact_tel,
                'contact_city': vendor.contact_city,
                'contact_state': vendor.contact_state,
                'full_address': vendor.get_full_contact_address(),
                'is_primary': True
            })
        
        # Add additional vendor sites
        for site in vendor.sites:
            site_data.append({
                'id': site.id,
                'contact_name': site.contact_name,
                'contact_dept': site.contact_dept,
                'contact_tel': site.contact_tel,
                'contact_city': site.contact_city,
                'contact_state': site.contact_state,
                'full_address': site.get_full_contact_address(),
                'is_primary': False
            })
        return jsonify(site_data)
    
    # PDF to Image conversion for positioning editor background
    @app.route('/api/pdf-template-image/<template_name>')
    def pdf_template_image(template_name):
        """Convert PDF template to image for background display"""
        print(f"🖼️ PDF Template Image Route Called:")
        print(f"  - template_name: {template_name}")
        
        try:
            import os
            import io
            from flask import Response, current_app
            
            # Try to import pdf2image, fall back to placeholder if not available
            try:
                from pdf2image import convert_from_path
                
                # Map template names to PDF files
                template_files = {
                    'po_template': 'po.pdf',
                    'po_page2': 'po_page2.pdf'
                }
                
                print(f"  - Available templates: {list(template_files.keys())}")
                
                if template_name not in template_files:
                    print(f"❌ Template '{template_name}' not found in available templates")
                    return Response("Template not found", status=404)
                
                pdf_path = os.path.join(app.root_path, 'static', 'po_files', template_files[template_name])
                print(f"  - PDF path: {pdf_path}")
                print(f"  - PDF exists: {os.path.exists(pdf_path)}")
                
                if not os.path.exists(pdf_path):
                    return Response("PDF file not found", status=404)
                
                # Convert first page to image
                images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)
                
                if not images:
                    return Response("Failed to convert PDF", status=500)
                
                # Convert PIL Image to PNG bytes
                img_buffer = io.BytesIO()
                images[0].save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                return Response(
                    img_buffer.getvalue(),
                    mimetype='image/png',
                    headers={'Cache-Control': 'public, max-age=3600'}  # Cache for 1 hour
                )
                
            except ImportError:
                # pdf2image not available, create a placeholder image
                from PIL import Image, ImageDraw, ImageFont
                
                # Create a white background with guidelines
                width, height = 612, 792  # Standard letter size in points
                img = Image.new('RGB', (width, height), 'white')
                draw = ImageDraw.Draw(img)
                
                # Draw border
                draw.rectangle([0, 0, width-1, height-1], outline='#cccccc', width=2)
                
                # Draw grid lines every 50 points
                for x in range(0, width, 50):
                    draw.line([x, 0, x, height], fill='#eeeeee', width=1)
                for y in range(0, height, 50):
                    draw.line([0, y, width, y], fill='#eeeeee', width=1)
                
                # Add title
                try:
                    font = ImageFont.load_default()
                    draw.text((width//2, height//2), f"PDF Template: {template_name}", 
                             fill='#999999', anchor='mm', font=font)
                    draw.text((width//2, height//2 + 20), "Install poppler-utils for PDF preview", 
                             fill='#666666', anchor='mm', font=font)
                except:
                    pass
                
                # Convert to PNG bytes
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                return Response(
                    img_buffer.getvalue(),
                    mimetype='image/png',
                    headers={
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                )
            
        except Exception as e:
            print(f"Error generating template image: {e}")
            import traceback
            traceback.print_exc()
            return Response(f"Error generating template image: {str(e)}", status=500)
    
    # PDF Positioning Editor routes
    @app.route('/pdf-positioning')
    @login_required
    def pdf_positioning_list():
        """List PDF positioning configurations"""
        configs = PDFPositioning.query.order_by(PDFPositioning.consortium_id, PDFPositioning.template_name).all()
        consortiums = Consortium.query.filter_by(active=True).all()
        
        # Add consortium info to each config
        for config in configs:
            config.consortium = Consortium.query.filter_by(consort_id=config.consortium_id).first()
        
        return render_template('admin/pdf_positioning_list.html', configs=configs, consortiums=consortiums)
    
    @app.route('/pdf-positioning/editor/<consortium_id>/<template_name>')
    @login_required
    def pdf_positioning_editor(consortium_id, template_name):
        """Visual PDF positioning editor"""
        print(f"🔍 PDF Editor Route Called:")
        print(f"  - consortium_id: {consortium_id}")
        print(f"  - template_name: {template_name}")
        
        # Debug: List all consortiums
        all_consortiums = Consortium.query.all()
        print(f"  - Available consortiums:")
        for c in all_consortiums:
            print(f"    * ID: {c.id}, consort_id: {c.consort_id}, name: {c.name}")
        
        consortium = Consortium.query.filter_by(consort_id=consortium_id).first()
        if not consortium:
            print(f"❌ No consortium found with consort_id='{consortium_id}'")
            return f"No consortium found with consort_id='{consortium_id}'. Available: {[c.consort_id for c in all_consortiums]}", 404
        
        print(f"✅ Found consortium: {consortium.name}")
        
        # Get existing positioning config or create default
        config = PDFPositioning.query.filter_by(
            consortium_id=consortium_id,
            template_name=template_name,
            active=True
        ).first()
        
        if not config:
            # Create default configuration with standard PDF fields
            config = PDFPositioning(
                consortium_id=consortium_id,
                template_name=template_name,
                created_by=current_user.get_display_name()
            )
            
            # Set default positions for common PDF fields
            default_fields = {
                'consortium_logo': {'x': 50, 'y': 750, 'width': 80, 'height': 40, 'visible': True},
                'po_number': {'x': 470, 'y': 710, 'font_size': 10, 'font_weight': 'bold', 'visible': True},
                'po_date': {'x': 470, 'y': 695, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'vendor_company': {'x': 60, 'y': 600, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'vendor_contact': {'x': 60, 'y': 585, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'vendor_address': {'x': 60, 'y': 570, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'vendor_phone': {'x': 60, 'y': 555, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'ship_to_name': {'x': 240, 'y': 600, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'ship_to_address': {'x': 240, 'y': 585, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'delivery_type': {'x': 410, 'y': 570, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'delivery_payment': {'x': 410, 'y': 545, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'delivery_routing': {'x': 410, 'y': 520, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'payment_terms': {'x': 60, 'y': 470, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'project_info': {'x': 240, 'y': 470, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'delivery_date': {'x': 410, 'y': 470, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'government_agreement': {'x': 240, 'y': 455, 'font_size': 8, 'font_weight': 'normal', 'visible': True},
                'requestor_info': {'x': 60, 'y': 380, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'invoice_address': {'x': 410, 'y': 380, 'font_size': 9, 'font_weight': 'normal', 'visible': True},
                'line_items_header': {'x': 60, 'y': 320, 'font_size': 8, 'font_weight': 'bold', 'visible': True},
                'subtotal': {'x': 400, 'y': 200, 'font_size': 9, 'font_weight': 'bold', 'visible': True},
                'total': {'x': 400, 'y': 180, 'font_size': 11, 'font_weight': 'bold', 'visible': True}
            }
            config.set_positioning_data(default_fields)
            db.session.add(config)
            db.session.commit()
        
        return render_template('admin/pdf_positioning_editor.html', 
                             config=config, 
                             consortium=consortium,
                             template_name=template_name)
    
    @app.route('/api/pdf-positioning/<int:config_id>', methods=['GET', 'POST', 'DELETE'])
    @login_required
    def api_pdf_positioning(config_id):
        """API for saving/loading/deleting PDF positioning data"""
        config = PDFPositioning.query.get_or_404(config_id)
        
        if request.method == 'GET':
            return jsonify(config.to_dict())
        
        elif request.method == 'POST':
            try:
                data = request.get_json()
                if 'positioning_data' in data:
                    config.set_positioning_data(data['positioning_data'])
                    config.updated_by = current_user.get_display_name()
                    db.session.commit()
                    return jsonify({'success': True, 'message': 'Positioning saved successfully'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 400
        
        elif request.method == 'DELETE':
            try:
                db.session.delete(config)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Configuration deleted successfully'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 400
        
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    @app.route('/api/pdf-positioning/preview/<int:config_id>')
    @login_required
    def api_pdf_positioning_preview(config_id):
        """Generate preview PDF with current positioning"""
        config = PDFPositioning.query.get_or_404(config_id)
        
        # Create a sample RFPO for preview
        try:
            # Get a sample RFPO or create dummy data
            sample_rfpo = RFPO.query.first()
            project = None
            consortium = None
            vendor = None
            vendor_site = None
            
            if sample_rfpo:
                # Get related data for real RFPO
                project = Project.query.filter_by(project_id=sample_rfpo.project_id).first()
                consortium = Consortium.query.filter_by(consort_id=sample_rfpo.consortium_id).first()
                vendor = Vendor.query.get(sample_rfpo.vendor_id) if sample_rfpo.vendor_id else None
                vendor_site = VendorSite.query.get(sample_rfpo.vendor_site_id) if sample_rfpo.vendor_site_id else None
            
            # Create dummy data if needed
            if not sample_rfpo or not project or not consortium:
                # Create dummy RFPO for preview
                from types import SimpleNamespace
                
                sample_rfpo = SimpleNamespace()
                sample_rfpo.rfpo_id = "PREVIEW-001"
                sample_rfpo.po_number = "PO-PREVIEW-001"
                sample_rfpo.po_date = datetime.now().strftime('%Y-%m-%d')
                sample_rfpo.vendor_id = 1
                sample_rfpo.vendor_site_id = None
                sample_rfpo.project_id = "PROJ-001"
                sample_rfpo.consortium_id = "CONSORT-001"
                sample_rfpo.ship_to_address = "123 Preview Street\nPreview City, ST 12345"
                sample_rfpo.bill_to_address = "456 Billing Ave\nBilling City, ST 54321"
                sample_rfpo.total_amount = 15000.00
                sample_rfpo.status = "Draft"
                sample_rfpo.created_at = datetime.now()
                sample_rfpo.shipto_name = "Preview Shipping Contact"
                sample_rfpo.shipto_address = "123 Shipping Street\nShipping City, ST 12345"
                sample_rfpo.delivery_type = "Standard Delivery"
                sample_rfpo.delivery_payment = "Prepaid"
                sample_rfpo.delivery_routing = "Direct"
                sample_rfpo.payment_terms = "Net 30"
                sample_rfpo.delivery_date = datetime.now()
                sample_rfpo.government_agreement_number = "USA-GOV-2024-001"
                sample_rfpo.line_items = []
                sample_rfpo.subtotal = 14000.00
                sample_rfpo.cost_share_amount = 1000.00
                sample_rfpo.requestor_id = "REQ001"
                sample_rfpo.requestor_tel = "(555) 987-6543"
                sample_rfpo.requestor_location = "Building A, Room 101"
                sample_rfpo.invoice_address = "456 Invoice Ave\nInvoice City, ST 54321"
                
                # Create dummy project
                project = SimpleNamespace()
                project.project_id = "PROJ-001"
                project.project_name = "Sample Preview Project"
                project.project_description = "This is a preview project for PDF positioning testing"
                project.ref = "PROJ-REF-001"
                project.name = "Sample Preview Project"
                
                # Create dummy consortium
                consortium = SimpleNamespace()
                consortium.consort_id = "CONSORT-001"
                consortium.consort_name = "Preview Consortium"
                consortium.consort_description = "Sample consortium for preview"
                consortium.abbrev = "PREVIEW"
                # Try to use an actual consortium logo for preview if available
                real_consortium = Consortium.query.filter_by(consort_id=config.consortium_id).first()
                consortium.logo = real_consortium.logo if real_consortium and real_consortium.logo else None
                
                # Create dummy vendor
                vendor = SimpleNamespace()
                vendor.vendor_id = 1
                vendor.vendor_name = "Preview Vendor Inc."
                vendor.company_name = "Preview Vendor Inc."
                vendor.vendor_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor.contact_email = "contact@previewvendor.com"
                vendor.contact_phone = "(555) 123-4567"
                vendor.contact_name = "John Smith"
                vendor.contact_dept = "Sales Department"  
                vendor.contact_tel = "(555) 123-4567"
                vendor.contact_fax = "(555) 123-4568"
                vendor.contact_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor.contact_city = "Vendor City"
                vendor.contact_state = "ST"
                vendor.contact_zip = "98765"
                vendor.contact_country = "USA"
                
                # Create dummy vendor_site
                vendor_site = SimpleNamespace()
                vendor_site.vendor_site_id = 1
                vendor_site.vendor_id = 1
                vendor_site.site_name = "Main Office"
                vendor_site.site_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor_site.contact_name = "Jane Doe"
                vendor_site.contact_dept = "Operations Department"
                vendor_site.contact_tel = "(555) 123-4569"
                vendor_site.contact_fax = "(555) 123-4570"
                vendor_site.contact_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor_site.contact_city = "Vendor City"
                vendor_site.contact_state = "ST"
                vendor_site.contact_zip = "98765"
                vendor_site.contact_country = "USA"
            
            # Generate PDF with custom positioning
            pdf_generator = RFPOPDFGenerator(positioning_config=config)
            pdf_buffer = pdf_generator.generate_po_pdf(sample_rfpo, consortium, project, vendor, vendor_site)
            
            return Response(
                pdf_buffer.getvalue(),
                mimetype='application/pdf',
                headers={'Content-Disposition': 'inline; filename="preview.pdf"'}
            )
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
    
    print("🚀 Custom RFPO Admin Panel Starting...")
    print("=" * 60)
    print("📧 Default Login: admin@rfpo.com")
    print("🔑 Default Password: admin123")
    print("🌐 Admin Panel: http://localhost:5111/")
    print("=" * 60)
    print("✨ NO Flask-Admin - Custom built from scratch!")
    print("🎯 Direct database operations - no compatibility issues!")
    print("📝 JSON fields handled properly with transformations")
    print("⚠️  Running on port 5111 (main app uses 5000)")
    print("")
    
    app.run(debug=True, host='0.0.0.0', port=5111)
