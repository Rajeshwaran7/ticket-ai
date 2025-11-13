# 🚀 Complete Setup Guide
## AI Powered Ticket Routing System with Authentication

---

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Backend Setup](#backend-setup)
3. [Frontend Setup](#frontend-setup)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [User Roles & Features](#user-roles--features)
7. [API Documentation](#api-documentation)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **Python 3.9+** - [Download](https://www.python.org/downloads/)
- **Node.js 16+** - [Download](https://nodejs.org/)
- **MySQL 5.7+ or 8.0+** - [Download](https://dev.mysql.com/downloads/)
- **Git** - [Download](https://git-scm.com/)

### API Keys
- **OpenAI API Key** - Get from [OpenAI Platform](https://platform.openai.com/)

---

## Backend Setup

### 1. Navigate to Backend Directory
```bash
cd backend
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
# Install all packages
pip install -r requirements.txt

# Install elsai-nli from custom index
pip install --index-url https://elsai-core-package.optisolbusiness.com/root/elsai-nli/ elsai-nli==0.1.0
```

### 4. Configure Environment Variables
```bash
# Copy example env file
cp env.example .env

# Edit .env with your settings
```

**`.env` Configuration:**
```env
# OpenAI API Configuration
OPENAI_API_KEY=your_actual_openai_api_key_here

# Model Configuration
ELSAI_MODEL=gpt-5-nano
ELSAI_AGENT_TYPE=openai-functions

# JWT Authentication
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_EXPIRE_MINUTES=1440

# MySQL Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=ticket_ai

# SMTP Configuration (for future notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
SMTP_FROM=noreply@ticketing.com
```

---

## Database Setup

### 1. Start MySQL Server
```bash
# Windows (if installed as service)
net start MySQL80

# macOS
brew services start mysql

# Linux
sudo systemctl start mysql
```

### 2. Create Database
```bash
# Login to MySQL
mysql -u root -p

# Run in MySQL prompt
source backend/setup_mysql.sql

# Or manually
CREATE DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;
```

### 3. Test Database Connection
```bash
cd backend
python test_mysql.py
```

Expected output:
```
✅ MySQL connection successful!
MySQL Version: 8.0.x
Current Database: ticket_ai
```

---

## Frontend Setup

### 1. Navigate to Frontend Directory
```bash
cd frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Configure Environment (Optional)
```bash
# Copy example env file
cp .env.example .env
```

**`.env` Configuration:**
```env
VITE_API_URL=http://localhost:8000
```

---

## Running the Application

### 1. Start Backend Server
```bash
cd backend
# Activate venv if not already activated
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

uvicorn main:app --reload --port 8000
```

Backend will be available at:
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

### 2. Start Frontend Server
```bash
cd frontend
npm run dev
```

Frontend will be available at:
- App: `http://localhost:5173`

---

## User Roles & Features

### 👤 Customer Role
**Access:** `/customer/chat`

**Features:**
- ✅ Chatbot interface for ticket submission
- ✅ Screenshot upload with OCR text extraction
- ✅ Real-time ticket classification
- ✅ View own tickets only
- ✅ Category and team assignment display

**How to Use:**
1. Register as "Customer" or login
2. Navigate to chat interface
3. Type your issue
4. Optionally upload screenshot
5. Submit ticket
6. View classification results

### 👨‍💼 Admin Role
**Access:** `/admin/dashboard`

**Features:**
- ✅ View all tickets from all users
- ✅ Search tickets by customer name or message
- ✅ Filter by category (billing, technical, delivery, general)
- ✅ Filter by status (pending, in_progress, resolved, closed)
- ✅ Create tickets manually
- ✅ Update ticket status
- ✅ Real-time dashboard

**How to Use:**
1. Register as "Admin" or login
2. Navigate to dashboard
3. Use search/filter to find tickets
4. Click refresh to update data
5. Manage tickets as needed

---

## API Documentation

### Authentication Endpoints

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "username",
  "password": "password123",
  "full_name": "John Doe",
  "role": "customer"  // or "admin"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "username",
  "password": "password123"
}
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "username",
    "role": "customer"
  }
}
```

### Ticket Endpoints

#### Create Ticket (Chatbot with Screenshot)
```http
POST /api/ticket/chat
Authorization: Bearer {token}
Content-Type: multipart/form-data

message: "I can't log in to my account"
customer: "John Doe"
screenshot: [file]
```

#### Get Tickets (with filters)
```http
GET /api/ticket?search=login&category=technical&status_filter=pending
Authorization: Bearer {token}
```

#### Classify Text
```http
POST /api/classify
Authorization: Bearer {token}
Content-Type: application/json

{
  "text": "I need help with my billing"
}
```

---

## Troubleshooting

### Backend Issues

#### 1. Module Not Found Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### 2. MySQL Connection Failed
```bash
# Check MySQL is running
# Windows
net start MySQL80

# Check credentials in .env
# Test connection
python test_mysql.py
```

#### 3. JWT/Authentication Errors
```bash
# Ensure JWT_SECRET_KEY is set in .env
# Clear browser localStorage and re-login
```

#### 4. File Upload Errors
```bash
# Ensure uploads directory exists
mkdir uploads

# Check file permissions
# Windows: Right-click > Properties > Security
# Linux: chmod 755 uploads
```

### Frontend Issues

#### 1. Cannot Connect to Backend
- Check backend is running on port 8000
- Check CORS settings in `backend/main.py`
- Verify `VITE_API_URL` in frontend `.env`

#### 2. Login Redirects Not Working
- Clear browser cache and localStorage
- Check browser console for errors
- Verify token is being stored

#### 3. Screenshot Upload Not Working
- Check file size (max 10MB)
- Ensure file is an image (PNG, JPG, etc.)
- Check browser console for errors

### Database Issues

#### 1. Tables Not Created
```bash
# Restart backend server - tables auto-create
# Or manually run
python -c "from models.ticket import init_db; init_db()"
```

#### 2. Migration Needed
```bash
# Drop and recreate database (WARNING: loses data)
mysql -u root -p
DROP DATABASE ticket_ai;
CREATE DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;

# Restart backend
```

---

## Default Admin Account

For testing, you can create an admin account:

```bash
# Register via API or frontend with role="admin"
```

Or via Python:
```python
from models.user import User
from models.ticket import SessionLocal

db = SessionLocal()
admin = User(
    email="admin@example.com",
    username="admin",
    hashed_password=User.hash_password("admin123"),
    full_name="Admin User",
    role="admin"
)
db.add(admin)
db.commit()
```

---

## Next Steps

1. ✅ Start both backend and frontend servers
2. ✅ Register a customer account
3. ✅ Register an admin account
4. ✅ Test customer chatbot interface
5. ✅ Test admin dashboard with filters
6. ✅ Upload a screenshot and verify OCR
7. ✅ Check ticket classification accuracy

---

## Support & Documentation

- **Backend API Docs:** http://localhost:8000/docs
- **Project README:** [README.md](README.md)
- **MySQL Setup:** [backend/MYSQL_SETUP.md](backend/MYSQL_SETUP.md)
- **Implementation Report:** [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)

---

## Security Notes

🔒 **Important for Production:**
1. Change `JWT_SECRET_KEY` to a strong random string
2. Use environment-specific `.env` files
3. Enable HTTPS
4. Set up proper CORS origins
5. Implement rate limiting
6. Regular security audits
7. Keep dependencies updated

---

**Happy Ticketing! 🎫**

