# MySQL Migration Summary

## ✅ Changes Made

### 1. **Updated Dependencies** (`backend/requirements.txt`)
- ✅ Added `pymysql==1.1.0` - MySQL database driver
- ✅ Added `cryptography==41.0.7` - Required for PyMySQL secure connections

### 2. **Updated Database Model** (`backend/models/ticket.py`)
- ✅ Added MySQL-specific column types with length constraints:
  - `customer`: `String(200)` instead of generic `String`
  - `message`: `Text` for long text content
  - `category`: `String(50)`
  - `assigned_team`: `String(100)`
  - `status`: `String(50)`
  - `confidence`: `String(10)`
- ✅ Created `get_database_url()` function to build MySQL connection string from env vars
- ✅ Updated engine configuration with MySQL best practices:
  - `pool_pre_ping=True` - Verify connections before using
  - `pool_recycle=3600` - Recycle connections after 1 hour
  - `echo=False` - Disable SQL query logging (set to True for debugging)
- ✅ Removed SQLite-specific `check_same_thread` parameter

### 3. **Updated Environment Configuration** (`backend/env.example`)
- ✅ Added MySQL database configuration variables:
  - `DB_HOST` - Database host (default: localhost)
  - `DB_PORT` - Database port (default: 3306)
  - `DB_USER` - Database username
  - `DB_PASSWORD` - Database password
  - `DB_NAME` - Database name (default: ticket_ai)
- ✅ Cleaned up SMTP configuration (removed hardcoded credentials)

### 4. **Created Setup Files**
- ✅ `backend/setup_mysql.sql` - SQL script to create database
- ✅ `backend/MYSQL_SETUP.md` - Comprehensive MySQL setup guide
- ✅ `backend/test_mysql.py` - Connection test script

### 5. **Updated Documentation** (`README.md`)
- ✅ Updated prerequisites to include MySQL
- ✅ Added MySQL setup step in backend setup instructions
- ✅ Updated tech stack section
- ✅ Added reference to MYSQL_SETUP.md

## 📋 Migration Steps for Users

### For New Installations:

1. **Install MySQL** (if not already installed)
   - Windows: Download from https://dev.mysql.com/downloads/installer/
   - macOS: `brew install mysql`
   - Linux: `sudo apt install mysql-server`

2. **Create Database:**
   ```bash
   mysql -u root -p < backend/setup_mysql.sql
   ```

3. **Install Python Dependencies:**
   ```bash
   cd backend
   pip install pymysql cryptography
   # Or reinstall all
   pip install -r requirements.txt
   ```

4. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your MySQL credentials
   ```

5. **Test Connection:**
   ```bash
   python test_mysql.py
   ```

6. **Start Server:**
   ```bash
   uvicorn main:app --reload
   ```
   Tables will be created automatically on first run.

### For Existing SQLite Installations:

If you have existing data in SQLite that you want to migrate:

1. **Backup SQLite data:**
   ```bash
   cp tickets.db tickets.db.backup
   ```

2. **Export data** (manual process):
   - Option A: Write a Python script to copy data
   - Option B: Export to CSV and import to MySQL
   - Option C: Use a migration tool

3. **Follow new installation steps above**

## 🔧 Key Differences: SQLite vs MySQL

| Feature | SQLite | MySQL |
|---------|--------|-------|
| **Connection String** | `sqlite:///./tickets.db` | `mysql+pymysql://user:pass@host:port/db` |
| **Column Types** | Generic `String` | Length-constrained `String(200)` |
| **Text Fields** | `String` | `Text` for long content |
| **Connection Args** | `check_same_thread=False` | `pool_pre_ping=True`, `pool_recycle=3600` |
| **Setup** | Automatic file creation | Requires database creation |
| **Concurrent Access** | Limited | Excellent |
| **Production Ready** | No | Yes |

## ⚙️ Configuration Options

### Environment Variables

```env
# MySQL Configuration
DB_HOST=localhost          # Database server host
DB_PORT=3306              # MySQL port (default: 3306)
DB_USER=root              # Database username
DB_PASSWORD=your_password # Database password
DB_NAME=ticket_ai         # Database name
```

### Connection Pool Settings

In `backend/models/ticket.py`:

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Verify connections before using
    pool_recycle=3600,       # Recycle connections after 1 hour
    pool_size=5,             # Number of connections to maintain (default: 5)
    max_overflow=10,         # Max overflow connections (default: 10)
    echo=False               # Set to True for SQL query logging
)
```

## 🐛 Troubleshooting

### Connection Issues

**Error:** `Can't connect to MySQL server`
- ✅ Check MySQL is running: `sudo systemctl status mysql`
- ✅ Verify host and port in `.env`

**Error:** `Access denied for user`
- ✅ Check username and password in `.env`
- ✅ Ensure user has privileges: `GRANT ALL PRIVILEGES ON ticket_ai.* TO 'user'@'localhost';`

**Error:** `Unknown database 'ticket_ai'`
- ✅ Create database: `mysql -u root -p < backend/setup_mysql.sql`

### Data Type Issues

**Error:** Column length too short
- ✅ Adjust column lengths in `ticket.py` if needed
- ✅ Current limits: customer(200), category(50), assigned_team(100), status(50)

**Error:** Emoji/Unicode issues
- ✅ Ensure database uses `utf8mb4`: 
  ```sql
  ALTER DATABASE ticket_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  ```

## 📊 Performance Benefits

MySQL provides several advantages over SQLite:

1. **Concurrent Access** - Multiple users can read/write simultaneously
2. **Connection Pooling** - Reuse connections for better performance
3. **Query Optimization** - Advanced query optimizer
4. **Indexing** - Better index support for large datasets
5. **Scalability** - Can handle millions of records
6. **Production Ready** - Industry standard for web applications

## 🔒 Security Considerations

1. **Don't commit .env file** - Add to `.gitignore`
2. **Use strong passwords** - For MySQL users
3. **Create dedicated user** - Don't use root in production
4. **Limit privileges** - Grant only necessary permissions
5. **Use SSL** - For remote connections
6. **Regular backups** - Use `mysqldump`

## 📝 Next Steps

1. ✅ Install MySQL
2. ✅ Run setup script
3. ✅ Configure .env
4. ✅ Test connection
5. ✅ Start server
6. ✅ Verify tables created
7. ✅ Test ticket creation

## 🆘 Support

For detailed setup instructions, see:
- [MYSQL_SETUP.md](backend/MYSQL_SETUP.md) - Complete MySQL setup guide
- [README.md](README.md) - Main project documentation

For MySQL-specific issues:
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [SQLAlchemy MySQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)

