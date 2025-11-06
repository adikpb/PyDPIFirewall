"""Rules management with file watching"""
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from threading import Lock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .config import PROJECT_ROOT

logger = logging.getLogger(__name__)


class Rule:
    """Represents a firewall rule"""
    def __init__(self, pattern: str, rule_type: str, action: str, description: str = ""):
        self.pattern = pattern
        self.type = rule_type  # url, header, or body
        self.action = action  # block
        self.description = description
        try:
            self.regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            self.regex = None


class RulesManager(FileSystemEventHandler):
    """Manages firewall rules with file watching"""
    
    def __init__(self, rules_file: str):
        self.rules_file = Path(rules_file)
        if not self.rules_file.is_absolute():
            self.rules_file = PROJECT_ROOT / self.rules_file
        self.rules: List[Rule] = []
        self.lock = Lock()
        self.observer = None
        self.last_loaded_at: Optional[str] = None
        self.load_rules()
        self.start_watching()
    
    def load_rules(self):
        """Load rules from JSON file"""
        try:
            if not self.rules_file.exists():
                logger.warning(f"Rules file not found: {self.rules_file}")
                self.rules = []
                return
            
            with open(self.rules_file, 'r') as f:
                data = json.load(f)
            
            new_rules = []
            for rule_data in data.get("rules", []):
                rule = Rule(
                    pattern=rule_data.get("pattern", ""),
                    rule_type=rule_data.get("type", "url"),
                    action=rule_data.get("action", "block"),
                    description=rule_data.get("description", "")
                )
                if rule.regex:  # Only add if regex compiled successfully
                    new_rules.append(rule)
            
            with self.lock:
                self.rules = new_rules
                from datetime import datetime
                self.last_loaded_at = datetime.utcnow().isoformat() + "Z"
            
            logger.info(f"Loaded {len(new_rules)} rules from {self.rules_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in rules file: {e}")
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.src_path == str(self.rules_file):
            logger.info(f"Rules file modified, reloading...")
            self.load_rules()
    
    def start_watching(self):
        """Start watching the rules file for changes"""
        try:
            self.observer = Observer()
            self.observer.schedule(self, path=str(self.rules_file.parent), recursive=False)
            self.observer.start()
            logger.info(f"Started watching rules file: {self.rules_file}")
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
    
    def stop_watching(self):
        """Stop watching the rules file"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
    
    def check_request(self, url: str, headers: Dict[str, str], body: str = "") -> Optional[Rule]:
        """Check if a request matches any rule"""
        with self.lock:
            rules = self.rules.copy()
        
        for rule in rules:
            if rule.type == "url":
                if rule.regex.search(url):
                    logger.info(f"Rule matched (URL): {rule.description or rule.pattern}")
                    return rule
            elif rule.type == "header":
                headers_str = "\n".join(f"{k}: {v}" for k, v in headers.items())
                if rule.regex.search(headers_str):
                    logger.info(f"Rule matched (Header): {rule.description or rule.pattern}")
                    return rule
            elif rule.type == "body":
                if rule.regex.search(body):
                    logger.info(f"Rule matched (Body): {rule.description or rule.pattern}")
                    return rule
        
        return None

    def serialize_rules(self) -> List[Dict[str, str]]:
        with self.lock:
            rules = self.rules.copy()
        return [
            {
                "pattern": r.pattern,
                "type": r.type,
                "action": r.action,
                "description": r.description,
            }
            for r in rules
            if r.regex is not None
        ]

    @staticmethod
    def validate_rules_payload(payload: Dict) -> Tuple[bool, List[Dict[str, str]]]:
        errors: List[Dict[str, str]] = []
        rules = payload.get("rules")
        if not isinstance(rules, list):
            return False, [{"index": "-", "message": "'rules' must be a list"}]
        for idx, rd in enumerate(rules):
            if not isinstance(rd, dict):
                errors.append({"index": str(idx), "message": "rule must be an object"})
                continue
            pat = rd.get("pattern")
            typ = rd.get("type")
            act = rd.get("action")
            if not pat or not isinstance(pat, str):
                errors.append({"index": str(idx), "message": "pattern is required"})
            if typ not in {"url", "header", "body"}:
                errors.append({"index": str(idx), "message": "type must be one of url|header|body"})
            if act != "block":
                errors.append({"index": str(idx), "message": "action must be 'block'"})
            try:
                re.compile(pat or "")
            except re.error as e:
                errors.append({"index": str(idx), "message": f"invalid regex: {e}"})
        return len(errors) == 0, errors

