"""
RFPO Management API Routes
Centralized RFPO endpoints for both user app and admin panel
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, RFPO, RFPOLineItem, Team, UploadedFile, Project, List
from utils import require_auth, error_response
import uuid
import mimetypes

rfpo_api = Blueprint("rfpo_api", __name__, url_prefix="/api/rfpos")

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff",
    ".ppt", ".pptx", ".rtf", ".odt", ".ods",
}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@rfpo_api.route("", methods=["GET"])
@require_auth
def list_rfpos():
    """List RFPOs with filtering and pagination based on user permissions"""
    try:
        user = request.current_user

        # Build base query with permission filtering and eager loading
        query = RFPO.query.options(
            joinedload(RFPO.team),
            joinedload(RFPO.line_items),
        )

        # If user is super admin, they can see all RFPOs
        if not user.is_super_admin():
            # Get user's accessible team IDs
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]

            # Get user's accessible project IDs
            all_projects = Project.query.all()
            accessible_project_ids = []
            for project in all_projects:
                viewer_users = project.get_rfpo_viewer_users()
                if user.record_id in viewer_users:
                    accessible_project_ids.append(project.project_id)

            # Filter RFPOs to only those user can access
            if team_ids or accessible_project_ids:
                filters = []
                if team_ids:
                    filters.append(RFPO.team_id.in_(team_ids))
                if accessible_project_ids:
                    filters.append(RFPO.project_id.in_(accessible_project_ids))

                if len(filters) > 1:
                    query = query.filter(db.or_(*filters))
                else:
                    query = query.filter(filters[0])
            else:
                # User has no access to any RFPOs
                query = query.filter(RFPO.id == -1)  # This will return no results

        # Apply additional filters
        team_id = request.args.get("team_id")
        if team_id:
            query = query.filter_by(team_id=team_id)

        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)

        search = request.args.get("search")
        if search:
            query = query.filter(
                RFPO.title.ilike(f"%{search}%")
                | RFPO.rfpo_id.ilike(f"%{search}%")
                | RFPO.description.ilike(f"%{search}%")
            )

        # Pagination
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 200)

        rfpos = query.order_by(RFPO.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "success": True,
                "rfpos": [rfpo.to_dict() for rfpo in rfpos.items],
                "total": rfpos.total,
                "page": rfpos.page,
                "pages": rfpos.pages,
            }
        )

    except Exception as e:
        return error_response(e)


@rfpo_api.route("", methods=["POST"])
@require_auth
def create_rfpo():
    """Create new RFPO"""
    try:
        # Only RFPO_ADMIN or GOD can create RFPOs
        user_perms = request.current_user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required to create RFPOs"}), 403

        data = request.get_json()

        # Validate required fields - only title is required, team is optional
        if not data.get("title"):
            return jsonify({"success": False, "message": "Title is required"}), 400

        # Verify team exists if provided
        team_id = data.get("team_id")
        if team_id:
            team = Team.query.get(team_id)
            if not team:
                return jsonify({"success": False, "message": "Team not found"}), 404
        # Generate RFPO ID atomically using MAX to avoid race conditions
        max_rfpo = db.session.query(db.func.max(RFPO.rfpo_id)).scalar()
        if max_rfpo:
            try:
                last_num = int(max_rfpo.replace("RFPO-", ""))
                rfpo_count = last_num
            except ValueError:
                rfpo_count = RFPO.query.count()
        else:
            rfpo_count = 0
        rfpo_id = f"RFPO-{rfpo_count + 1:04d}"

        # Ensure unique RFPO ID
        while RFPO.query.filter_by(rfpo_id=rfpo_id).first():
            rfpo_count += 1
            rfpo_id = f"RFPO-{rfpo_count + 1:04d}"

        rfpo = RFPO(
            rfpo_id=rfpo_id,
            title=data["title"],
            description=data.get("description", ""),
            vendor=data.get("vendor", ""),
            due_date=(
                datetime.fromisoformat(data["due_date"])
                if data.get("due_date")
                else None
            ),
            status=data.get("status", "Draft"),
            team_id=team_id,
            created_by=request.current_user.username,
            updated_by=request.current_user.username,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(rfpo)
        db.session.commit()

        return jsonify({"success": True, "rfpo": rfpo.to_dict()}), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "RFPO ID already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>", methods=["GET"])
@require_auth
def get_rfpo(rfpo_id):
    """Get RFPO details"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Authorization: verify user has access to this RFPO
        user = request.current_user
        if not user.is_super_admin():
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]

            # Check project-level access
            accessible_project_ids = []
            if rfpo.project_id:
                project = Project.query.filter_by(project_id=rfpo.project_id).first()
                if project and user.record_id in project.get_rfpo_viewer_users():
                    accessible_project_ids.append(rfpo.project_id)

            has_team_access = rfpo.team_id and rfpo.team_id in team_ids
            has_project_access = rfpo.project_id and rfpo.project_id in accessible_project_ids

            if not has_team_access and not has_project_access:
                return jsonify({"success": False, "message": "Access denied"}), 403

        rfpo_data = rfpo.to_dict()

        # Add line items
        line_items = RFPOLineItem.query.filter_by(rfpo_id=rfpo_id).all()
        rfpo_data["line_items"] = [item.to_dict() for item in line_items]

        # Add uploaded files
        files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()
        rfpo_data["files"] = [file.to_dict() for file in files]

        return jsonify({"success": True, "rfpo": rfpo_data})

    except Exception as e:
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>", methods=["PUT"])
@require_auth
def update_rfpo(rfpo_id):
    """Update RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        # Update fields
        rfpo.title = data.get("title", rfpo.title)
        rfpo.description = data.get("description", rfpo.description)
        rfpo.vendor = data.get("vendor", rfpo.vendor)
        if data.get("due_date"):
            rfpo.due_date = datetime.fromisoformat(data["due_date"])
        rfpo.status = data.get("status", rfpo.status)
        rfpo.updated_by = request.current_user.username
        rfpo.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({"success": True, "rfpo": rfpo.to_dict()})

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>", methods=["DELETE"])
@require_auth
def delete_rfpo(rfpo_id):
    """Delete RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Check permissions (only creator or admin can delete)
        user_perms = request.current_user.get_permissions() or []
        if (
            rfpo.created_by != request.current_user.username
            and "GOD" not in user_perms
        ):
            return jsonify({"success": False, "message": "Permission denied"}), 403

        db.session.delete(rfpo)
        db.session.commit()

        return jsonify({"success": True, "message": "RFPO deleted successfully"})

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/line-items", methods=["GET"])
@require_auth
def get_rfpo_line_items(rfpo_id):
    """Get RFPO line items"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_items = RFPOLineItem.query.filter_by(rfpo_id=rfpo_id).all()

        return jsonify(
            {"success": True, "line_items": [item.to_dict() for item in line_items]}
        )

    except Exception as e:
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/line-items", methods=["POST"])
@require_auth
def create_line_item(rfpo_id):
    """Create RFPO line item"""
    try:
        # Only RFPO_ADMIN or GOD can create line items
        user_perms = request.current_user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        if not data.get("description"):
            return jsonify({"success": False, "message": "Description is required"}), 400

        # Auto-assign next line number
        max_line = (
            db.session.query(db.func.max(RFPOLineItem.line_number))
            .filter_by(rfpo_id=rfpo.id)
            .scalar()
        )
        next_line_number = (max_line or 0) + 1

        quantity = int(data.get("quantity", 1))
        unit_price = float(data.get("unit_price", 0.0))

        line_item = RFPOLineItem(
            rfpo_id=rfpo_id,
            line_number=data.get("line_number", next_line_number),
            description=data.get("description", ""),
            quantity=quantity,
            unit_price=unit_price,
            total_price=quantity * unit_price,
            is_capital_equipment=bool(data.get("is_capital_equipment", False)),
            capital_description=data.get("capital_description"),
            capital_serial_id=data.get("capital_serial_id"),
            capital_location=data.get("capital_location"),
            capital_condition=data.get("capital_condition"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Handle capital equipment date
        capital_date = data.get("capital_acquisition_date")
        if capital_date:
            from dateutil.parser import parse as parse_date
            try:
                line_item.capital_acquisition_date = parse_date(capital_date).date()
            except (ValueError, TypeError):
                pass

        # Handle capital cost
        capital_cost = data.get("capital_acquisition_cost")
        if capital_cost:
            try:
                line_item.capital_acquisition_cost = float(capital_cost)
            except (ValueError, TypeError):
                pass

        db.session.add(line_item)
        db.session.flush()

        # Update RFPO totals
        rfpo.update_totals()

        db.session.commit()

        return jsonify({"success": True, "line_item": line_item.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/line-items/<int:line_item_id>", methods=["PUT"])
@require_auth
def update_line_item(rfpo_id, line_item_id):
    """Update RFPO line item"""
    try:
        # Only RFPO_ADMIN or GOD can update line items
        user_perms = request.current_user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_item = RFPOLineItem.query.get_or_404(line_item_id)

        if line_item.rfpo_id != rfpo.id:
            return jsonify({"success": False, "message": "Line item does not belong to this RFPO"}), 400

        data = request.get_json()

        if "description" in data:
            line_item.description = data["description"]
        if "quantity" in data:
            line_item.quantity = int(data["quantity"])
        if "unit_price" in data:
            line_item.unit_price = float(data["unit_price"])
        if "is_capital_equipment" in data:
            line_item.is_capital_equipment = bool(data["is_capital_equipment"])
        if "capital_description" in data:
            line_item.capital_description = data["capital_description"]
        if "capital_serial_id" in data:
            line_item.capital_serial_id = data["capital_serial_id"]
        if "capital_location" in data:
            line_item.capital_location = data["capital_location"]
        if "capital_condition" in data:
            line_item.capital_condition = data["capital_condition"]

        # Recalculate total
        line_item.calculate_total()
        line_item.updated_at = datetime.utcnow()

        # Update RFPO totals
        rfpo.update_totals()

        db.session.commit()

        return jsonify({"success": True, "line_item": line_item.to_dict()})

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/line-items/<int:line_item_id>", methods=["DELETE"])
@require_auth
def delete_line_item(rfpo_id, line_item_id):
    """Delete RFPO line item"""
    try:
        # Only RFPO_ADMIN or GOD can delete line items
        user_perms = request.current_user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_item = RFPOLineItem.query.get_or_404(line_item_id)

        if line_item.rfpo_id != rfpo.id:
            return jsonify({"success": False, "message": "Line item does not belong to this RFPO"}), 400

        db.session.delete(line_item)

        # Update RFPO totals
        rfpo.update_totals()

        db.session.commit()

        return jsonify({"success": True, "message": "Line item deleted successfully"})

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/files", methods=["GET"])
@require_auth
def get_rfpo_files(rfpo_id):
    """Get RFPO uploaded files"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()

        return jsonify({"success": True, "files": [file.to_dict() for file in files]})

    except Exception as e:
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/files/upload", methods=["POST"])
@require_auth
def upload_rfpo_file(rfpo_id):
    """Upload a file to an RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file provided"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"success": False, "message": "No file selected"}), 400

        document_type = request.form.get("document_type", "")
        description = request.form.get("description", "")

        from werkzeug.utils import secure_filename
        original_filename = secure_filename(file.filename)
        if not original_filename:
            return jsonify({"success": False, "message": "Invalid filename"}), 400

        # Validate extension
        file_extension = os.path.splitext(original_filename)[1].lower()
        if file_extension not in ALLOWED_UPLOAD_EXTENSIONS:
            return jsonify({"success": False, "message": f"File type '{file_extension}' is not allowed"}), 400

        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_UPLOAD_SIZE_BYTES:
            return jsonify({"success": False, "message": "File exceeds 10 MB limit"}), 400

        mime_type, _ = mimetypes.guess_type(original_filename)

        # Generate unique file ID and stored filename
        file_id = str(uuid.uuid4())
        stored_filename = f"{file_id}_{original_filename}"

        # Create RFPO-specific directory
        rfpo_dir = os.path.join("uploads", "rfpo_files", f"rfpo_{rfpo.id}")
        os.makedirs(rfpo_dir, exist_ok=True)

        file_path = os.path.join(rfpo_dir, stored_filename)
        file.save(file_path)

        # Get uploader name from JWT-authenticated user
        user = request.current_user
        user_name = user.get_display_name() if hasattr(user, 'get_display_name') else str(user)

        uploaded_file = UploadedFile(
            file_id=file_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            file_extension=file_extension,
            document_type=document_type if document_type else None,
            description=description if description else None,
            rfpo_id=rfpo.id,
            uploaded_by=user_name,
        )

        db.session.add(uploaded_file)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f'File "{original_filename}" uploaded successfully',
            "file": uploaded_file.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/files/<file_id>/view", methods=["GET"])
@require_auth
def view_rfpo_file(rfpo_id, file_id):
    """View/download an uploaded file"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        uploaded_file = UploadedFile.query.filter_by(
            file_id=file_id, rfpo_id=rfpo.id
        ).first_or_404()

        if not os.path.exists(uploaded_file.file_path):
            return jsonify({"success": False, "message": "File not found on disk"}), 404

        from flask import send_file
        return send_file(
            uploaded_file.file_path,
            mimetype=uploaded_file.mime_type,
            as_attachment=False,
            download_name=uploaded_file.original_filename,
        )

    except Exception as e:
        return error_response(e)


@rfpo_api.route("/<int:rfpo_id>/files/<file_id>", methods=["DELETE"])
@require_auth
def delete_rfpo_file(rfpo_id, file_id):
    """Delete an uploaded file"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        uploaded_file = UploadedFile.query.filter_by(
            file_id=file_id, rfpo_id=rfpo.id
        ).first_or_404()

        # Delete physical file
        if os.path.exists(uploaded_file.file_path):
            os.remove(uploaded_file.file_path)

        db.session.delete(uploaded_file)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f'File "{uploaded_file.original_filename}" deleted successfully',
        })

    except Exception as e:
        db.session.rollback()
        return error_response(e)


@rfpo_api.route("/doc-types", methods=["GET"])
@require_auth
def get_doc_types():
    """Get document type options for file upload"""
    try:
        doc_types = List.get_by_type("doc_types")
        types = [
            {"key": dt.key, "value": dt.value}
            for dt in doc_types
            if dt.value and dt.value.strip()
        ]
        return jsonify({"success": True, "doc_types": types})
    except Exception as e:
        return error_response(e)
