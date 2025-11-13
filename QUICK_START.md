# ⚡ Quick Start Guide
## Get Up and Running in 5 Minutes

---

## 🎯 Prerequisites Check

Before starting, ensure you have:
- [ ] Python 3.9+ installed
- [ ] Node.js 16+ installed
- [ ] MySQL 5.7+ installed and running
- [ ] OpenAI API key ready

---

## 🚀 Quick Setup (5 Steps)

### Step 1: Clone & Install (2 min)

```bash
# Navigate to project
cd ticket-ai

# Backend dependencies
cd backend
pip install -r requirements.txt
pip install --index-url https://elsai-core-package.optisolbusiness.com/root/elsai-nli/ elsai-nli==0.1.0

# Frontend dependencies
cd ../frontend
npm install
```

### Step 2: Setup MySQL (1 min)

```bash
# Login to MySQL
mysql -u root -p

# Run this in MySQL prompt
CREATE DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;
```

### Step 3: Configure Environment (1 min)

```bash
# Backend
cd backend
cp env.example .env

# Edit .env - Update these 3 lines:
# OPENAI_API_KEY=your_actual_key_here
# DB_PASSWORD=your_mysql_password
# JWT_SECRET_KEY=change-this-to-random-string
```

### Step 4: Create Test Users (30 sec)

```bash
# Still in backend directory
python create_admin.py
```

This creates:
- **Admin:** username: `admin`, password: `admin123`
- **Customer:** username: `customer`, password: `customer123`

### Step 5: Start Servers (30 sec)

```bash
# Terminal 1: Backend
cd backend
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

---

## 🎉 You're Ready!

### Access the Application

1. **Open Browser:** http://localhost:5173

2. **Login as Customer:**
   - Username: `customer`
   - Password: `customer123`
   - You'll see the chatbot interface

3. **Login as Admin:**
   - Username: `admin`
   - Password: `admin123`
   - You'll see the dashboard

---

## 🧪 Quick Test

### Test Customer Chatbot:
1. Login as customer
2. Type: "I can't access my account"
3. Optionally upload a screenshot
4. Click "Send Ticket"
5. See AI classification result!

### Test Admin Dashboard:
1. Login as admin
2. See all tickets
3. Try search: type "account"
4. Try filter: select "Technical"
5. See filtered results!

---

## 🔧 Troubleshooting

### Backend won't start?
```bash
# Check MySQL is running
mysql -u root -p

# Test connection
python test_mysql.py
```

### Frontend won't start?
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Can't login?
- Check backend is running (http://localhost:8000/docs)
- Clear browser localStorage
- Check browser console for errors

---

## 📚 Next Steps

- [ ] Read [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup
- [ ] Check [FEATURES_SUMMARY.md](FEATURES_SUMMARY.md) for all features
- [ ] Review [API Documentation](http://localhost:8000/docs)
- [ ] Test screenshot upload
- [ ] Try search and filters
- [ ] Create more test tickets

---

## 🎯 Default Test Accounts

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Admin | admin | admin123 | /admin/dashboard |
| Customer | customer | customer123 | /customer/chat |

⚠️ **Change passwords in production!**

---

## 📞 Need Help?

1. Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions
2. Review [TROUBLESHOOTING section](SETUP_GUIDE.md#troubleshooting)
3. Check backend logs in terminal
4. Check browser console for frontend errors

---

**Happy Testing! 🎫**

