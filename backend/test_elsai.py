"""Test script to diagnose ElsAI agent initialization."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=== ElsAI Agent Diagnostic ===")
print()

# Check CSV file
csv_path = Path(__file__).parent / "data" / "ticket_routing.csv"
print(f"1. CSV File Check:")
print(f"   Path: {csv_path}")
print(f"   Exists: {csv_path.exists()}")
print(f"   Absolute: {csv_path.absolute()}")
print()

# Check environment variables
print("2. Environment Variables:")
print(f"   ELSAI_MODEL: {os.getenv('ELSAI_MODEL', 'NOT SET (default: gpt-3.5-turbo)')}")
print(f"   ELSAI_AGENT_TYPE: {os.getenv('ELSAI_AGENT_TYPE', 'NOT SET (default: openai-functions)')}")
openai_key = os.getenv('OPENAI_API_KEY')
print(f"   OPENAI_API_KEY: {'SET (' + openai_key[:10] + '...)' if openai_key else 'NOT SET'}")
print()

# Check package imports
print("3. Package Imports:")
try:
    from elsai_nli.natural_language_interface import CSVAgentHandler
    print("   ✓ CSVAgentHandler imported")
except ImportError as e:
    print(f"   ✗ Failed to import CSVAgentHandler: {e}")
    sys.exit(1)

try:
    from langchain_community.chat_models import ChatOpenAI
    print("   ✓ ChatOpenAI from langchain_community imported")
except ImportError:
    try:
        from langchain.chat_models import ChatOpenAI
        print("   ✓ ChatOpenAI from langchain.chat_models imported")
    except ImportError:
        print("   ✗ Failed to import ChatOpenAI")
        sys.exit(1)
print()

# Try to initialize agent
if not csv_path.exists():
    print("4. Agent Initialization:")
    print("   ✗ Cannot initialize - CSV file not found")
    sys.exit(1)

if not openai_key:
    print("4. Agent Initialization:")
    print("   ✗ Cannot initialize - OPENAI_API_KEY not set")
    sys.exit(1)

print("4. Agent Initialization:")
try:
    model_name = os.getenv("ELSAI_MODEL", "gpt-3.5-turbo")
    agent_type = os.getenv("ELSAI_AGENT_TYPE", "openai-functions")
    
    print(f"   Creating ChatOpenAI model...")
    print(f"   Model: {model_name}")
    model_instance = ChatOpenAI(
        model=model_name,
        temperature=0
    )
    print("   ✓ ChatOpenAI model created")
    
    print(f"   Creating CSVAgentHandler...")
    print(f"   CSV: {csv_path}")
    print(f"   Agent Type: {agent_type}")
    
    agent = CSVAgentHandler(
        csv_files=str(csv_path),
        model=model_instance,
        agent_type=agent_type,
        verbose=True
    )
    print("   ✓ Agent initialized successfully!")
    
    # Test a simple question
    print()
    print("5. Test Classification:")
    test_text = "I need help with my billing"
    print(f"   Test text: '{test_text}'")
    response = agent.ask_question(
        f"Based on the CSV routing rules, classify this ticket message into one category: '{test_text}'. Respond with only the category name (billing, technical, delivery, or general)."
    )
    print(f"   Response: {response}")
    print()
    print("✓ All tests passed!")
    
except Exception as e:
    print(f"   ✗ Failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
