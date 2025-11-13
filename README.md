# AI Powered Ticket Routing System

A full-stack application that uses **ElsAI Foundry NLI** API to automatically classify and route customer support tickets to the appropriate teams.

## 🚀 Features

- **AI-Powered Classification**: Automatically classifies tickets using ElsAI Foundry NLI API
- **Smart Routing**: Routes tickets to appropriate teams (Billing, Technical, Delivery, General)
- **Ticket Management**: Create, view, and manage tickets through a modern web interface
- **Real-time Dashboard**: View all tickets with their classification and status
- **Confidence Scores**: See AI confidence levels for each classification

## 📋 Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **MySQL** - Relational database with PyMySQL driver
- **elsai-nli** - ElsAI Foundry NLI Python package for natural language classification

### Frontend
- **React** - UI library
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **Axios** - HTTP client

## 📁 Project Structure

```
ticket-ai/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example           # Environment variables template
│   ├── models/
│   │   ├── __init__.py
│   │   └── ticket.py          # Database models
│   ├── routes/
│   │   ├── __init__.py
│   │   └── tickets.py         # API routes
│   ├── services/
│   │   ├── __init__.py
│   │   └── elsai_service.py   # ElsAI NLI Python package integration
│   └── data/
│       └── ticket_routing.csv # Ticket routing rules and examples
├── frontend/
│   ├── package.json           # Node.js dependencies
│   ├── vite.config.js         # Vite configuration
│   ├── index.html             # HTML entry point
│   ├── .env.example          # Frontend environment variables
│   └── src/
│       ├── main.jsx           # React entry point
│       ├── App.jsx            # Main app component
│       ├── index.css          # Global styles
│       ├── pages/
│       │   ├── CreateTicket.jsx    # Create ticket page
│       │   ├── CreateTicket.css
│       │   ├── Dashboard.jsx       # Dashboard page
│       │   └── Dashboard.css
│       └── services/
│           └── api.js         # API client
└── README.md                  # This file
```

## 🛠️ Setup Instructions

### Prerequisites

- Python 3.9+ installed
- Node.js 16+ and npm installed
- MySQL 5.7+ or MySQL 8.0+ installed and running
- LLM API key (OpenAI API key or other supported model API key)

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment (recommended):**
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   **Note:** The `elsai-nli` package requires installation from a custom index:
   ```bash
   pip install --index-url https://elsai-core-package.optisolbusiness.com/root/elsai-nli/ elsai-nli==0.1.0
   ```
   Or install all dependencies including elsai-nli:
   ```bash
   pip install -r requirements.txt --extra-index-url https://elsai-core-package.optisolbusiness.com/root/elsai-nli/
   ```

5. **Set up MySQL database:**
   
   See [MYSQL_SETUP.md](backend/MYSQL_SETUP.md) for detailed instructions.
   
   Quick setup:
   ```bash
   # Login to MySQL
   mysql -u root -p
   
   # Run setup script
   source backend/setup_mysql.sql
   
   # Or manually create database
   CREATE DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   exit;
   ```

6. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and configure your settings:
   ```env
   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key_here
   ELSAI_MODEL=gpt-5-nano
   ELSAI_AGENT_TYPE=openai-functions
   
   # MySQL Configuration
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=ticket_ai
   ```

7. **Test MySQL connection (optional):**
   ```bash
   python test_mysql.py
   ```

8. **Run the backend server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`
   API documentation: `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Set up environment variables (optional):**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` if your backend runs on a different port:
   ```
   VITE_API_URL=http://localhost:8000
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

## 🎯 Usage

### Creating a Ticket

1. Navigate to the "Create Ticket" page
2. Enter customer name and ticket message
3. Optionally click "Preview Classification" to see how the ticket will be classified
4. Click "Submit Ticket" to create the ticket
5. The system will automatically:
   - Classify the ticket using ElsAI NLI API
   - Route it to the appropriate team
   - Store it in the database
   - Display the results

### Viewing Tickets

1. Navigate to the "Dashboard" page
2. View all tickets in a table format
3. See classification, assigned team, status, and confidence scores
4. The dashboard auto-refreshes every 5 seconds

## 🤖 ElsAI NLI Integration

This project uses the **elsai-nli** Python package to classify tickets. The system:

1. Uses a CSV file (`backend/data/ticket_routing.csv`) containing routing rules and examples
2. Leverages an LLM agent (via `elsai-nli`) to classify ticket text
3. Maps categories to teams automatically

The CSV file contains:
- Category definitions (billing, technical, delivery, general)
- Keywords and examples for each category
- Team assignments

You can customize the routing logic by editing `backend/data/ticket_routing.csv`.

## 🔌 API Endpoints

### POST `/api/ticket`
Create a new ticket with automatic classification.

**Request Body:**
```json
{
  "customer": "John Doe",
  "message": "I need help with my billing issue"
}
```

**Response:**
```json
{
  "id": 1,
  "customer": "John Doe",
  "message": "I need help with my billing issue",
  "category": "billing",
  "assignedTeam": "BillingTeam",
  "status": "pending",
  "createdAt": "2024-01-01T12:00:00",
  "confidence": "0.92"
}
```

### POST `/api/classify`
Classify ticket text without creating a ticket.

**Request Body:**
```json
{
  "text": "My order hasn't arrived yet"
}
```

**Response:**
```json
{
  "label": "delivery",
  "confidence": "0.88",
  "assignedTeam": "DeliveryTeam"
}
```

### GET `/api/ticket`
Get all tickets (with pagination).

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records (default: 100)

### GET `/api/ticket/{id}`
Get a specific ticket by ID.

### PUT `/api/ticket/{id}/status`
Update ticket status.

**Request Body:**
```json
{
  "status": "in_progress"
}
```

Valid statuses: `pending`, `in_progress`, `resolved`, `closed`

## 🗂️ Database Schema

```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    customer VARCHAR NOT NULL,
    message VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    assigned_team VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence VARCHAR
);
```

## 🔄 Ticket Routing Logic

The system maps categories to teams as follows:

- **billing** → BillingTeam
- **technical** → TechSupport
- **delivery** → DeliveryTeam
- **general** → GeneralSupport

## 🧪 Testing

### Test the API directly:

```bash
# Create a ticket
curl -X POST "http://localhost:8000/api/ticket" \
  -H "Content-Type: application/json" \
  -d '{"customer": "Test User", "message": "I have a billing question"}'

# Classify text
curl -X POST "http://localhost:8000/api/classify" \
  -H "Content-Type: application/json" \
  -d '{"text": "My order is delayed"}'

# Get all tickets
curl "http://localhost:8000/api/ticket"
```

## 📝 Environment Variables

### Backend (.env)
- `ELSAI_MODEL` - LLM model identifier (default: gpt-3.5-turbo)
- `ELSAI_AGENT_TYPE` - Agent type (default: openai-functions)
- `OPENAI_API_KEY` - Your OpenAI API key (required if using OpenAI models)

### Frontend (.env)
- `VITE_API_URL` - Backend API URL (default: http://localhost:8000)

## 🐛 Troubleshooting

### Backend Issues

1. **Database not found**: The database will be created automatically on first run
2. **elsai-nli installation error**: Make sure to install from the custom index URL:
   ```bash
   pip install --index-url https://elsai-core-package.optisolbusiness.com/root/elsai-nli/ elsai-nli==0.1.0
   ```
3. **API key error**: Make sure `OPENAI_API_KEY` is set in `.env` file if using OpenAI models
4. **CSV file not found**: Ensure `backend/data/ticket_routing.csv` exists
5. **Port already in use**: Change the port in the uvicorn command

### Frontend Issues

1. **Cannot connect to backend**: Check that backend is running on port 8000
2. **CORS errors**: Backend CORS is configured for localhost:3000 and localhost:5173
3. **Build errors**: Make sure all dependencies are installed with `npm install`

## 🔒 Security Notes

- Never commit `.env` files to version control
- Keep your ElsAI API key secure
- In production, use environment variables and secure database connections

## 📚 Additional Resources

- [ElsAI Foundry NLI Documentation](https://core.elsaifoundry.ai/user-guide/elsai-nli.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## 📄 License

This project is open source and available for use.

---

**Happy Ticket Routing! 🎫**

