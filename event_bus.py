from collections import defaultdict
from typing import Callable, Any

class EventBus:
    """A centralized publish/subscribe event bus for inter-component communication."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers = defaultdict(list)
        return cls._instance

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to an event type."""
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from an event type."""
        if callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)

    def publish(self, event_type: str, *args, **kwargs):
        """Publish an event with optional arguments."""
        # Create a copy of the list to safely iterate if subscribers modify the list
        for callback in list(self.subscribers.get(event_type, [])):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                import traceback
                print(f"Error executing callback for event '{event_type}': {e}")
                traceback.print_exc()

    def clear(self):
        """Clear all subscribers."""
        self.subscribers.clear()
