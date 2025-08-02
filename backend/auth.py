"""
Authentication and Security Module for Portfolio Analyzer
"""

import hashlib
import secrets
import time
from functools import wraps
from flask import request, jsonify, session
import hmac
import json
from datetime import datetime, timedelta

class SecurityManager:
    def __init__(self):
        # Generate secure secret keys
        self.secret_key = secrets.token_hex(32)
        self.rate_limit_storage = {}
        self.failed_attempts = {}
        self.blocked_ips = {}
        
        # Security settings
        self.max_requests_per_minute = 30
        self.max_failed_attempts = 5
        self.block_duration = 900  # 15 minutes
        self.session_timeout = 3600  # 1 hour
        
        # Default admin credentials (CHANGE THESE!)
        self.admin_username = "admin"
        self.admin_password_hash = self.hash_password("portfolio2025!")  # CHANGE THIS!
        
    def hash_password(self, password):
        """Securely hash password with salt"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return f"{salt}:{password_hash.hex()}"
    
    def verify_password(self, password, stored_hash):
        """Verify password against stored hash"""
        try:
            salt, hash_part = stored_hash.split(':')
            password_hash = hashlib.pbkdf2_hmac('sha256',
                                              password.encode('utf-8'),
                                              salt.encode('utf-8'),
                                              100000)
            return hmac.compare_digest(hash_part, password_hash.hex())
        except:
            return False
    
    def authenticate_user(self, username, password):
        """Authenticate user credentials"""
        if username == self.admin_username and self.verify_password(password, self.admin_password_hash):
            return True
        return False
    
    def is_rate_limited(self, ip_address):
        """Check if IP is rate limited"""
        current_time = time.time()
        
        # Clean old entries
        self.rate_limit_storage = {
            ip: timestamps for ip, timestamps in self.rate_limit_storage.items()
            if any(current_time - t < 60 for t in timestamps)
        }
        
        # Check current IP
        if ip_address not in self.rate_limit_storage:
            self.rate_limit_storage[ip_address] = []
        
        # Remove timestamps older than 1 minute
        self.rate_limit_storage[ip_address] = [
            t for t in self.rate_limit_storage[ip_address] 
            if current_time - t < 60
        ]
        
        # Check if over limit
        if len(self.rate_limit_storage[ip_address]) >= self.max_requests_per_minute:
            return True
        
        # Add current request
        self.rate_limit_storage[ip_address].append(current_time)
        return False
    
    def is_ip_blocked(self, ip_address):
        """Check if IP is blocked due to failed attempts"""
        if ip_address in self.blocked_ips:
            if time.time() - self.blocked_ips[ip_address] > self.block_duration:
                del self.blocked_ips[ip_address]
                if ip_address in self.failed_attempts:
                    del self.failed_attempts[ip_address]
                return False
            return True
        return False
    
    def record_failed_attempt(self, ip_address):
        """Record failed login attempt"""
        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = []
        
        current_time = time.time()
        self.failed_attempts[ip_address].append(current_time)
        
        # Remove attempts older than 1 hour
        self.failed_attempts[ip_address] = [
            t for t in self.failed_attempts[ip_address]
            if current_time - t < 3600
        ]
        
        # Block IP if too many failed attempts
        if len(self.failed_attempts[ip_address]) >= self.max_failed_attempts:
            self.blocked_ips[ip_address] = current_time
    
    def validate_input(self, data, max_length=1000):
        """Validate and sanitize input data"""
        if not isinstance(data, str):
            return False
        
        if len(data) > max_length:
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            '<script', 'javascript:', 'data:', 'vbscript:', 
            'onload=', 'onerror=', 'onclick=', 'eval(',
            'document.', 'window.', 'alert(', 'prompt(',
            'DROP TABLE', 'SELECT *', 'INSERT INTO', 'DELETE FROM'
        ]
        
        data_lower = data.lower()
        for pattern in suspicious_patterns:
            if pattern in data_lower:
                return False
        
        return True

# Global security manager instance
security_manager = SecurityManager()

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        # Check if IP is blocked
        if security_manager.is_ip_blocked(client_ip):
            return jsonify({'error': 'IP blocked due to suspicious activity'}), 429
        
        # Check rate limiting
        if security_manager.is_rate_limited(client_ip):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Check authentication
        if 'authenticated' not in session or not session['authenticated']:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check session timeout
        if 'login_time' in session:
            if time.time() - session['login_time'] > security_manager.session_timeout:
                session.clear()
                return jsonify({'error': 'Session expired'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_only(f):
    """Decorator for rate limiting without authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        if security_manager.is_ip_blocked(client_ip):
            return jsonify({'error': 'IP blocked due to suspicious activity'}), 429
        
        if security_manager.is_rate_limited(client_ip):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        return f(*args, **kwargs)
    return decorated_function

def validate_request_data(f):
    """Decorator to validate request data"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validate JSON data if present
        if request.json:
            for key, value in request.json.items():
                if isinstance(value, str) and not security_manager.validate_input(value):
                    return jsonify({'error': f'Invalid input data for field: {key}'}), 400
        
        # Validate form data if present
        if request.form:
            for key, value in request.form.items():
                if not security_manager.validate_input(value):
                    return jsonify({'error': f'Invalid input data for field: {key}'}), 400
        
        return f(*args, **kwargs)
    return decorated_function