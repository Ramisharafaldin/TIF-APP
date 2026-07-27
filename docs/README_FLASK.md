# Flask Application - Inventory Management and Forecasting System

## Overview

This is a Flask-based web application for inventory management, branch transfers, and sales forecasting. The application was migrated from Streamlit to Flask while preserving all existing business logic and functionality.

### Key Features

- **User Authentication**: Secure login system with admin and regular user roles
- **Inventory Analysis**: Analyze stock levels, identify critical items, and detect stagnant inventory
- **Branch Transfers**: Balance inventory across multiple branches with automated transfer recommendations
- **Sales Forecasting**: Predict future sales using XGBoost machine learning models
- **Admin Panel**: User management interface for administrators
- **Multi-language Support**: Arabic (RTL) interface with Bootstrap styling
- **SQLite Storage**: Efficient database storage for uploaded files and processed data (no session size limits)

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Application Structure](#application-structure)
- [Features and Usage](#features-and-usage)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Prerequisites

Before running the application, ensure you have the following installed:

- **Python 3.8 or higher**
- **pip** (Python package installer)
- **Virtual environment** (recommended)

### System Requirements

- **RAM**: Minimum 4GB (8GB recommended for large datasets)
- **Disk Space**: At least 500MB for application and dependencies
- **Operating System**: Windows, Linux, or macOS

## Installation

### 1. Clone or Download the Repository

```bash
# If using git
git clone <repository-url>
cd <project-directory>

# Or download and extract the ZIP file
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the Database

The application will automatically create the SQLite database (`users.db`) on first run with a default admin user:

- **Username**: `admin`
- **Password**: `admin123`

**IMPORTANT**: Change the default admin password immediately after first login!

## Configuration

### Environment Variables

The application uses environment variables for configuration. Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env
```

### Required Configuration

Edit the `.env` file and set the following:

```bash
# REQUIRED: Generate a strong secret key for production
SECRET_KEY=your-secret-key-here-change-this-in-production

# Environment: development or production
FLASK_ENV=development
```

### Generate a Secure Secret Key

For production, generate a strong random secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and set it as your `SECRET_KEY` in the `.env` file.

### Optional Configuration

Additional settings in `.env`:

```bash
# Debug mode (never use True in production)
FLASK_DEBUG=True

# Host and port
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Database path
DATABASE_PATH=users.db

# Upload settings
MAX_CONTENT_LENGTH_MB=50
UPLOAD_FOLDER=uploads
```

### Configuration Classes

The application supports two configuration modes:

1. **Development** (`DevelopmentConfig`):
   - Debug mode enabled
   - Detailed error pages
   - Less strict security settings

2. **Production** (`ProductionConfig`):
   - Debug mode disabled
   - Secure cookie settings
   - Requires HTTPS
   - Strict session management

## Running the Application

### Development Mode

#### Option 1: Using the Batch File (Windows)

```bash
run_flask.bat
```

#### Option 2: Using Python Directly

```bash
# Windows
set FLASK_APP=flask_app.py
set FLASK_ENV=development
python flask_app.py

# Linux/macOS
export FLASK_APP=flask_app.py
export FLASK_ENV=development
python flask_app.py
```

#### Option 3: Using Flask CLI

```bash
flask run --host=0.0.0.0 --port=5000
```

### Accessing the Application

Once running, open your web browser and navigate to:

```
http://localhost:5000
```

Or from another device on the same network:

```
http://<your-ip-address>:5000
```

### Default Login Credentials

- **Username**: `admin`
- **Password**: `admin123`

**Change these immediately after first login!**

## Application Structure

```
project_root/
├── flask_app.py              # Main Flask application with all routes
├── auth_flask.py             # Authentication module (Flask-compatible)
├── config.py                 # Configuration classes
├── .env                      # Environment variables (create from .env.example)
├── .env.example              # Example environment configuration
├── requirements.txt          # Python dependencies
├── run_flask.bat             # Windows batch file to run the app
├── users.db                  # SQLite database (created automatically)
│
├── templates/                # Jinja2 HTML templates
│   ├── base.html            # Base template with navigation
│   ├── login.html           # Login page
│   ├── home.html            # Home dashboard
│   ├── inventory.html       # Inventory analysis page
│   ├── transfers.html       # Branch transfers page
│   ├── forecasting.html     # Sales forecasting page
│   ├── admin.html           # Admin user management page
│   ├── 403.html             # Forbidden error page
│   ├── 404.html             # Not found error page
│   ├── 413.html             # File too large error page
│   └── 500.html             # Internal server error page
│
├── static/                   # Static assets
│   ├── css/
│   │   └── custom.css       # Custom styles (RTL support, etc.)
│   └── js/
│       └── app.js           # Client-side JavaScript
│
├── utils/                    # Business logic utilities
│   ├── data_processing.py   # Data loading and processing
│   ├── analysis.py          # Inventory analysis logic
│   ├── forecasting.py       # Sales forecasting pipeline
│   ├── ui_helpers.py        # UI formatting and export functions
│   ├── flask_helpers.py     # Flask-specific helper functions
│   └── validation.py        # Input validation functions
│
├── uploads/                  # Temporary file uploads (created automatically)
├── logs/                     # Application logs (created automatically)
│   ├── flask_app.log        # General application logs
│   └── errors.log           # Error logs
│
├── data/                     # Data files
│   └── Branch.xlsx          # Branch information
│
└── forecast_modules/         # Forecasting data and models
    ├── special_events.xlsx  # Special events calendar
    └── generate_model_a.py  # Model generation script
```

## Features and Usage

### 1. User Authentication

#### Login
- Navigate to `/login`
- Enter username and password
- Click "تسجيل الدخول" (Login)

#### Logout
- Click the logout button in the navigation bar
- Session data is cleared automatically

### 2. Inventory Analysis

#### Upload Data
1. Navigate to "تحليل المخزون" (Inventory Analysis)
2. Click "اختر ملف" (Choose File) and select an Excel file
3. File must contain two sheets:
   - `Transactions`: Sales transaction data
   - `Item info`: Product information
4. Click "رفع الملف" (Upload File)

#### Configure Analysis
1. Set analysis parameters:
   - **Min Coverage**: Minimum days of stock coverage (default: 7)
   - **Max Coverage**: Maximum days of stock coverage (default: 30)
   - **Forecast Days**: Days to forecast (default: 30)
   - **Safety Stock**: Safety stock quantity (default: 0)
   - **Reorder Point**: Reorder point quantity (default: 0)
   - **Stagnant Period**: Days to consider item stagnant (default: 90)
2. Select date range (start and end dates)
3. Click "تحليل" (Analyze)

#### View Results
- **General Report**: All items with coverage analysis
- **Critical Items**: Items below minimum coverage
- **Stagnant Items**: Items with no sales in stagnant period

#### Export Results
- Click "تصدير التقرير" (Export Report)
- Downloads Excel file with multiple sheets

### 3. Branch Transfers

#### Upload Branch Data
1. Navigate to "نقل بين الفروع" (Branch Transfers)
2. Select branch code from dropdown
3. Upload Excel file for that branch
4. Repeat for all branches (minimum 2 branches required)

#### Run Analysis
1. Set coverage parameters (min and max)
2. Select date range
3. Click "تحليل التوازن" (Analyze Balance)

#### View Results
- **Transfer Recommendations**: Suggested transfers between branches
- **Branch Summary**: Coverage status for each branch

#### Export Results
- Click "تصدير التقرير الكامل" (Export Full Report)
- Downloads Excel file with transfers and summary sheets

### 4. Sales Forecasting

#### Upload Data
1. Navigate to "التنبؤ بالمبيعات" (Sales Forecasting)
2. Upload unified Excel file with Sales and Inventory sheets
3. Select date range for historical data
4. Click "رفع الملف" (Upload File)

#### Run Forecast
1. Set forecast days (1-365)
2. Click "تشغيل التنبؤ" (Run Forecast)
3. Wait for processing (may take several minutes)

#### View Results
- **Product Summary**: Forecast summary by product
- **Feature Importance**: Top features influencing predictions
- **Charts**: Visual representation of forecasts (if available)

#### Export Results
- Click "تصدير ملخص التنبؤ" (Export Forecast Summary)
- Downloads Excel file with forecast data

### 5. Admin Panel (Admin Users Only)

#### View Users
- Navigate to "إدارة المستخدمين" (User Management)
- View list of all users with their roles

#### Add User
1. Enter username (3-50 characters, alphanumeric and underscore only)
2. Enter password (minimum 6 characters)
3. Check "مسؤول" (Admin) if user should have admin privileges
4. Click "إضافة مستخدم" (Add User)

#### Delete User
1. Select user from dropdown
2. Click "حذف المستخدم" (Delete User)
3. Confirm deletion
4. Note: Cannot delete your own account

#### Change Password
1. Select user from dropdown
2. Enter new password
3. Click "تغيير كلمة المرور" (Change Password)

## Deployment

### Production Deployment Checklist

1. **Set Environment to Production**
   ```bash
   FLASK_ENV=production
   ```

2. **Generate Strong Secret Key**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Disable Debug Mode**
   ```bash
   FLASK_DEBUG=False
   ```

4. **Use Production WSGI Server**
   - Do NOT use Flask's built-in server in production
   - Use Gunicorn, uWSGI, or Waitress

### Deployment with Gunicorn (Linux)

#### Install Gunicorn
```bash
pip install gunicorn
```

#### Run with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 flask_app:app
```

Options:
- `-w 4`: Use 4 worker processes
- `-b 0.0.0.0:5000`: Bind to all interfaces on port 5000
- `--timeout 300`: Set timeout for long operations

### Deployment with Waitress (Windows)

#### Install Waitress
```bash
pip install waitress
```

#### Run with Waitress
```python
# Create serve.py
from waitress import serve
from flask_app import app

serve(app, host='0.0.0.0', port=5000, threads=4)
```

```bash
python serve.py
```

### Reverse Proxy with Nginx

For production, use Nginx as a reverse proxy:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/your/app/static;
        expires 30d;
    }

    client_max_body_size 50M;
}
```

### HTTPS Configuration

For production, always use HTTPS:

1. Obtain SSL certificate (Let's Encrypt, etc.)
2. Configure Nginx with SSL
3. Set `SESSION_COOKIE_SECURE=True` in config
4. Redirect HTTP to HTTPS

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

**Error**: `ModuleNotFoundError`
- **Solution**: Install all dependencies: `pip install -r requirements.txt`

**Error**: `SECRET_KEY not set`
- **Solution**: Create `.env` file and set `SECRET_KEY`

#### 2. File Upload Fails

**Error**: "File size exceeds maximum"
- **Solution**: Increase `MAX_CONTENT_LENGTH` in config.py or .env

**Error**: "Invalid file type"
- **Solution**: Ensure file is .xlsx or .xls format

#### 3. Database Errors

**Error**: "Database is locked"
- **Solution**: Close other connections to users.db

**Error**: "No such table: users"
- **Solution**: Delete users.db and restart app to recreate

#### 4. Session Issues

**Error**: "Please log in to access this page"
- **Solution**: Clear browser cookies and log in again

**Error**: Session data lost
- **Solution**: Check `PERMANENT_SESSION_LIFETIME` in config

#### 5. Analysis Errors

**Error**: "Failed to process file"
- **Solution**: Verify Excel file has required sheets (Transactions, Item info)

**Error**: "No data found for date range"
- **Solution**: Check date range and ensure data exists

### Logging

Application logs are stored in the `logs/` directory:

- **flask_app.log**: General application logs
- **errors.log**: Error logs with request context

View logs to diagnose issues:

```bash
# View recent logs
tail -f logs/flask_app.log

# View errors
tail -f logs/errors.log
```

### Debug Mode

For development troubleshooting, enable debug mode:

```bash
FLASK_DEBUG=True
FLASK_ENV=development
```

**WARNING**: Never enable debug mode in production!

## Security Considerations

### Best Practices

1. **Secret Key**
   - Use a strong, random secret key
   - Never commit secret keys to version control
   - Rotate keys periodically

2. **Passwords**
   - Change default admin password immediately
   - Use strong passwords (minimum 6 characters)
   - Passwords are hashed with bcrypt

3. **File Uploads**
   - Only .xlsx and .xls files are accepted
   - File size limited to 50MB
   - Temporary files are cleaned up after processing

4. **Session Security**
   - Sessions expire after 24 hours
   - HttpOnly cookies prevent XSS attacks
   - SameSite cookies prevent CSRF attacks

5. **CSRF Protection**
   - All forms include CSRF tokens
   - Flask-WTF provides CSRF protection

6. **Input Validation**
   - All user inputs are validated
   - SQL injection prevented by parameterized queries
   - XSS prevented by Jinja2 auto-escaping

7. **Access Control**
   - Admin routes require admin privileges
   - Protected routes require authentication
   - 403 errors for unauthorized access

### Production Security Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_DEBUG=False`
- [ ] Enable HTTPS
- [ ] Set `SESSION_COOKIE_SECURE=True`
- [ ] Use production WSGI server (not Flask dev server)
- [ ] Configure firewall rules
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity
- [ ] Backup database regularly
- [ ] Limit file upload sizes
- [ ] Use strong passwords for all users

## Additional Resources

### Dependencies

- **Flask**: Web framework
- **Flask-WTF**: CSRF protection and form handling
- **pandas**: Data manipulation
- **numpy**: Numerical operations
- **openpyxl**: Excel file reading/writing
- **xlsxwriter**: Excel file generation
- **bcrypt**: Password hashing
- **xgboost**: Machine learning for forecasting
- **scikit-learn**: Machine learning utilities
- **python-dotenv**: Environment variable management

### Support

For issues or questions:
1. Check the troubleshooting section
2. Review application logs
3. Consult Flask documentation: https://flask.palletsprojects.com/
4. Contact system administrator

### Version Information

- **Application Version**: 1.0.0
- **Flask Version**: 3.x
- **Python Version**: 3.8+

## License

[Add your license information here]

## Changelog

### Version 1.0.0 (Initial Release)
- Migrated from Streamlit to Flask
- Implemented user authentication
- Added inventory analysis module
- Added branch transfer module
- Added sales forecasting module
- Added admin panel
- Implemented error handling and logging
- Added Arabic RTL support
