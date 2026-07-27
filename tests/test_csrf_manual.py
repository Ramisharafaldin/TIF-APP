"""
Manual test to verify CSRF token presence by starting Flask app and making requests.
"""

import requests
import sys
import os
from bs4 import BeautifulSoup

def test_csrf_token_manually():
    """Test CSRF token presence by making HTTP requests to running Flask app"""
    
    # Base URL - assuming Flask app is running on localhost:5000
    base_url = "http://localhost:5000"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    try:
        # First, try to access login page to get session
        login_response = session.get(f"{base_url}/login")
        if login_response.status_code != 200:
            print(f"❌ Cannot access login page. Status: {login_response.status_code}")
            print("Make sure Flask app is running with: python flask_app.py")
            return False
        
        # Try to login (you may need to adjust credentials)
        login_data = {
            'username': 'admin',  # Adjust as needed
            'password': 'admin123'  # Adjust as needed
        }
        
        login_post = session.post(f"{base_url}/login", data=login_data)
        
        # Test pages that should have CSRF tokens
        pages_to_test = ['/dashboard', '/inventory', '/transfers', '/forecasting']
        
        for page in pages_to_test:
            try:
                response = session.get(f"{base_url}{page}")
                if response.status_code == 200:
                    # Parse HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find CSRF token meta tag
                    csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                    
                    if csrf_meta:
                        token_content = csrf_meta.get('content')
                        if token_content and token_content.strip():
                            print(f"✅ {page}: CSRF token found - {token_content[:20]}...")
                        else:
                            print(f"❌ {page}: CSRF token meta tag found but content is empty")
                    else:
                        print(f"❌ {page}: CSRF token meta tag not found")
                        
                    # Check for AI features script
                    if 'ai_features.js' in response.text:
                        print(f"✅ {page}: AI features script included")
                    else:
                        print(f"❌ {page}: AI features script not found")
                        
                else:
                    print(f"❌ {page}: Cannot access page. Status: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ {page}: Error accessing page - {e}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask app. Make sure it's running on localhost:5000")
        print("Start the app with: python flask_app.py")
        return False
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False


if __name__ == "__main__":
    print("Testing CSRF token presence on AI-enabled pages...")
    print("=" * 60)
    
    success = test_csrf_token_manually()
    
    if success:
        print("=" * 60)
        print("✅ Manual CSRF token test completed!")
    else:
        print("=" * 60)
        print("❌ Manual CSRF token test failed!")
        sys.exit(1)