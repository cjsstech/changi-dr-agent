"""
Authentication Service - Simple session-based authentication
"""
import json
import os
import logging
from typing import Optional
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

from core.web.app_tools import session, redirect, url_for, request, jsonify
import config
from core.web.lambda_request import LambdaRequest

from services.file_store_service import FileStorageService

logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling authentication"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or getattr(config, 'USERS_STORAGE_PATH', 'storage/users.json')
        self.storage = FileStorageService()
        self._ensure_default_user()
    
    def _ensure_default_user(self):
        """Create default admin user if no users exist"""
        users = self._load_users()
        if not users:
            # Create default admin user (password: admin)
            # Use pbkdf2:sha256 method for compatibility with older Python versions
            default_user = {
                'username': 'admin',
                'password_hash': generate_password_hash('admin', method='pbkdf2:sha256'),
                'role': 'admin'
            }
            users['admin'] = default_user
            self._save_users(users)
            logger.info("Created default admin user (username: admin, password: admin)")
    
    def _load_users(self) -> dict:
        """Load users from storage"""
        try:
            if self.storage.exists(self.storage_path):
                data = self.storage.read(self.storage_path)
                return json.loads(data.decode('utf-8'))
            return {}
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}
    
    def _save_users(self, users: dict):
        """Save users to storage"""
        try:
            data = json.dumps(users, indent=2, ensure_ascii=False).encode('utf-8')
            self.storage.write(self.storage_path, data)
        except Exception as e:
            logger.error(f"Error saving users: {e}")
            raise
    
    def login(self, username: str, password: str) -> bool:
        """
        Authenticate a user
        
        Returns:
            True if authentication successful
        """
        users = self._load_users()
        user = users.get(username)
        
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = username
            session['role'] = user.get('role', 'user')
            # session.permanent is Flask-only; skipped for Lambda
            logger.info(f"User {username} logged in")
            return True
        
        logger.warning(f"Failed login attempt for user: {username}")
        return False
    
    def logout(self):
        """Log out the current user"""
        username = session.get('username')
        session.clear()
        if username:
            logger.info(f"User {username} logged out")
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return 'username' in session
    
    def get_current_user(self) -> Optional[dict]:
        """Get current authenticated user"""
        if not self.is_authenticated():
            return None
        
        users = self._load_users()
        username = session.get('username')
        user = users.get(username, {})
        return {
            'username': username,
            'role': user.get('role', 'user')
        }

    def require_auth(self, f):
        @wraps(f)
        def decorated_function(request: LambdaRequest, *args, **kwargs):
            if not self.is_authenticated():
                # Check if this is an API request (JSON expected)
                is_json = getattr(request, 'is_json', False) if request else False
                req_path = getattr(request, 'path', '') if request else ''
                if is_json or (req_path and req_path.startswith('/admin/')):
                    return jsonify({'error': 'Authentication required', 'success': False}, status=401)
                # Otherwise redirect to login page
                return redirect(url_for('login'))
            return f(request, *args, **kwargs)
        return decorated_function

# Global instance
auth_service = AuthService()

