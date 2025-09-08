"""Test database operations"""

import pytest
from datetime import datetime
from cli import db


class TestDatabase:
    """Test database functions"""
    
    def test_add_unblock_session(self, clean_sessions):
        """Test adding a basic unblock session"""
        domains = ['example.com', 'test.com']
        session_id = db.add_unblock_session(domains, 30, 0, 'unblock')
        
        assert isinstance(session_id, int)
        assert session_id > 0
    
    def test_get_session_info(self, clean_sessions):
        """Test retrieving session information"""
        domains = ['example.com']
        session_id = db.add_unblock_session(domains, 30, 0, 'unblock')
        
        session = db.get_session_info(session_id)
        
        assert session is not None
        assert session['id'] == session_id
        assert session['domains'] == domains
        assert session['session_type'] == 'unblock'
    
    def test_get_active_sessions(self, clean_sessions):
        """Test getting active sessions"""
        # Add an active session (no wait)
        db.add_unblock_session(['active.com'], 30, 0, 'unblock')
        
        # Add a pending session (with wait)
        db.add_unblock_session(['pending.com'], 30, 5, 'unblock')
        
        active = db.get_active_sessions()
        
        assert len(active) == 1
        assert active[0]['domains'] == ['active.com']
    
    def test_get_pending_sessions(self, clean_sessions):
        """Test getting pending sessions"""
        # Add an active session (no wait)
        db.add_unblock_session(['active.com'], 30, 0, 'unblock')
        
        # Add a pending session (with wait)
        db.add_unblock_session(['pending.com'], 30, 5, 'unblock')
        
        pending = db.get_pending_sessions()
        
        assert len(pending) == 1
        assert pending[0]['domains'] == ['pending.com']
    
    def test_cancel_session(self, clean_sessions):
        """Test canceling a session"""
        session_id = db.add_unblock_session(['cancel.com'], 30, 0, 'unblock')
        
        # Verify it exists
        assert db.get_session_info(session_id) is not None
        
        # Cancel it
        db.cancel_session(session_id)
        
        # Verify it's gone
        assert db.get_session_info(session_id) is None
    
    def test_get_all_unblocked_domains(self, clean_sessions):
        """Test getting all unblocked domains"""
        # Add multiple active sessions
        db.add_unblock_session(['domain1.com', 'domain2.com'], 30, 0, 'unblock')
        db.add_unblock_session(['domain3.com'], 30, 0, 'unblock')
        
        # Don't include pending
        db.add_unblock_session(['pending.com'], 30, 5, 'unblock')
        
        unblocked = db.get_all_unblocked_domains()
        
        assert 'domain1.com' in unblocked
        assert 'domain2.com' in unblocked
        assert 'domain3.com' in unblocked
        assert 'pending.com' not in unblocked
        assert len(unblocked) == 3
    
    def test_session_timing(self, clean_sessions):
        """Test that session timing is calculated correctly"""
        duration_minutes = 30
        wait_minutes = 5
        
        session_id = db.add_unblock_session(['test.com'], duration_minutes, wait_minutes, 'unblock')
        session = db.get_session_info(session_id)
        
        now = datetime.now().timestamp()
        
        # Check wait_until is approximately now + wait_minutes
        expected_wait = now + (wait_minutes * 60)
        assert abs(session['wait_until'] - expected_wait) < 2  # Within 2 seconds
        
        # Check end_time is wait_until + duration
        expected_end = session['wait_until'] + (duration_minutes * 60)
        assert abs(session['end_time'] - expected_end) < 1  # Within 1 second
    
    def test_is_all_domains_flag(self, clean_sessions):
        """Test the is_all_domains flag"""
        # Regular session
        regular_id = db.add_unblock_session(['test.com'], 30, 0, 'unblock', is_all_domains=False)
        regular = db.get_session_info(regular_id)
        assert not regular['is_all_domains']
        
        # All domains session
        all_id = db.add_unblock_session(['test.com'], 30, 0, 'peek', is_all_domains=True)
        all_session = db.get_session_info(all_id)
        assert all_session['is_all_domains']