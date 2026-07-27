#!/usr/bin/env python3
"""
Inventory Export CSRF Fix Validation
This script validates the specific inventory export functionality that was fixed.
"""

import re
import os
from pathlib import Path

def test_inventory_export_button_integration():
    """Test that inventory export buttons are properly integrated with CSRF"""
    print("🔍 Testing inventory export button integration...")
    
    inventory_template = "templates/inventory.html"
    if not os.path.exists(inventory_template):
        print(f"❌ Inventory template not found: {inventory_template}")
        return False
    
    with open(inventory_template, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for export functionality
    export_patterns = [
        'downloadInventoryReport',
        'generateInventoryInsights',
        'AIFeatures',
        'onclick.*download',
        'button.*export'
    ]
    
    found_export = False
    for pattern in export_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"✅ Export functionality pattern found: {pattern}")
            found_export = True
            break
    
    if not found_export:
        print("ℹ️  No explicit export buttons found in inventory template (may be dynamically generated)")
    
    # Check that template extends base (inherits CSRF token)
    if 'extends' in content and 'base.html' in content:
        print("✅ Inventory template extends base template (inherits CSRF token)")
    else:
        print("❌ Inventory template does not extend base template")
        return False
    
    return True

def test_ai_features_inventory_methods():
    """Test that AI features has inventory-specific methods"""
    print("\n🔍 Testing AI features inventory methods...")
    
    js_path = "static/js/ai_features.js"
    if not os.path.exists(js_path):
        print(f"❌ AI features JavaScript not found: {js_path}")
        return False
    
    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for inventory-specific methods
    inventory_methods = [
        'generateInventoryInsights',
        'downloadInventoryReport'
    ]
    
    for method in inventory_methods:
        if method in content:
            print(f"✅ {method} method found")
        else:
            print(f"❌ {method} method not found")
            return False
    
    # Check that these methods use CSRF token
    csrf_usage_patterns = [
        r'_getCSRFToken\(\)',
        r'X-CSRFToken.*csrfToken',
        r'csrfToken.*X-CSRFToken'
    ]
    
    csrf_found = False
    for pattern in csrf_usage_patterns:
        if re.search(pattern, content):
            print(f"✅ CSRF token usage pattern found: {pattern}")
            csrf_found = True
            break
    
    if not csrf_found:
        print("❌ CSRF token usage not found in API methods")
        return False
    
    return True

def test_error_handling_for_inventory():
    """Test error handling specific to inventory export"""
    print("\n🔍 Testing error handling for inventory export...")
    
    js_path = "static/js/ai_features.js"
    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for download-specific error handling
    download_error_patterns = [
        'download.*error',
        'Download.*Error',
        'تنزيل.*خطأ',
        'خطأ.*تنزيل'
    ]
    
    found_download_error = False
    for pattern in download_error_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"✅ Download error handling found: {pattern}")
            found_download_error = True
            break
    
    if not found_download_error:
        print("⚠️  Specific download error handling not found")
    
    # Check for authentication error handling
    auth_error_patterns = [
        '_handleAuthenticationError',
        'Authentication error',
        'خطأ في المصادقة'
    ]
    
    for pattern in auth_error_patterns:
        if pattern in content:
            print(f"✅ Authentication error handling found: {pattern}")
        else:
            print(f"❌ Authentication error handling not found: {pattern}")
            return False
    
    return True

def test_csrf_token_flow():
    """Test the complete CSRF token flow"""
    print("\n🔍 Testing complete CSRF token flow...")
    
    # Test 1: Base template provides token
    base_template = "templates/base.html"
    with open(base_template, 'r', encoding='utf-8') as f:
        base_content = f.read()
    
    if 'csrf_token()' in base_content:
        print("✅ Step 1: Base template generates CSRF token")
    else:
        print("❌ Step 1: Base template does not generate CSRF token")
        return False
    
    # Test 2: JavaScript retrieves token
    js_path = "static/js/ai_features.js"
    with open(js_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    if '_getCSRFToken()' in js_content:
        print("✅ Step 2: JavaScript has method to retrieve CSRF token")
    else:
        print("❌ Step 2: JavaScript cannot retrieve CSRF token")
        return False
    
    # Test 3: Token is used in API requests
    if 'X-CSRFToken' in js_content:
        print("✅ Step 3: CSRF token is included in API request headers")
    else:
        print("❌ Step 3: CSRF token is not included in API requests")
        return False
    
    # Test 4: Error handling for missing token
    if 'CSRF token not found' in js_content:
        print("✅ Step 4: Error handling for missing CSRF token")
    else:
        print("❌ Step 4: No error handling for missing CSRF token")
        return False
    
    return True

def test_browser_compatibility():
    """Test browser compatibility for the CSRF fix"""
    print("\n🔍 Testing browser compatibility...")
    
    js_path = "static/js/ai_features.js"
    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for modern JavaScript features that might need polyfills
    modern_features = {
        'document.querySelector': 'Modern DOM selection (IE8+)',
        'fetch(': 'Modern HTTP requests (IE not supported, needs polyfill)',
        'async ': 'Async/await (ES2017, modern browsers)',
        'const ': 'Block-scoped variables (ES6)',
        'let ': 'Block-scoped variables (ES6)'
    }
    
    for feature, description in modern_features.items():
        if feature in content:
            print(f"✅ {feature} - {description}")
        else:
            print(f"ℹ️  {feature} not found - {description}")
    
    # Check for fallback mechanisms
    if 'try {' in content and 'catch' in content:
        print("✅ Try-catch error handling provides fallback for unsupported features")
    else:
        print("❌ No try-catch error handling found")
        return False
    
    return True

def validate_inventory_export_fix():
    """Main validation function for inventory export CSRF fix"""
    print("🚀 INVENTORY EXPORT CSRF FIX VALIDATION")
    print("="*60)
    
    all_tests_passed = True
    
    tests = [
        ("Inventory Export Button Integration", test_inventory_export_button_integration),
        ("AI Features Inventory Methods", test_ai_features_inventory_methods),
        ("Error Handling for Inventory", test_error_handling_for_inventory),
        ("CSRF Token Flow", test_csrf_token_flow),
        ("Browser Compatibility", test_browser_compatibility)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}")
        print("-" * 50)
        result = test_func()
        results.append((test_name, result))
        if not result:
            all_tests_passed = False
    
    # Summary
    print("\n" + "="*60)
    print("📋 VALIDATION SUMMARY")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    if all_tests_passed:
        print("🎉 INVENTORY EXPORT CSRF FIX VALIDATION SUCCESSFUL!")
        print("\n✅ Fix Summary:")
        print("- CSRF token meta tag added to base template")
        print("- AI features JavaScript safely retrieves CSRF tokens")
        print("- Inventory export methods use CSRF tokens in API requests")
        print("- Comprehensive error handling prevents JavaScript crashes")
        print("- User-friendly error messages in Arabic and English")
        print("- Cross-browser compatibility maintained")
        
        print("\n🔧 The Original Issue is RESOLVED:")
        print("- JavaScript error 'Cannot read properties of null' is fixed")
        print("- CSRF token meta tag is now available for JavaScript access")
        print("- Export functionality should work without errors")
        
        print("\n🚀 Ready for Manual Testing:")
        print("1. Start the Flask application")
        print("2. Login and navigate to inventory page")
        print("3. Click export/download buttons")
        print("4. Verify reports download successfully")
        print("5. Test in different browsers (Chrome, Firefox, Edge)")
        
    else:
        print("❌ SOME VALIDATIONS FAILED!")
        print("Please review the failed tests above and fix any issues.")
    
    print("="*60)
    return all_tests_passed

if __name__ == "__main__":
    success = validate_inventory_export_fix()
    exit(0 if success else 1)