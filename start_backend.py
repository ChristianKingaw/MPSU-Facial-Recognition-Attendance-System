#!/usr/bin/env python3
"""
Flask Backend Launcher
Starts the Flask backend for FRCAS-ClassPass
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Launch the Flask backend"""
    # Get the directory of this script (root directory)
    root_dir = Path(__file__).parent.absolute()

    # Change to the backend directory
    backend_dir = root_dir / "backend"
    os.chdir(backend_dir)

    # Set Flask environment variables
    os.environ['FLASK_APP'] = 'app:create_app'
    os.environ['FLASK_ENV'] = 'development'
    os.environ['PYTHONPATH'] = str(backend_dir)
    os.environ['FLASK_RUN_HOST'] = '0.0.0.0'

    # Run the app using subprocess
    try:
        # Use the same Python executable that's running this script
        python_exe = sys.executable

        # Run flask run with host and HTTPS for camera access
        result = subprocess.run([python_exe, "-m", "flask", "run", "--host=0.0.0.0", "--port=5000", "--cert=cert.pem", "--key=key.pem"], check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error running Flask backend: {e}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
    
if __name__ == "__main__":
    main()