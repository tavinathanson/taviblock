#!/usr/bin/python3
"""
Config loader for taviblock YAML configuration
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import yaml


class Config:
    """Taviblock configuration loaded from YAML"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Look for config in standard locations
            possible_paths = [
                # System-wide config location
                "/etc/taviblock/config.yaml",
                # Home directory
                os.path.expanduser("~/.taviblock/config.yaml"),
                # Current working directory
                "config.yaml",
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            else:
                raise FileNotFoundError(
                    "Config file not found. Please create config.yaml in one of these locations:\n" +
                    "\n".join(f"  - {p}" for p in possible_paths)
                )
        
        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)
        
        self.domains = self.data.get('domains', {})
        self.profiles = self.data.get('profiles', {})
    
    def get_all_domains(self) -> List[str]:
        """Get all configured domains (individual + from groups)"""
        all_domains = []
        
        for name, config in self.domains.items():
            if isinstance(config, dict) and 'domains' in config:
                # It's a group
                all_domains.extend(config['domains'])
            else:
                # It's an individual domain
                all_domains.append(name)
        
        return list(set(all_domains))
    
    def resolve_targets(self, targets: List[str], profile_name: str = 'unblock') -> Tuple[List[str], Set[str]]:
        """
        Resolve target names to actual domains and collect all tags
        
        Returns:
            Tuple of (list of domains, set of all tags)
        """
        profile = self.profiles.get(profile_name, {})
        domains = []
        all_tags = set()
        
        # Handle special scopes
        if profile.get('all'):
            return self.get_all_domains(), self._get_all_tags()
        
        if 'tags' in profile:
            # Profile specifies tags to unblock
            for tag in profile['tags']:
                tagged_domains, _ = self._get_domains_by_tag(tag)
                domains.extend(tagged_domains)
            return list(set(domains)), set(profile['tags'])
        
        if 'only' in profile:
            # Profile specifies exact domains/groups
            targets = profile['only']
        
        # Resolve each target
        for target in targets:
            target = target.strip()
            
            # Check if it's a configured domain or group
            if target in self.domains:
                config = self.domains[target]
                if isinstance(config, dict):
                    if 'domains' in config:
                        # It's a group
                        domains.extend(config['domains'])
                    else:
                        # Individual domain with config
                        domains.append(target)
                    # Collect tags
                    if 'tags' in config:
                        all_tags.update(config['tags'])
            
            # Try adding .com if not found
            elif not target.endswith('.com') and (target + '.com') in self.domains:
                target_com = target + '.com'
                config = self.domains[target_com]
                if isinstance(config, dict):
                    if 'domains' in config:
                        domains.extend(config['domains'])
                    else:
                        domains.append(target_com)
                    if 'tags' in config:
                        all_tags.update(config['tags'])
            
            # If still not found, treat as raw domain
            else:
                domains.append(target)
        
        return list(set(domains)), all_tags
    
    def _get_domains_by_tag(self, tag: str) -> Tuple[List[str], Set[str]]:
        """Get all domains that have a specific tag"""
        domains = []
        all_tags = set()
        
        for name, config in self.domains.items():
            if isinstance(config, dict) and 'tags' in config and tag in config['tags']:
                if 'domains' in config:
                    # It's a group
                    domains.extend(config['domains'])
                else:
                    # Individual domain
                    domains.append(name)
                all_tags.update(config['tags'])
        
        return domains, all_tags
    
    def _get_all_tags(self) -> Set[str]:
        """Get all tags from all domains"""
        all_tags = set()
        for config in self.domains.values():
            if isinstance(config, dict) and 'tags' in config:
                all_tags.update(config['tags'])
        return all_tags
    
    def calculate_timing(self, profile_name: str, target_count: int, 
                        concurrent_sessions: int, all_tags: Set[str]) -> Dict[str, Any]:
        """
        Calculate wait and duration for a profile
        
        Args:
            profile_name: Name of the profile
            target_count: Number of targets being unblocked
            concurrent_sessions: Number of currently active/pending sessions
            all_tags: Set of all tags from targets
            
        Returns:
            Dict with 'wait' and 'duration' in minutes
        """
        profile = self.profiles.get(profile_name, {})
        
        # Handle simple cases
        if isinstance(profile.get('wait'), (int, float)):
            wait = profile['wait']
        else:
            wait_config = profile.get('wait', {})
            if isinstance(wait_config, dict):
                base = wait_config.get('base', 5)
                concurrent_penalty = wait_config.get('concurrent_penalty', 0)
                wait = base + (concurrent_sessions * concurrent_penalty)
            else:
                wait = 5  # Default
        
        # Check for tag-based overrides
        if 'tag_rules' in profile:
            for rule in profile['tag_rules']:
                if 'tags' in rule:
                    # Check if any of the rule's tags are in our tags
                    if any(tag in all_tags for tag in rule['tags']):
                        if 'wait_override' in rule:
                            wait = rule['wait_override']
                            break
        
        duration = profile.get('duration', 30)
        
        return {
            'wait': wait,
            'duration': duration,
            'cooldown': profile.get('cooldown', 0)
        }
    
    def get_profile_names(self) -> List[str]:
        """Get all available profile names"""
        return list(self.profiles.keys())
    
    def is_valid_profile(self, profile_name: str) -> bool:
        """Check if a profile exists"""
        return profile_name in self.profiles
    
    def get_default_profile(self) -> Optional[str]:
        """Get the default profile name if specified"""
        return self.data.get('default_profile')