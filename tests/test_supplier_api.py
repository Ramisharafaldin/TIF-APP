#!/usr/bin/env python3
"""
Test script for the new supplier distribution API endpoint.
"""

import requests
import json
import time

def test_supplier_api():
    """Test the supplier distribution API endpoint."""
    
    # Wait a moment for the server to fully start
    time.sleep(2)
    
    base_url = "http://localhost:5000"
    
    print("Testing Supplier Distribution API...")
    print("=" * 50)
    
    try:
        # Test the API endpoint
        response = requests.get(f"{base_url}/api/supplier-distribution")
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nAPI Response Structure:")
            print(f"- Success: {data.get('success', 'N/A')}")
            print(f"- Total Value: {data.get('totalValue', 'N/A')}")
            print(f"- Last Updated: {data.get('lastUpdated', 'N/A')}")
            print(f"- Number of Suppliers: {len(data.get('suppliers', []))}")
            
            if data.get('suppliers'):
                print("\nTop 3 Suppliers:")
                for i, supplier in enumerate(data['suppliers'][:3]):
                    print(f"  {i+1}. {supplier.get('name', 'N/A')} - {supplier.get('percentage', 0):.1f}%")
            
            print("\n✅ API endpoint is working correctly!")
            
        elif response.status_code == 302:
            print("\n⚠️  Redirected (likely to login page)")
            print("This is expected if not logged in")
            
        else:
            print(f"\n❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to Flask server")
        print("Make sure the Flask app is running on http://localhost:5000")
        
    except Exception as e:
        print(f"\n❌ Error testing API: {e}")

if __name__ == "__main__":
    test_supplier_api()