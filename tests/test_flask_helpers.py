"""
Simple test script to verify flask_helpers functionality.
"""

import pandas as pd
import os
from utils.flask_helpers import (
    allowed_file,
    serialize_dataframe,
    deserialize_dataframe,
    cleanup_upload
)


def test_allowed_file():
    """Test file extension validation"""
    print("Testing allowed_file...")
    
    # Valid extensions
    assert allowed_file("test.xlsx") == True
    assert allowed_file("test.xls") == True
    assert allowed_file("data.XLSX") == True  # Case insensitive
    
    # Invalid extensions
    assert allowed_file("test.csv") == False
    assert allowed_file("test.txt") == False
    assert allowed_file("test") == False
    assert allowed_file("") == False
    assert allowed_file(None) == False
    
    print("✓ allowed_file tests passed")


def test_dataframe_serialization():
    """Test DataFrame serialization and deserialization"""
    print("\nTesting DataFrame serialization...")
    
    # Create test DataFrame
    df_original = pd.DataFrame({
        'A': [1, 2, 3],
        'B': ['x', 'y', 'z'],
        'C': [1.1, 2.2, 3.3]
    })
    
    # Serialize
    serialized = serialize_dataframe(df_original)
    assert isinstance(serialized, str)
    assert len(serialized) > 0
    print(f"  Serialized length: {len(serialized)} characters")
    
    # Deserialize
    df_restored = deserialize_dataframe(serialized)
    assert isinstance(df_restored, pd.DataFrame)
    
    # Verify data integrity
    pd.testing.assert_frame_equal(df_original, df_restored)
    print("✓ DataFrame serialization tests passed")


def test_serialization_errors():
    """Test error handling in serialization"""
    print("\nTesting serialization error handling...")
    
    # Test None DataFrame
    try:
        serialize_dataframe(None)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Cannot serialize None" in str(e)
        print("✓ None DataFrame error handled correctly")
    
    # Test empty string deserialization
    try:
        deserialize_dataframe("")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Cannot deserialize empty" in str(e)
        print("✓ Empty string error handled correctly")
    
    # Test invalid data deserialization
    try:
        deserialize_dataframe("invalid_base64_data")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Failed to deserialize" in str(e)
        print("✓ Invalid data error handled correctly")


def test_cleanup_upload():
    """Test file cleanup functionality"""
    print("\nTesting cleanup_upload...")
    
    # Create a temporary test file
    test_file = "test_temp_file.txt"
    with open(test_file, 'w') as f:
        f.write("test content")
    
    assert os.path.exists(test_file)
    
    # Cleanup the file
    cleanup_upload(test_file)
    assert not os.path.exists(test_file)
    print("✓ File cleanup successful")
    
    # Test cleanup of non-existent file (should not raise error)
    cleanup_upload("non_existent_file.txt")
    print("✓ Non-existent file cleanup handled gracefully")
    
    # Test cleanup with None/empty path
    cleanup_upload(None)
    cleanup_upload("")
    print("✓ None/empty path cleanup handled gracefully")


if __name__ == "__main__":
    print("Running flask_helpers tests...\n")
    print("=" * 50)
    
    test_allowed_file()
    test_dataframe_serialization()
    test_serialization_errors()
    test_cleanup_upload()
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")
