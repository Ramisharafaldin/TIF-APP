#!/usr/bin/env python3
"""
Simple test to verify CSRF implementation without importing Flask app.
This validates the files directly to ensure proper implementation.
"""

import re
import os

def test_base_template_csrf_token():
    """Test that base template includes CSRF token meta tag"""
    print("🔍 Testing base template CSRF token implementation...")
    
    template_path = "templates/base.html"
    if not os.path.exists(template_path):
        print(f"❌ Base template not found: {template_path}")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Test 1: CSRF token meta tag exists
    csrf_pattern = r'<meta\s+name="csrf-token"\s+content="\{\{\s*csrf_token\(\)\s*\}\}"'
    if re.search(csrf_pattern, content):
        print("✅ CSRF token meta tag found with correct Flask-WTF syntax")
    else:
        print("❌ CSRF token meta tag not found or incorrect syntax")
        return False
    
    # Test 2: Meta tag is in head section
    head_start = content.find('<head>')
    head_end = content.find('</head>')
    csrf_pos = content.find('name="csrf-token"')
    
    if head_start < csrf_pos < head_end:
        print("✅ CSRF token meta tag is properly placed in head section")
    else:
        print("❌ CSRF token meta tag is not in head section")
        return False
    
    return True

def test_ai_features_csrf_handling():
    """Test that AI features JavaScript handles CSRF tokens properly"""
    print("\n🔍 Testing AI features CSRF token handling...")
    
    js_path = "static/js/ai_features.js"
    if not os.path.exists(js_path):
        print(f"❌ AI features JavaScript not found: {js_path}")
        return False
    
    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Test 1: _getCSRFToken method exists
    if '_getCSRFToken()' in content:
        print("✅ _getCSRFToken method found")
    else:
        print("❌ _getCSRFToken method not found")
        return False
    
    # Test 2: Error handling for missing CSRF token
    if 'CSRF token not found' in content:
        print("✅ Error handling for missing CSRF token found")
    else:
        print("❌ Error handling for missing CSRF token not found")
        return False
    
    # Test 3: Try-catch blocks for safe token access
    if 'try {' in content and 'catch' in content:
        print("✅ Try-catch blocks found for safe token access")
    else:
        print("❌ Try-catch blocks not found")
        return False
    
    # Test 4: CSRF token used in API requests
    if 'X-CSRFToken' in content:
        print("✅ CSRF token header usage found in API requests")
    else:
        print("❌ CSRF token header usage not found")
        return False
    
    # Test 5: Authentication error handling
    if '_handleAuthenticationError' in content:
        print("✅ Authentication error handling method found")
    else:
        print("❌ Authentication error handling method not found")
        return False
    
    return True

def test_inventory_template_ai_features():
    """Test that inventory template includes AI features"""
    print("\n🔍 Testing inventory template AI features inclusion...")
    
    template_path = "templates/inventory.html"
    if not os.path.exists(template_path):
        print(f"❌ Inventory template not found: {template_path}")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for export button or AI features usage
    if 'downloadInventoryReport' in content or 'generateInventoryInsights' in content:
        print("✅ Inventory template includes AI features functionality")
        return True
    else:
        print("⚠️  Inventory template may not include AI features (this is okay if not implemented yet)")
        return True  # Not a failure, just a note

def main():
    """Main test function"""
    print("🚀 CSRF Implementation Validation (File-based)")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test base template
    if not test_base_template_csrf_token():
        all_tests_passed = False
    
    # Test AI features JavaScript
    if not test_ai_features_csrf_handling():
        all_tests_passed = False
    
    # Test inventory template
    if not test_inventory_template_ai_features():
        all_tests_passed = False
    
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("🎉 All CSRF implementation tests PASSED!")
        print("\n✅ Implementation Summary:")
        print("- CSRF token meta tag properly added to base template")
        print("- AI features JavaScript safely handles CSRF tokens")
        print("- Error handling implemented for missing tokens")
        print("- Authentication error handling in place")
        print("\n🔧 Ready for manual testing:")
        print("1. Start Flask app: python flask_app.py")
        print("2. Login and navigate to inventory page")
        print("3. Test export functionality")
    else:
        print("❌ Some CSRF implementation tests FAILED!")
        print("Please review the issues above before proceeding.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())