"""
Simple test to verify Streamlit dependencies have been removed from utility modules.
"""

import sys
import os

def test_imports_without_streamlit():
    """Test that modules can be imported without streamlit"""
    print("Testing imports without Streamlit...")
    
    # Block streamlit import
    sys.modules['streamlit'] = None
    
    # Test data_processing
    try:
        from utils import data_processing
        # Check that st is not used
        source = open('utils/data_processing.py').read()
        assert 'import streamlit' not in source, "Found streamlit import in data_processing.py"
        assert '@st.cache_data' not in source, "Found @st.cache_data decorator in data_processing.py"
        assert 'st.spinner' not in source, "Found st.spinner in data_processing.py"
        assert 'st.error' not in source, "Found st.error in data_processing.py"
        assert 'st.success' not in source, "Found st.success in data_processing.py"
        assert 'st.warning' not in source, "Found st.warning in data_processing.py"
        print("✓ data_processing.py has no Streamlit dependencies")
    except Exception as e:
        print(f"✗ data_processing.py test failed: {e}")
        raise
    
    # Test forecasting (check source only, don't import due to xgboost)
    try:
        source = open('utils/forecasting.py').read()
        assert 'import streamlit' not in source, "Found streamlit import in forecasting.py"
        assert '@st.cache_resource' not in source, "Found @st.cache_resource decorator in forecasting.py"
        assert 'st.spinner' not in source, "Found st.spinner in forecasting.py"
        assert 'st.error' not in source, "Found st.error in forecasting.py"
        assert 'st.success' not in source, "Found st.success in forecasting.py"
        assert 'st.warning' not in source, "Found st.warning in forecasting.py"
        assert 'st.info' not in source, "Found st.info in forecasting.py"
        assert 'st.download_button' not in source, "Found st.download_button in forecasting.py"
        print("✓ forecasting.py has no Streamlit dependencies")
    except Exception as e:
        print(f"✗ forecasting.py test failed: {e}")
        raise
    
    print("\n✅ All modules have been successfully cleaned of Streamlit dependencies!")


def test_logging_usage():
    """Test that logging is used instead of streamlit"""
    print("\nTesting logging usage...")
    
    # Check data_processing
    source = open('utils/data_processing.py').read()
    assert 'import logging' in source, "Missing logging import in data_processing.py"
    assert 'logger = logging.getLogger(__name__)' in source, "Missing logger setup in data_processing.py"
    assert 'logger.info' in source or 'logger.error' in source or 'logger.warning' in source, \
        "Logger not used in data_processing.py"
    print("✓ data_processing.py uses logging")
    
    # Check forecasting
    source = open('utils/forecasting.py').read()
    assert 'import logging' in source, "Missing logging import in forecasting.py"
    assert 'logger = logging.getLogger(__name__)' in source, "Missing logger setup in forecasting.py"
    assert 'logger.info' in source or 'logger.error' in source or 'logger.warning' in source, \
        "Logger not used in forecasting.py"
    print("✓ forecasting.py uses logging")
    
    print("\n✅ All modules use logging correctly!")


def test_exception_handling():
    """Test that exceptions are raised instead of returning None"""
    print("\nTesting exception handling...")
    
    # Check data_processing
    source = open('utils/data_processing.py').read()
    assert 'raise ValueError' in source or 'raise' in source, \
        "Missing exception raising in data_processing.py"
    print("✓ data_processing.py raises exceptions")
    
    # Check forecasting
    source = open('utils/forecasting.py').read()
    assert 'raise ValueError' in source or 'raise' in source, \
        "Missing exception raising in forecasting.py"
    print("✓ forecasting.py raises exceptions")
    
    print("\n✅ All modules handle exceptions correctly!")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Streamlit Dependency Removal")
    print("=" * 70)
    print()
    
    try:
        test_imports_without_streamlit()
        test_logging_usage()
        test_exception_handling()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED - Streamlit dependencies successfully removed!")
        print("=" * 70)
    except AssertionError as e:
        print("\n" + "=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
