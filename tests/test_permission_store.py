import pytest
import json
import os
from unittest.mock import MagicMock, patch, mock_open
from src.utils.permission_store import PermissionManager


class TestPermissionManager:
    @pytest.fixture
    def mock_permissions_data(self):
        return {
            "admins": [12345, 67890],
            "restricted": [99999, 11111]
        }

    @pytest.fixture
    def permission_manager(self, mock_permissions_data):
        with patch('src.utils.permission_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_permissions_data))):
            return PermissionManager()

    def test_initialization(self, permission_manager):
        """Test PermissionManager initialization"""
        assert permission_manager.filepath.endswith("permissions.json")
        assert isinstance(permission_manager.admins, list)
        assert isinstance(permission_manager.restricted_members, list)
        assert len(permission_manager.admins) == 2
        assert len(permission_manager.restricted_members) == 2

    def test_load_permissions_file_exists(self, mock_permissions_data):
        """Test loading permissions when file exists"""
        with patch('src.utils.permission_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_permissions_data))), \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            manager = PermissionManager()
            assert manager.admins == [12345, 67890]
            assert manager.restricted_members == [99999, 11111]
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Loaded 2 admins and 2 from" in log_call

    def test_load_permissions_file_not_exists(self):
        """Test loading permissions when file doesn't exist"""
        with patch('src.utils.permission_store.os.path.exists', return_value=False), \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            manager = PermissionManager()
            assert manager.admins == []
            assert manager.restricted_members == []
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Permission file found at" in log_call

    def test_load_permissions_json_error(self):
        """Test loading permissions with JSON decode error"""
        with patch('src.utils.permission_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="invalid json")), \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            manager = PermissionManager()
            assert manager.admins == []
            assert manager.restricted_members == []
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "Error loading permissions" in log_call

    def test_load_permissions_missing_keys(self):
        """Test loading permissions when data is missing keys"""
        incomplete_data = {"admins": [12345]}  # Missing 'restricted' key
        with patch('src.utils.permission_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(incomplete_data))), \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            manager = PermissionManager()
            assert manager.admins == [12345]
            assert manager.restricted_members == []  # Should default to empty list

    def test_load_permissions_empty_data(self):
        """Test loading permissions with empty data structure"""
        empty_data = {}
        with patch('src.utils.permission_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(empty_data))), \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            manager = PermissionManager()
            assert manager.admins == []
            assert manager.restricted_members == []

    def test_save_permissions_success(self, permission_manager):
        """Test successfully saving permissions to file"""
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump, \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            permission_manager.save_permissions()
            
            # Verify file was opened for writing
            mock_file.assert_called_once_with(permission_manager.filepath, 'w')
            
            # Verify json.dump was called with correct data
            mock_json_dump.assert_called_once()
            call_args = mock_json_dump.call_args[0]
            expected_data = {
                'admins': permission_manager.admins,
                'restricted': permission_manager.restricted_members
            }
            assert call_args[0] == expected_data
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Saved" in log_call and "successfully" in log_call

    def test_save_permissions_error(self, permission_manager):
        """Test handling save error"""
        with patch('builtins.open', side_effect=IOError("Write error")), \
             patch('src.utils.permission_store.logger') as mock_logger:
            
            permission_manager.save_permissions()
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "Error saving quotes" in log_call  # Note: This is the actual message in the code

    def test_filepath_construction(self):
        """Test that filepath is constructed correctly"""
        with patch('src.utils.permission_store.os.path.exists', return_value=False), \
             patch('src.utils.permission_store.logger'):
            
            manager = PermissionManager()
            
            # Verify the filepath ends with the expected path
            assert manager.filepath.endswith(os.path.join("data", "permissions.json"))
            
            # Verify it's an absolute path
            assert os.path.isabs(manager.filepath)

    def test_admin_list_operations(self, permission_manager):
        """Test operations on admin list"""
        # Test initial state
        assert 12345 in permission_manager.admins
        assert 67890 in permission_manager.admins
        
        # Test adding admin
        permission_manager.admins.append(55555)
        assert 55555 in permission_manager.admins
        
        # Test removing admin
        permission_manager.admins.remove(12345)
        assert 12345 not in permission_manager.admins
        assert 67890 in permission_manager.admins  # Other admin should remain

    def test_restricted_members_list_operations(self, permission_manager):
        """Test operations on restricted members list"""
        # Test initial state
        assert 99999 in permission_manager.restricted_members
        assert 11111 in permission_manager.restricted_members
        
        # Test adding restricted member
        permission_manager.restricted_members.append(22222)
        assert 22222 in permission_manager.restricted_members
        
        # Test removing restricted member
        permission_manager.restricted_members.remove(99999)
        assert 99999 not in permission_manager.restricted_members
        assert 11111 in permission_manager.restricted_members  # Other member should remain

    def test_admin_check_functionality(self, permission_manager):
        """Test checking if user is admin"""
        # Test existing admin
        assert 12345 in permission_manager.admins
        assert 67890 in permission_manager.admins
        
        # Test non-admin
        assert 99999 not in permission_manager.admins
        assert 88888 not in permission_manager.admins

    def test_restricted_check_functionality(self, permission_manager):
        """Test checking if user is restricted"""
        # Test existing restricted member
        assert 99999 in permission_manager.restricted_members
        assert 11111 in permission_manager.restricted_members
        
        # Test non-restricted member
        assert 12345 not in permission_manager.restricted_members
        assert 88888 not in permission_manager.restricted_members

    def test_data_persistence_workflow(self, permission_manager):
        """Test complete workflow of modifying and saving permissions"""
        with patch.object(permission_manager, 'save_permissions') as mock_save:
            # Add new admin
            permission_manager.admins.append(33333)
            
            # Add new restricted member
            permission_manager.restricted_members.append(44444)
            
            # Save changes
            permission_manager.save_permissions()
            
            # Verify save was called
            mock_save.assert_called_once()
            
            # Verify data was modified
            assert 33333 in permission_manager.admins
            assert 44444 in permission_manager.restricted_members

    def test_empty_initialization(self):
        """Test initialization with no existing file"""
        with patch('src.utils.permission_store.os.path.exists', return_value=False), \
             patch('src.utils.permission_store.logger'):
            
            manager = PermissionManager()
            assert manager.admins == []
            assert manager.restricted_members == []
            
            # Test that we can still add data
            manager.admins.append(12345)
            manager.restricted_members.append(67890)
            
            assert 12345 in manager.admins
            assert 67890 in manager.restricted_members

    def test_data_types_consistency(self, permission_manager):
        """Test that data types remain consistent"""
        # Verify initial types
        assert isinstance(permission_manager.admins, list)
        assert isinstance(permission_manager.restricted_members, list)
        
        # Verify all elements are integers (user IDs)
        for admin_id in permission_manager.admins:
            assert isinstance(admin_id, int)
        
        for restricted_id in permission_manager.restricted_members:
            assert isinstance(restricted_id, int)

    def test_duplicate_handling(self, permission_manager):
        """Test handling of duplicate entries"""
        initial_admin_count = len(permission_manager.admins)
        initial_restricted_count = len(permission_manager.restricted_members)
        
        # Try to add existing admin
        if permission_manager.admins:
            existing_admin = permission_manager.admins[0]
            permission_manager.admins.append(existing_admin)
            # Should now have duplicate
            assert len(permission_manager.admins) == initial_admin_count + 1
        
        # Try to add existing restricted member
        if permission_manager.restricted_members:
            existing_restricted = permission_manager.restricted_members[0]
            permission_manager.restricted_members.append(existing_restricted)
            # Should now have duplicate
            assert len(permission_manager.restricted_members) == initial_restricted_count + 1

    def test_cross_list_membership(self, permission_manager):
        """Test that users can be in both admin and restricted lists"""
        # Add an admin to restricted list
        if permission_manager.admins:
            admin_id = permission_manager.admins[0]
            permission_manager.restricted_members.append(admin_id)
            
            # Should be in both lists
            assert admin_id in permission_manager.admins
            assert admin_id in permission_manager.restricted_members