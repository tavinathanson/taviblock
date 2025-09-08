"""Test configuration loading and validation"""

import pytest
from cli.config_loader import Config


class TestConfigLoader:
    """Test the Config class"""
    
    def test_config_loads_correctly(self, test_config):
        """Test that config loads all expected data"""
        # Check domains are loaded
        assert 'example.com' in test_config.domains
        assert 'testgroup' in test_config.domains
        assert 'ultra.com' in test_config.domains
        
        # Check profiles are loaded
        assert 'unblock' in test_config.profiles
        assert 'quick' in test_config.profiles
        assert 'testwork' in test_config.profiles
        
        # Check default profile
        assert test_config.get_default_profile() == 'unblock'
    
    def test_resolve_targets_single_domain(self, test_config):
        """Test resolving a single domain"""
        domains, tags = test_config.resolve_targets(['example.com'])
        
        assert 'example.com' in domains
        assert 'test' in tags
        assert 'basic' in tags
    
    def test_resolve_targets_without_com(self, test_config):
        """Test resolving domain without .com suffix"""
        domains, tags = test_config.resolve_targets(['example'])
        
        assert 'example.com' in domains
        assert len(domains) == 1
    
    def test_resolve_targets_group(self, test_config):
        """Test resolving a domain group"""
        domains, tags = test_config.resolve_targets(['testgroup'])
        
        assert 'group1.com' in domains
        assert 'group2.com' in domains
        assert len(domains) == 2
        assert 'group' in tags
    
    def test_resolve_targets_invalid_raises(self, test_config):
        """Test that invalid targets raise ValueError"""
        with pytest.raises(ValueError) as exc_info:
            test_config.resolve_targets(['notarealdomain'])
        
        assert 'Unknown domain or group: notarealdomain' in str(exc_info.value)
    
    def test_is_valid_target(self, test_config):
        """Test target validation method"""
        # Valid targets
        assert test_config.is_valid_target('example.com')
        assert test_config.is_valid_target('example')  # without .com
        assert test_config.is_valid_target('testgroup')
        assert test_config.is_valid_target('ultra.com')
        
        # Invalid targets
        assert not test_config.is_valid_target('fake')
        assert not test_config.is_valid_target('notreal.com')
        assert not test_config.is_valid_target('random123')
    
    def test_profile_timing_basic(self, test_config):
        """Test basic profile timing calculation"""
        timing = test_config.calculate_timing('unblock', 1, 0, set())
        
        assert timing['wait'] == 5
        assert timing['duration'] == 30
    
    def test_profile_timing_with_concurrent(self, test_config):
        """Test timing with concurrent sessions"""
        timing = test_config.calculate_timing('unblock', 1, 2, set())
        
        # Base 5 + (2 concurrent * 5 penalty) = 15
        assert timing['wait'] == 15
    
    def test_profile_timing_ultra_distracting(self, test_config):
        """Test ultra_distracting tag override"""
        timing = test_config.calculate_timing('unblock', 1, 0, {'ultra_distracting'})
        
        assert timing['wait'] == 30  # Override from tag_rules
    
    def test_get_profile_names(self, test_config):
        """Test getting all profile names"""
        profiles = test_config.get_profile_names()
        
        assert 'unblock' in profiles
        assert 'quick' in profiles
        assert 'testwork' in profiles
        assert 'testall' in profiles