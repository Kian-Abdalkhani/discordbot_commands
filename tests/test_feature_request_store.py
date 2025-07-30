import pytest
import json
import os
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime
from src.utils.feature_request_store import FeatureRequestManager


class TestFeatureRequestManager:
    @pytest.fixture
    def mock_requests_data(self):
        return {
            "requests": [
                {
                    "id": 1,
                    "name": "Test User",
                    "request": "Add a new game feature",
                    "user_id": 12345,
                    "username": "testuser",
                    "timestamp": "2023-01-01T00:00:00",
                    "status": "pending"
                },
                {
                    "id": 2,
                    "name": "Another User",
                    "request": "Fix a bug in the system",
                    "user_id": 67890,
                    "username": "anotheruser",
                    "timestamp": "2023-01-02T00:00:00",
                    "status": "completed"
                }
            ]
        }

    @pytest.fixture
    def feature_manager(self, mock_requests_data):
        with patch('src.utils.feature_request_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_requests_data))):
            return FeatureRequestManager()

    def test_initialization(self, feature_manager):
        """Test FeatureRequestManager initialization"""
        assert feature_manager.filepath.endswith("feature_requests.json")
        assert isinstance(feature_manager.requests, list)
        assert len(feature_manager.requests) == 2

    def test_load_requests_file_exists(self, mock_requests_data):
        """Test loading requests when file exists"""
        with patch('src.utils.feature_request_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_requests_data))), \
             patch('src.utils.feature_request_store.logger') as mock_logger:
            
            manager = FeatureRequestManager()
            assert len(manager.requests) == 2
            assert manager.requests[0]["name"] == "Test User"
            assert manager.requests[1]["name"] == "Another User"
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Loaded 2 feature requests" in log_call

    def test_load_requests_file_not_exists(self):
        """Test loading requests when file doesn't exist"""
        with patch('src.utils.feature_request_store.os.path.exists', return_value=False), \
             patch('src.utils.feature_request_store.logger') as mock_logger:
            
            manager = FeatureRequestManager()
            assert manager.requests == []
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Feature requests file not found" in log_call

    def test_load_requests_json_error(self):
        """Test loading requests with JSON decode error"""
        with patch('src.utils.feature_request_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="invalid json")), \
             patch('src.utils.feature_request_store.logger') as mock_logger:
            
            manager = FeatureRequestManager()
            assert manager.requests == []
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "Error loading feature requests" in log_call

    def test_load_requests_missing_requests_key(self):
        """Test loading requests when data doesn't have 'requests' key"""
        invalid_data = {"other_key": "value"}
        with patch('src.utils.feature_request_store.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(invalid_data))), \
             patch('src.utils.feature_request_store.logger') as mock_logger:
            
            manager = FeatureRequestManager()
            assert manager.requests == []

    def test_add_request_success(self, feature_manager):
        """Test successfully adding a new feature request"""
        with patch.object(feature_manager, 'save_requests') as mock_save, \
             patch('src.utils.feature_request_store.logger') as mock_logger, \
             patch('src.utils.feature_request_store.datetime') as mock_datetime:
            
            # Mock datetime.now()
            mock_now = datetime(2023, 1, 3, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            # Add a new request
            result = feature_manager.add_request(
                name="New User",
                request_text="Add a cool new feature",
                user_id=99999,
                username="newuser"
            )
            
            # Verify the request was added
            assert len(feature_manager.requests) == 3
            assert result["id"] == 3  # Should be len(requests) + 1 before adding
            assert result["name"] == "New User"
            assert result["request"] == "Add a cool new feature"
            assert result["user_id"] == 99999
            assert result["username"] == "newuser"
            assert result["timestamp"] == mock_now.isoformat()
            assert result["status"] == "pending"
            
            # Verify save was called
            mock_save.assert_called_once()
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Added new feature request from New User" in log_call

    def test_add_request_minimal_data(self, feature_manager):
        """Test adding a request with minimal required data"""
        with patch.object(feature_manager, 'save_requests') as mock_save, \
             patch('src.utils.feature_request_store.logger'), \
             patch('src.utils.feature_request_store.datetime') as mock_datetime:
            
            mock_now = datetime(2023, 1, 3, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            # Add request with only required fields
            result = feature_manager.add_request(
                name="Minimal User",
                request_text="Simple request"
            )
            
            # Verify the request was added with defaults
            assert result["name"] == "Minimal User"
            assert result["request"] == "Simple request"
            assert result["user_id"] is None
            assert result["username"] is None
            assert result["status"] == "pending"
            
            mock_save.assert_called_once()

    def test_add_request_incremental_ids(self, feature_manager):
        """Test that request IDs increment correctly"""
        with patch.object(feature_manager, 'save_requests'), \
             patch('src.utils.feature_request_store.logger'), \
             patch('src.utils.feature_request_store.datetime') as mock_datetime:
            
            mock_datetime.now.return_value = datetime.now()
            
            # Add first request
            result1 = feature_manager.add_request("User1", "Request1")
            assert result1["id"] == 3  # Should be 3 since we start with 2 requests
            
            # Add second request
            result2 = feature_manager.add_request("User2", "Request2")
            assert result2["id"] == 4  # Should increment

    def test_save_requests_success(self, feature_manager):
        """Test successfully saving requests to file"""
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump, \
             patch('src.utils.feature_request_store.logger') as mock_logger:
            
            feature_manager.save_requests()
            
            # Verify file was opened for writing
            mock_file.assert_called_once_with(feature_manager.filepath, 'w')
            
            # Verify json.dump was called with correct data
            mock_json_dump.assert_called_once()
            call_args = mock_json_dump.call_args[0]
            assert 'requests' in call_args[0]
            assert call_args[0]['requests'] == feature_manager.requests
            
            # Verify logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Saved" in log_call and "successfully" in log_call

    def test_save_requests_error(self, feature_manager):
        """Test handling save error"""
        with patch('builtins.open', side_effect=IOError("Write error")), \
             patch('src.utils.feature_request_store.logger') as mock_logger:
            
            feature_manager.save_requests()
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "Error saving feature requests" in log_call

    def test_filepath_construction(self):
        """Test that filepath is constructed correctly"""
        with patch('src.utils.feature_request_store.os.path.exists', return_value=False), \
             patch('src.utils.feature_request_store.logger'):
            
            manager = FeatureRequestManager()
            
            # Verify the filepath ends with the expected path
            assert manager.filepath.endswith(os.path.join("data", "feature_requests.json"))
            
            # Verify it's an absolute path
            assert os.path.isabs(manager.filepath)

    def test_request_data_structure(self, feature_manager):
        """Test that request data has the correct structure"""
        with patch.object(feature_manager, 'save_requests'), \
             patch('src.utils.feature_request_store.logger'), \
             patch('src.utils.feature_request_store.datetime') as mock_datetime:
            
            mock_now = datetime(2023, 1, 3, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            result = feature_manager.add_request(
                name="Test User",
                request_text="Test request",
                user_id=12345,
                username="testuser"
            )
            
            # Verify all required fields are present
            required_fields = ["id", "name", "request", "user_id", "username", "timestamp", "status"]
            for field in required_fields:
                assert field in result
            
            # Verify data types
            assert isinstance(result["id"], int)
            assert isinstance(result["name"], str)
            assert isinstance(result["request"], str)
            assert isinstance(result["timestamp"], str)
            assert isinstance(result["status"], str)

    def test_empty_requests_list_initialization(self):
        """Test initialization with empty requests list"""
        with patch('src.utils.feature_request_store.os.path.exists', return_value=False), \
             patch('src.utils.feature_request_store.logger'):
            
            manager = FeatureRequestManager()
            assert manager.requests == []
            
            # Test adding first request
            with patch.object(manager, 'save_requests'), \
                 patch('src.utils.feature_request_store.logger'), \
                 patch('src.utils.feature_request_store.datetime') as mock_datetime:
                
                mock_datetime.now.return_value = datetime.now()
                result = manager.add_request("First User", "First request")
                assert result["id"] == 1  # Should start at 1 for empty list