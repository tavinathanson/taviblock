"""Test taviblock commands with minimal mocking"""

import pytest
import sys
from io import StringIO
from contextlib import contextmanager
from cli import db
import cli.taviblock as taviblock


@contextmanager
def capture_stdout():
    """Capture stdout for testing print output"""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        yield sys.stdout
    finally:
        sys.stdout = old_stdout


class TestCommands:
    """Test taviblock command functions"""
    
    def test_format_time_remaining(self):
        """Test time formatting function"""
        assert taviblock.format_time_remaining(30) == "30 seconds"
        assert taviblock.format_time_remaining(60) == "1 minute"
        assert taviblock.format_time_remaining(90) == "1 minute 30 seconds"
        assert taviblock.format_time_remaining(120) == "2 minutes"
        assert taviblock.format_time_remaining(3600) == "1 hour"
        assert taviblock.format_time_remaining(3660) == "1 hour 1 minute"
        assert taviblock.format_time_remaining(7200) == "2 hours"
    
    def test_find_session_by_target(self, clean_sessions):
        """Test finding sessions by target name"""
        # Create some sessions
        db.add_unblock_session(['example.com'], 30, 0, 'unblock')
        db.add_unblock_session(['group1.com', 'group2.com'], 30, 0, 'unblock')
        
        sessions = db.get_active_sessions()
        
        # Find exact match
        session = taviblock.find_session_by_target('example.com', sessions)
        assert session is not None
        assert 'example.com' in session['domains']
        
        # Find partial match
        session = taviblock.find_session_by_target('group1', sessions)
        assert session is not None
        assert 'group1.com' in session['domains']
        
        # Not found
        session = taviblock.find_session_by_target('notreal', sessions)
        assert session is None
    
    def test_cmd_profile_basic(self, clean_sessions, test_config):
        """Test basic profile command execution"""
        with capture_stdout() as output:
            # Should succeed and create a session
            taviblock.cmd_profile(test_config, 'unblock', ['example'])
        
        output_text = output.getvalue()
        assert 'Created 1 parallel session(s)' in output_text
        
        # Verify session was created (might be pending due to wait time)
        sessions = db.get_active_sessions() + db.get_pending_sessions()
        assert len(sessions) == 1
        assert 'example.com' in sessions[0]['domains']
    
    def test_cmd_profile_invalid_target(self, clean_sessions, test_config):
        """Test profile command with invalid target"""
        with capture_stdout() as output:
            with pytest.raises(SystemExit):
                taviblock.cmd_profile(test_config, 'unblock', ['fakedomainxyz'])
        
        output_text = output.getvalue()
        assert 'Unknown domain or group' in output_text
        assert 'Available targets' in output_text
    
    def test_cmd_profile_duplicate_prevention(self, clean_sessions, test_config):
        """Test that duplicate sessions are prevented"""
        # Create first session with no wait time (immediate active)
        db.add_unblock_session(['example.com'], 30, 0, 'unblock')
        
        # Try to create duplicate
        with capture_stdout() as output:
            taviblock.cmd_profile(test_config, 'unblock', ['example'])
        
        output_text = output.getvalue()
        assert 'Already unblocked: example' in output_text
        
        # Should still only have one session
        sessions = db.get_active_sessions()
        assert len(sessions) == 1
    
    def test_cmd_profile_pending_duplicate(self, clean_sessions, test_config):
        """Test duplicate prevention for pending sessions"""
        # Create a pending session
        db.add_unblock_session(['example.com'], 30, 5, 'unblock')
        
        # Try to create duplicate
        with capture_stdout() as output:
            taviblock.cmd_profile(test_config, 'unblock', ['example'])
        
        output_text = output.getvalue()
        assert 'Already pending: example' in output_text
    
    def test_cmd_cancel_by_id(self, clean_sessions, test_config):
        """Test canceling session by ID"""
        # Create a session
        session_id = db.add_unblock_session(['example.com'], 30, 0, 'unblock')
        
        # Mock args
        class Args:
            target = str(session_id)
        
        with capture_stdout() as output:
            taviblock.cmd_cancel(test_config, Args())
        
        output_text = output.getvalue()
        assert f'Cancelled session {session_id}' in output_text
        
        # Verify it's gone
        assert db.get_session_info(session_id) is None
    
    def test_cmd_cancel_by_name(self, clean_sessions, test_config):
        """Test canceling session by name"""
        # Create a session
        session_id = db.add_unblock_session(['example.com'], 30, 0, 'unblock')
        
        # Mock args
        class Args:
            target = 'example'
        
        with capture_stdout() as output:
            taviblock.cmd_cancel(test_config, Args())
        
        output_text = output.getvalue()
        assert 'Cancelled session' in output_text
        assert 'for example' in output_text
        
        # Verify it's gone
        assert db.get_session_info(session_id) is None
    
    def test_cmd_cancel_all(self, clean_sessions, test_config):
        """Test canceling all sessions"""
        # Create multiple sessions
        db.add_unblock_session(['example.com'], 30, 0, 'unblock')
        db.add_unblock_session(['test.com'], 30, 5, 'unblock')
        
        # Mock args
        class Args:
            target = None
        
        with capture_stdout() as output:
            taviblock.cmd_cancel(test_config, Args())
        
        output_text = output.getvalue()
        assert 'Cancelled 2 session(s)' in output_text
        
        # Verify all are gone
        assert len(db.get_active_sessions()) == 0
        assert len(db.get_pending_sessions()) == 0
    
    def test_cmd_replace_by_id(self, clean_sessions, test_config):
        """Test replacing session by ID"""
        # Create a pending session
        session_id = db.add_unblock_session(['example.com'], 30, 5, 'unblock')
        
        # Mock args
        class Args:
            old = str(session_id)
            new_targets = ['test']
        
        with capture_stdout() as output:
            taviblock.cmd_replace(test_config, Args())
        
        output_text = output.getvalue()
        assert f'Replaced session {session_id}' in output_text
        assert 'New targets: test' in output_text
        
        # Verify old is gone and new exists
        assert db.get_session_info(session_id) is None
        sessions = db.get_pending_sessions()
        assert len(sessions) == 1
        assert 'test.com' in sessions[0]['domains']
    
    def test_cmd_replace_by_name(self, clean_sessions, test_config):
        """Test replacing session by name"""
        # Create a pending session
        db.add_unblock_session(['example.com'], 30, 5, 'unblock')
        
        # Mock args
        class Args:
            old = 'example'
            new_targets = ['test']
        
        with capture_stdout() as output:
            taviblock.cmd_replace(test_config, Args())
        
        output_text = output.getvalue()
        assert 'Replaced session' in output_text
        
        # Verify replacement
        sessions = db.get_pending_sessions()
        assert len(sessions) == 1
        assert 'test.com' in sessions[0]['domains']
    
    def test_cmd_replace_active_fails(self, clean_sessions, test_config):
        """Test that replacing active session fails"""
        # Create an active session
        session_id = db.add_unblock_session(['example.com'], 30, 0, 'unblock')
        
        # Mock args
        class Args:
            old = str(session_id)
            new_targets = ['test']
        
        with capture_stdout() as output:
            with pytest.raises(SystemExit):
                taviblock.cmd_replace(test_config, Args())
        
        output_text = output.getvalue()
        assert 'already active' in output_text
    
    def test_cmd_status_empty(self, clean_sessions, test_config):
        """Test status with no sessions"""
        # Mock args
        class Args:
            pass
        
        with capture_stdout() as output:
            taviblock.cmd_status(test_config, Args())
        
        output_text = output.getvalue()
        assert 'All domains are blocked' in output_text
    
    def test_cmd_status_with_sessions(self, clean_sessions, test_config):
        """Test status with active and pending sessions"""
        # Create sessions
        db.add_unblock_session(['active.com'], 30, 0, 'unblock')
        db.add_unblock_session(['pending.com'], 30, 5, 'unblock')
        
        # Mock args
        class Args:
            pass
        
        with capture_stdout() as output:
            taviblock.cmd_status(test_config, Args())
        
        output_text = output.getvalue()
        assert 'ACTIVE SESSIONS:' in output_text
        assert 'PENDING SESSIONS:' in output_text
        assert 'active.com' in output_text
        assert 'pending.com' in output_text