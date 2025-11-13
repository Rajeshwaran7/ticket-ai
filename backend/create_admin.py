"""Script to create an admin user for testing."""
import os
from dotenv import load_dotenv
from models.user import User, UserRole
from models.ticket import SessionLocal

load_dotenv()

def create_admin_user():
    """Create a default admin user."""
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print("❌ Admin user already exists!")
            print(f"   Username: admin")
            return
        
        # Create admin user
        admin = User(
            email="admin@ticketai.com",
            username="admin",
            hashed_password=User.hash_password("admin123"),
            full_name="Admin User",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        
        print("✅ Admin user created successfully!")
        print(f"   Email: admin@ticketai.com")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print(f"   Role: admin")
        print("\n⚠️  Please change the password after first login!")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()


def create_test_customer():
    """Create a test customer user."""
    db = SessionLocal()
    
    try:
        # Check if customer already exists
        existing_customer = db.query(User).filter(User.username == "customer").first()
        if existing_customer:
            print("❌ Test customer already exists!")
            return
        
        # Create customer user
        customer = User(
            email="customer@test.com",
            username="customer",
            hashed_password=User.hash_password("customer123"),
            full_name="Test Customer",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        
        db.add(customer)
        db.commit()
        
        print("✅ Test customer created successfully!")
        print(f"   Email: customer@test.com")
        print(f"   Username: customer")
        print(f"   Password: customer123")
        print(f"   Role: customer")
        
    except Exception as e:
        print(f"❌ Error creating customer: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("Creating test users...")
    print("-" * 50)
    create_admin_user()
    print()
    create_test_customer()
    print("-" * 50)
    print("Done!")

