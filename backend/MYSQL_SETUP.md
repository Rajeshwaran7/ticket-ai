# MySQL Setup Guide

## Prerequisites

- MySQL Server 5.7+ or MySQL 8.0+ installed
- MySQL running on your system

## Installation

### Windows

1. **Download MySQL:**
   - Visit https://dev.mysql.com/downloads/installer/
   - Download MySQL Installer
   - Run installer and select "MySQL Server"

2. **During installation:**
   - Set root password
   - Keep default port (3306)
   - Configure as Windows Service (optional)

### macOS

```bash
# Using Homebrew
brew install mysql

# Start MySQL service
brew services start mysql

# Secure installation
mysql_secure_installation
```

### Linux (Ubuntu/Debian)

```bash
# Install MySQL
sudo apt update
sudo apt install mysql-server

# Start MySQL service
sudo systemctl start mysql
sudo systemctl enable mysql

# Secure installation
sudo mysql_secure_installation
```

## Database Setup

### Option 1: Using MySQL Command Line

1. **Login to MySQL:**
   ```bash
   mysql -u root -p
   ```

2. **Run setup script:**
   ```sql
   source backend/setup_mysql.sql
   ```

3. **Exit MySQL:**
   ```sql
   exit;
   ```

### Option 2: Manual Setup

1. **Login to MySQL:**
   ```bash
   mysql -u root -p
   ```

2. **Create database:**
   ```sql
   CREATE DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. **Create user (optional):**
   ```sql
   CREATE USER 'ticket_user'@'localhost' IDENTIFIED BY 'your_secure_password';
   GRANT ALL PRIVILEGES ON ticket_ai.* TO 'ticket_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

4. **Exit:**
   ```sql
   exit;
   ```

### Option 3: Using MySQL Workbench

1. Open MySQL Workbench
2. Connect to your MySQL server
3. Click "Create Schema" button
4. Name it `ticket_ai`
5. Set charset to `utf8mb4` and collation to `utf8mb4_unicode_ci`
6. Click Apply

## Environment Configuration

1. **Copy env.example to .env:**
   ```bash
   cd backend
   cp env.example .env
   ```

2. **Edit .env file with your MySQL credentials:**
   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=ticket_ai
   ```

## Verify Connection

Run this Python script to test the connection:

```python
# backend/test_mysql.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "3306")
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "")
db_name = os.getenv("DB_NAME", "ticket_ai")

url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ MySQL connection successful!")
        print(f"Connected to: {db_name} on {db_host}:{db_port}")
except Exception as e:
    print("❌ MySQL connection failed!")
    print(f"Error: {e}")
```

Run it:
```bash
cd backend
python test_mysql.py
```

## Initialize Tables

The tables will be created automatically when you start the FastAPI server:

```bash
cd backend
python -m uvicorn main:app --reload
```

Or manually run:
```python
from models.ticket import init_db
init_db()
```

## Troubleshooting

### Connection Refused

**Problem:** `Can't connect to MySQL server on 'localhost'`

**Solutions:**
- Ensure MySQL is running: `sudo systemctl status mysql` (Linux) or check Services (Windows)
- Start MySQL: `sudo systemctl start mysql` (Linux) or `brew services start mysql` (macOS)

### Access Denied

**Problem:** `Access denied for user 'root'@'localhost'`

**Solutions:**
- Check password in `.env` file
- Reset root password if forgotten
- Ensure user has proper privileges

### Database Does Not Exist

**Problem:** `Unknown database 'ticket_ai'`

**Solution:**
- Run the setup script: `mysql -u root -p < backend/setup_mysql.sql`
- Or manually create: `CREATE DATABASE ticket_ai;`

### Character Set Issues

**Problem:** Emoji or special characters not saving

**Solution:**
- Ensure database uses `utf8mb4`:
  ```sql
  ALTER DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  ```

## Migration from SQLite

If you have existing SQLite data:

1. **Export SQLite data:**
   ```bash
   sqlite3 tickets.db .dump > sqlite_dump.sql
   ```

2. **Convert to MySQL format** (manual editing required)
   - Remove SQLite-specific syntax
   - Adjust data types if needed

3. **Import to MySQL:**
   ```bash
   mysql -u root -p ticket_ai < converted_dump.sql
   ```

Or use a migration tool like `pgloader` or write a Python script to copy data.

## Performance Tips

1. **Connection Pooling:** Already configured in `ticket.py`
   - `pool_pre_ping=True` - Verify connections
   - `pool_recycle=3600` - Recycle after 1 hour

2. **Indexes:** Already configured on:
   - `customer` column
   - `category` column
   - `id` (primary key)

3. **Enable Query Cache** (MySQL 5.7):
   ```sql
   SET GLOBAL query_cache_size = 1048576;
   ```

4. **Monitor Slow Queries:**
   ```sql
   SET GLOBAL slow_query_log = 'ON';
   SET GLOBAL long_query_time = 2;
   ```

## Security Best Practices

1. **Don't use root in production:**
   - Create dedicated user with limited privileges
   - Use strong passwords

2. **Secure .env file:**
   ```bash
   chmod 600 .env
   ```

3. **Use SSL for remote connections:**
   ```python
   engine = create_engine(
       DATABASE_URL,
       connect_args={"ssl": {"ssl_ca": "/path/to/ca.pem"}}
   )
   ```

4. **Regular backups:**
   ```bash
   mysqldump -u root -p ticket_ai > backup_$(date +%Y%m%d).sql
   ```

## Additional Resources

- [MySQL Documentation](https://dev.mysql.com/doc/)
- [SQLAlchemy MySQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)

