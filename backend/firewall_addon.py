"""mitmproxy addon for Deep Packet Inspection"""
import logging
from mitmproxy import http
from .rules_manager import RulesManager
from .database import log_request

logger = logging.getLogger(__name__)


class FirewallAddon:
    """mitmproxy addon that implements DPI firewall"""
    
    def __init__(self, rules_manager: RulesManager, get_observe_mode):
        self.rules_manager = rules_manager
        self.get_observe_mode = get_observe_mode
    
    def request(self, flow: http.HTTPFlow) -> None:
        """Handle incoming HTTP/HTTPS requests"""
        url = "unknown"
        try:
            url = flow.request.pretty_url
            headers = dict(flow.request.headers)
            
            # Get request body
            body = ""
            if flow.request.content:
                try:
                    body = flow.request.content.decode('utf-8', errors='ignore')
                except Exception as e:
                    logger.warning(f"Failed to decode request body: {e}")
                    body = ""
            
            # Convert headers to string for logging
            headers_str = "\n".join(f"{k}: {v}" for k, v in headers.items())
            
            # Check rules
            matched_rule = self.rules_manager.check_request(url, headers, body)
            
            if matched_rule and matched_rule.action == "block":
                description = matched_rule.description or matched_rule.pattern
                if not self.get_observe_mode():
                    # Enforce: Block the request
                    block_message = f"Request blocked by firewall rule: {description}"
                    flow.response = http.Response.make(
                        403,
                        block_message.encode(),
                        {"Content-Type": "text/plain"}
                    )
                    logger.warning(f"BLOCKED: {url} - {description}")
                    log_request(url, blocked=True, headers=headers_str, body=body, matched_rule=description)
                else:
                    # Observe mode: do not block, but log matched rule
                    logger.info(f"OBSERVE MATCH: {url} - {description}")
                    log_request(url, blocked=False, headers=headers_str, body=body, matched_rule=description)
            else:
                # Allow the request
                logger.info(f"ALLOWED: {url}")
                log_request(url, blocked=False, headers=headers_str, body=body)
        
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            # On error, allow the request to pass through
            log_request(url, blocked=False)

