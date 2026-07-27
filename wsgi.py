import os
os.environ.setdefault('DB_BACKEND', 'mongodb')

from flask_app import app

if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host=host, port=port, debug=debug)
