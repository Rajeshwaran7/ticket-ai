"""Test MySQL database connection."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def test_connection():
    """Test MySQL database connection."""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "ticket_ai")

    url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    print("Testing MySQL connection...")
    print(f"Host: {db_host}:{db_port}")
    print(f"Database: {db_name}")
    print(f"User: {db_user}")
    print("-" * 50)

    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            
            print("✅ MySQL connection successful!")
            print(f"MySQL Version: {version}")
            
            # Test database
            result = conn.execute(text(f"SELECT DATABASE()"))
            current_db = result.fetchone()[0]
            print(f"Current Database: {current_db}")
            
            # Check if tables exist
            result = conn.execute(text("SHOW TABLES"))
            tables = result.fetchall()
            
            if tables:
                print(f"\nExisting tables ({len(tables)}):")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("\nNo tables found. Run the FastAPI server to create tables.")
            
            return True
            
    except Exception as e:
        print("❌ MySQL connection failed!")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure MySQL is running")
        print("2. Check credentials in .env file")
        print("3. Verify database 'ticket_ai' exists")
        print("4. Run: mysql -u root -p < backend/setup_mysql.sql")
        return False


if __name__ == "__main__":
    test_connection()

