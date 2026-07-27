"""
Flask helper utilities for file upload handling and DataFrame serialization.
"""

import os
import pickle
import base64
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
import pandas as pd


# File upload configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB



def allowed_file(filename: str) -> bool:
    """
    Check if the uploaded file has an allowed extension using current_app config.
    """
    from flask import current_app
    if not filename:
        return False
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_upload(file) -> str:
    """
    Save uploaded file with a unique name and return the file path.
    
    Args:
        file: FileStorage object from Flask request
        
    Returns:
        str: Path to the saved file
        
    Raises:
        ValueError: If file is invalid or has disallowed extension
        OSError: If file cannot be saved
    """
    if not file:
        raise ValueError("No file provided")
    
    if not file.filename:
        raise ValueError("File has no filename")
    
    if not allowed_file(file.filename):
        from flask import current_app
        allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
        raise ValueError(f"File type not allowed. Allowed types: {', '.join(sorted(allowed))}")
    
    # Determine upload folder from app config
    from flask import current_app
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    secure_name = secure_filename(file.filename)
    unique_filename = f"{timestamp}_{secure_name}"
    
    filepath = os.path.join(upload_folder, unique_filename)
    
    try:
        file.save(filepath)
    except Exception as e:
        raise OSError(f"Failed to save file: {str(e)}")
    
    return filepath


def list_uploaded_files() -> list:
    """List files present in the configured UPLOAD_FOLDER.

    Returns a list of dicts with keys: filename, size, modified
    """
    from flask import current_app
    upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    files = []
    try:
        os.makedirs(upload_folder, exist_ok=True)
    except Exception:
        pass
    try:
        for fname in sorted(os.listdir(upload_folder), reverse=True):
            fpath = os.path.join(upload_folder, fname)
            if os.path.isfile(fpath):
                files.append({
                    'filename': fname,
                    'size': os.path.getsize(fpath),
                    'modified': datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                })
    except Exception:
        # Return empty list on any error; caller can log if needed
        return []
    return files


def cleanup_upload(filepath: str) -> None:
    """
    Delete temporary uploaded file.
    
    Args:
        filepath: Path to the file to delete
        
    Note:
        Silently ignores if file doesn't exist
    """
    if not filepath:
        return
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        # Log error but don't raise - cleanup is best effort
        print(f"Warning: Failed to cleanup file {filepath}: {str(e)}")


def serialize_dataframe(df: pd.DataFrame) -> str:
    """
    Serialize a pandas DataFrame to a base64-encoded string for session storage.
    
    Args:
        df: pandas DataFrame to serialize
        
    Returns:
        str: Base64-encoded pickled DataFrame
        
    Raises:
        ValueError: If serialization fails
    """
    if df is None:
        raise ValueError("Cannot serialize None DataFrame")
    
    try:
        pickled = pickle.dumps(df)
        encoded = base64.b64encode(pickled).decode('utf-8')
        return encoded
    except Exception as e:
        raise ValueError(f"Failed to serialize DataFrame: {str(e)}")


def deserialize_dataframe(data: str) -> pd.DataFrame:
    """
    Deserialize a base64-encoded string back to a pandas DataFrame.
    
    Args:
        data: Base64-encoded pickled DataFrame string
        
    Returns:
        pd.DataFrame: Restored DataFrame
        
    Raises:
        ValueError: If deserialization fails
    """
    if not data:
        raise ValueError("Cannot deserialize empty data")
    
    try:
        decoded = base64.b64decode(data.encode('utf-8'))
        df = pickle.loads(decoded)
        return df
    except Exception as e:
        raise ValueError(f"Failed to deserialize DataFrame: {str(e)}")
