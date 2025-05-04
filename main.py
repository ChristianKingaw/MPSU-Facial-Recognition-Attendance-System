import os
from dotenv import load_dotenv

# Load environment variables from .env and .flaskenv files
load_dotenv('.env')
load_dotenv('.flaskenv')

# Hard-coded secret key as fallback if environment variable is not set
if not os.environ.get('SESSION_SECRET'):
    os.environ['SESSION_SECRET'] = 'thisisasecretkey123456789'

# Import the app after setting environment variables
from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
