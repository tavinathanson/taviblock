"""Pytest configuration and fixtures"""

import pytest
import tempfile
import os
import shutil
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.config_loader import Config
from cli import db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    
    # Monkey patch the database path
    original_db_path = db.DB_PATH
    db.DB_PATH = db_path
    
    # Initialize the test database
    db.init_db()
    
    yield db_path
    
    # Cleanup
    db.DB_PATH = original_db_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_config():
    """Load test configuration"""
    test_config_path = os.path.join(os.path.dirname(__file__), 'test_config.yaml')
    return Config(test_config_path)


@pytest.fixture
def clean_sessions(temp_db):
    """Ensure clean session state before each test"""
    # Clear any existing sessions
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM unblock_sessions")
    conn.commit()
    conn.close()
    return temp_db