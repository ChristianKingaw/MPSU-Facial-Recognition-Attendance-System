from functools import wraps
from flask import jsonify, abort
from flask_login import current_user

def admin_required(f):
    """Decorate routes to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            # Check if this is an API endpoint by looking at the request path
            from flask import request
            if request.path.startswith('/api/') or '/api/' in request.path:
                return jsonify({'error': 'Unauthorized', 'message': 'This endpoint requires admin privileges'}), 403
            else:
                abort(403)
        return f(*args, **kwargs)
    return decorated_function

def instructor_required(f):
    """Decorate routes to require instructor role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'instructor':
            return jsonify({'error': 'Unauthorized', 'message': 'This endpoint requires instructor privileges'}), 403
        return f(*args, **kwargs)
    return decorated_function 

def admin_or_instructor_required(f):
    """Decorate routes to require either admin or instructor role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'instructor']:
            # Check if this is an API endpoint by looking at the request path
            from flask import request
            if request.path.startswith('/api/') or '/api/' in request.path:
                return jsonify({'error': 'Unauthorized', 'message': 'This endpoint requires admin or instructor privileges'}), 403
            else:
                abort(403)
        return f(*args, **kwargs)
    return decorated_function