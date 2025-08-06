"""
User Management System
Comprehensive user authentication, authorization, and management
"""
import json
import os
import uuid
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

class UserStatus:
    """User status constants"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    LOCKED = "locked"

class AuditAction:
    """Audit action constants"""
    LOGIN = "login"
    LOGOUT = "logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    PASSWORD_CHANGED = "password_changed"
    ROLE_CHANGED = "role_changed"
    STATUS_CHANGED = "status_changed"

class UserManager:
    """Comprehensive user management system"""
    
    def __init__(self, data_file: str = "config/users.json"):
        self.data_file = data_file
        self.password_min_length = 12
        self.password_max_length = 128
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        
        # Initialize data structure
        self._ensure_data_structure()
        
    def _ensure_data_structure(self):
        """Ensure the data file exists with proper structure"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        if not os.path.exists(self.data_file):
            initial_data = {
                "users": [],
                "roles": {
                    "Administrator": {
                        "name": "Administrator",
                        "description": "Full system access",
                        "permissions": ["*"]
                    },
                    "Manager": {
                        "name": "Manager",
                        "description": "Management level access",
                        "permissions": ["read", "write", "manage_users"]
                    },
                    "User": {
                        "name": "User",
                        "description": "Standard user access",
                        "permissions": ["read", "write"]
                    },
                    "Inactive": {
                        "name": "Inactive",
                        "description": "No access",
                        "permissions": []
                    }
                },
                "audit_logs": []
            }
            self._save_data(initial_data)
    
    def _load_data(self) -> Dict:
        """Load data from JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._ensure_data_structure()
            return self._load_data()
    
    def _save_data(self, data: Dict) -> None:
        """Save data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    
    def _generate_id(self, prefix: str = "user") -> str:
        """Generate unique ID"""
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    
    def _validate_password(self, password: str) -> List[str]:
        """Validate password against policy"""
        errors = []
        
        if len(password) < self.password_min_length:
            errors.append(f"Password must be at least {self.password_min_length} characters long")
        
        if len(password) > self.password_max_length:
            errors.append(f"Password must not exceed {self.password_max_length} characters")
        
        # Check for character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;':\"<>,.?/" for c in password)
        
        if not has_upper:
            errors.append("Password must contain at least one uppercase letter")
        if not has_lower:
            errors.append("Password must contain at least one lowercase letter")
        if not has_digit:
            errors.append("Password must contain at least one number")
        if not has_special:
            errors.append("Password must contain at least one special character")
        
        return errors
    
    def _validate_email(self, email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def create_user(self, username: str, email: str, password: str, 
                   display_name: str = "", roles: List[str] = None, 
                   status: str = UserStatus.ACTIVE) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Validate inputs
            if not username or not email or not password:
                return {"success": False, "message": "Username, email, and password are required"}
            
            if not self._validate_email(email):
                return {"success": False, "message": "Invalid email format"}
            
            # Validate password
            password_errors = self._validate_password(password)
            if password_errors:
                return {"success": False, "message": "; ".join(password_errors)}
            
            # Load existing data
            data = self._load_data()
            
            # Check for existing username or email
            for user in data["users"]:
                if user["username"].lower() == username.lower():
                    return {"success": False, "message": "Username already exists"}
                if user["email"].lower() == email.lower():
                    return {"success": False, "message": "Email already exists"}
            
            # Set default roles
            if roles is None:
                roles = ["User"]
            
            # Validate roles
            valid_roles = list(data["roles"].keys())
            invalid_roles = [role for role in roles if role not in valid_roles]
            if invalid_roles:
                return {"success": False, "message": f"Invalid roles: {', '.join(invalid_roles)}"}
            
            # Create user
            user = {
                "id": self._generate_id("user"),
                "username": username,
                "email": email,
                "display_name": display_name,
                "password_hash": self._hash_password(password),
                "roles": roles,
                "status": status,
                "must_change_password": False,
                "email_verified": False,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "last_login_at": None,
                "login_attempts": 0,
                "locked_until": None
            }
            
            # Add user to data
            data["users"].append(user)
            
            # Save data
            self._save_data(data)
            
            # Log audit
            self.log_audit(user["id"], AuditAction.USER_CREATED, f"User {username} created")
            
            return {"success": True, "message": "User created successfully", "user_id": user["id"]}
            
        except Exception as e:
            return {"success": False, "message": f"Error creating user: {str(e)}"}
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with username/email and password"""
        try:
            data = self._load_data()
            
            # Find user by username or email
            user = None
            for u in data["users"]:
                if (u["username"].lower() == username.lower() or 
                    u["email"].lower() == username.lower()):
                    user = u
                    break
            
            if not user:
                return None
            
            # Check if account is locked
            if user.get("locked_until"):
                locked_until = datetime.fromisoformat(user["locked_until"].replace('Z', '+00:00'))
                if datetime.utcnow().replace(tzinfo=locked_until.tzinfo) < locked_until:
                    return None
            
            # Verify password
            if not self._verify_password(password, user["password_hash"]):
                # Increment login attempts
                user["login_attempts"] = user.get("login_attempts", 0) + 1
                
                # Lock account if max attempts reached
                if user["login_attempts"] >= self.max_login_attempts:
                    user["locked_until"] = (datetime.utcnow() + self.lockout_duration).isoformat() + "Z"
                    self.log_audit(user["id"], "account_locked", "Account locked due to failed login attempts")
                
                self._save_data(data)
                return None
            
            # Reset login attempts on successful login
            user["login_attempts"] = 0
            user["locked_until"] = None
            
            # Log successful login
            self.log_audit(user["id"], AuditAction.LOGIN, f"User {user['username']} logged in")
            
            return user
            
        except Exception as e:
            print(f"Authentication error: {e}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            data = self._load_data()
            for user in data["users"]:
                if user["id"] == user_id:
                    return user
            return None
        except Exception:
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            data = self._load_data()
            for user in data["users"]:
                if user["username"].lower() == username.lower():
                    return user
            return None
        except Exception:
            return None
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user information"""
        try:
            data = self._load_data()
            
            # Find user
            user_index = None
            for i, user in enumerate(data["users"]):
                if user["id"] == user_id:
                    user_index = i
                    break
            
            if user_index is None:
                return {"success": False, "message": "User not found"}
            
            user = data["users"][user_index]
            
            # Update allowed fields
            allowed_fields = ["display_name", "email", "roles", "status"]
            for field in allowed_fields:
                if field in updates:
                    user[field] = updates[field]
            
            # Validate email if updated
            if "email" in updates and not self._validate_email(updates["email"]):
                return {"success": False, "message": "Invalid email format"}
            
            # Check for email conflicts
            if "email" in updates:
                for other_user in data["users"]:
                    if (other_user["id"] != user_id and 
                        other_user["email"].lower() == updates["email"].lower()):
                        return {"success": False, "message": "Email already exists"}
            
            # Validate roles
            if "roles" in updates:
                valid_roles = list(data["roles"].keys())
                invalid_roles = [role for role in updates["roles"] if role not in valid_roles]
                if invalid_roles:
                    return {"success": False, "message": f"Invalid roles: {', '.join(invalid_roles)}"}
            
            user["updated_at"] = datetime.utcnow().isoformat() + "Z"
            
            # Save data
            self._save_data(data)
            
            # Log audit
            self.log_audit(user_id, AuditAction.USER_UPDATED, f"User {user['username']} updated")
            
            return {"success": True, "message": "User updated successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error updating user: {str(e)}"}
    
    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """Delete user"""
        try:
            data = self._load_data()
            
            # Find and remove user
            user_to_delete = None
            for i, user in enumerate(data["users"]):
                if user["id"] == user_id:
                    user_to_delete = data["users"].pop(i)
                    break
            
            if not user_to_delete:
                return {"success": False, "message": "User not found"}
            
            # Save data
            self._save_data(data)
            
            # Log audit
            self.log_audit(user_id, AuditAction.USER_DELETED, f"User {user_to_delete['username']} deleted")
            
            return {"success": True, "message": "User deleted successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error deleting user: {str(e)}"}
    
    def update_user_status(self, user_id: str, status: str) -> Dict[str, Any]:
        """Update user status"""
        try:
            valid_statuses = [UserStatus.ACTIVE, UserStatus.INACTIVE, UserStatus.PENDING, UserStatus.LOCKED]
            if status not in valid_statuses:
                return {"success": False, "message": "Invalid status"}
            
            return self.update_user(user_id, {"status": status})
            
        except Exception as e:
            return {"success": False, "message": f"Error updating status: {str(e)}"}
    
    def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp"""
        try:
            data = self._load_data()
            for user in data["users"]:
                if user["id"] == user_id:
                    user["last_login_at"] = datetime.utcnow().isoformat() + "Z"
                    break
            self._save_data(data)
        except Exception:
            pass
    
    def get_users(self, page: int = 1, per_page: int = 10, 
                  search: str = "", role_filter: str = "") -> Dict[str, Any]:
        """Get paginated users list"""
        try:
            data = self._load_data()
            users = data["users"]
            
            # Apply search filter
            if search:
                search_lower = search.lower()
                users = [u for u in users if (
                    search_lower in u["username"].lower() or
                    search_lower in u["email"].lower() or
                    search_lower in u.get("display_name", "").lower()
                )]
            
            # Apply role filter
            if role_filter:
                users = [u for u in users if role_filter in u.get("roles", [])]
            
            # Calculate pagination
            total_users = len(users)
            total_pages = (total_users + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_users = users[start_idx:end_idx]
            
            # Remove password hashes from response
            safe_users = []
            for user in paginated_users:
                safe_user = user.copy()
                safe_user.pop("password_hash", None)
                safe_users.append(safe_user)
            
            return {
                "success": True,
                "users": safe_users,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_users": total_users,
                    "total_pages": total_pages
                }
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error getting users: {str(e)}"}
    
    def get_roles(self) -> List[Dict[str, Any]]:
        """Get available roles"""
        try:
            data = self._load_data()
            return list(data["roles"].values())
        except Exception:
            return []
    
    def log_audit(self, user_id: str, action: str, details: str) -> None:
        """Log audit event"""
        try:
            data = self._load_data()
            
            audit_entry = {
                "id": self._generate_id("audit"),
                "user_id": user_id,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "ip_address": None  # Could be populated from request
            }
            
            data["audit_logs"].append(audit_entry)
            
            # Keep only last 1000 audit logs to prevent file from growing too large
            if len(data["audit_logs"]) > 1000:
                data["audit_logs"] = data["audit_logs"][-1000:]
            
            self._save_data(data)
            
        except Exception as e:
            print(f"Error logging audit: {e}")
    
    def get_audit_logs(self, page: int = 1, per_page: int = 10) -> List[Dict[str, Any]]:
        """Get paginated audit logs"""
        try:
            data = self._load_data()
            logs = sorted(data["audit_logs"], key=lambda x: x["timestamp"], reverse=True)
            
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_logs = logs[start_idx:end_idx]
            
            return paginated_logs
            
        except Exception:
            return []
    
    def change_password(self, user_id: str, current_password: str, new_password: str) -> Dict[str, Any]:
        """Change user password"""
        try:
            data = self._load_data()
            
            # Find user
            user = None
            for u in data["users"]:
                if u["id"] == user_id:
                    user = u
                    break
            
            if not user:
                return {"success": False, "message": "User not found"}
            
            # Verify current password
            if not self._verify_password(current_password, user["password_hash"]):
                return {"success": False, "message": "Current password is incorrect"}
            
            # Validate new password
            password_errors = self._validate_password(new_password)
            if password_errors:
                return {"success": False, "message": "; ".join(password_errors)}
            
            # Update password
            user["password_hash"] = self._hash_password(new_password)
            user["must_change_password"] = False
            user["updated_at"] = datetime.utcnow().isoformat() + "Z"
            
            # Save data
            self._save_data(data)
            
            # Log audit
            self.log_audit(user_id, AuditAction.PASSWORD_CHANGED, "Password changed")
            
            return {"success": True, "message": "Password changed successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error changing password: {str(e)}"}
    
    def has_permission(self, user: Dict[str, Any], permission: str) -> bool:
        """Check if user has specific permission"""
        try:
            data = self._load_data()
            user_roles = user.get("roles", [])
            
            for role_name in user_roles:
                role = data["roles"].get(role_name, {})
                permissions = role.get("permissions", [])
                
                # Check for wildcard permission or specific permission
                if "*" in permissions or permission in permissions:
                    return True
            
            return False
            
        except Exception:
            return False
