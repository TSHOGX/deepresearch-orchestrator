"""Event bus for publishing and subscribing to events."""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine
from weakref import WeakSet

from deep_research.models.events import BaseEvent, EventType

logger = logging.getLogger(__name__)

# Type for event handlers
EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus for publishing and subscribing to events.

    Supports both global event subscriptions and session-specific subscriptions.
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        # Global handlers: event_type -> set of handlers
        self._global_handlers: dict[EventType, set[EventHandler]] = defaultdict(set)

        # Session handlers: session_id -> event_type -> set of handlers
        self._session_handlers: dict[str, dict[EventType, set[EventHandler]]] = defaultdict(
            lambda: defaultdict(set)
        )

        # Async queues for session streams: session_id -> queue
        self._session_queues: dict[str, asyncio.Queue[BaseEvent]] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all subscribed handlers.

        Args:
            event: The event to publish.
        """
        logger.debug(f"Publishing event: {event.event_type.value} for session {event.session_id}")

        # Collect all handlers to call
        handlers: list[EventHandler] = []

        # Global handlers for this event type
        if event.event_type in self._global_handlers:
            handlers.extend(self._global_handlers[event.event_type])

        # Session-specific handlers
        if event.session_id in self._session_handlers:
            session_handlers = self._session_handlers[event.session_id]
            if event.event_type in session_handlers:
                handlers.extend(session_handlers[event.event_type])

        # Call all handlers concurrently
        if handlers:
            await asyncio.gather(
                *[self._safe_call(handler, event) for handler in handlers],
                return_exceptions=True,
            )

        # Put event in session queue if exists
        if event.session_id in self._session_queues:
            try:
                self._session_queues[event.session_id].put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Event queue full for session {event.session_id}")

    async def _safe_call(self, handler: EventHandler, event: BaseEvent) -> None:
        """Safely call a handler, catching exceptions."""
        try:
            await handler(event)
        except Exception as e:
            logger.exception(f"Error in event handler for {event.event_type.value}: {e}")

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        session_id: str | None = None,
    ) -> Callable[[], None]:
        """Subscribe to an event type.

        Args:
            event_type: The type of event to subscribe to.
            handler: Async handler function to call when event is published.
            session_id: Optional session ID for session-specific subscription.

        Returns:
            Unsubscribe function to remove the subscription.
        """
        if session_id:
            self._session_handlers[session_id][event_type].add(handler)

            def unsubscribe() -> None:
                self._session_handlers[session_id][event_type].discard(handler)
                # Clean up empty entries
                if not self._session_handlers[session_id][event_type]:
                    del self._session_handlers[session_id][event_type]
                if not self._session_handlers[session_id]:
                    del self._session_handlers[session_id]

        else:
            self._global_handlers[event_type].add(handler)

            def unsubscribe() -> None:
                self._global_handlers[event_type].discard(handler)

        return unsubscribe

    def subscribe_all(
        self,
        handler: EventHandler,
        session_id: str | None = None,
    ) -> Callable[[], None]:
        """Subscribe to all event types.

        Args:
            handler: Async handler function to call for any event.
            session_id: Optional session ID for session-specific subscription.

        Returns:
            Unsubscribe function to remove all subscriptions.
        """
        unsubscribers = []
        for event_type in EventType:
            unsubscribe = self.subscribe(event_type, handler, session_id)
            unsubscribers.append(unsubscribe)

        def unsubscribe_all() -> None:
            for unsub in unsubscribers:
                unsub()

        return unsubscribe_all

    async def create_session_stream(
        self, session_id: str, max_size: int = 100
    ) -> asyncio.Queue[BaseEvent]:
        """Create an event queue for streaming session events.

        Args:
            session_id: The session ID to stream events for.
            max_size: Maximum queue size.

        Returns:
            Async queue that receives all events for this session.
        """
        async with self._lock:
            if session_id not in self._session_queues:
                self._session_queues[session_id] = asyncio.Queue(maxsize=max_size)
            return self._session_queues[session_id]

    async def close_session_stream(self, session_id: str) -> None:
        """Close and remove a session's event stream.

        Args:
            session_id: The session ID to close.
        """
        async with self._lock:
            if session_id in self._session_queues:
                del self._session_queues[session_id]

            # Also clean up session handlers
            if session_id in self._session_handlers:
                del self._session_handlers[session_id]

    def get_session_queue(self, session_id: str) -> asyncio.Queue[BaseEvent] | None:
        """Get the event queue for a session if it exists.

        Args:
            session_id: The session ID.

        Returns:
            The event queue or None if not found.
        """
        return self._session_queues.get(session_id)

    async def clear(self) -> None:
        """Clear all handlers and queues."""
        async with self._lock:
            self._global_handlers.clear()
            self._session_handlers.clear()
            self._session_queues.clear()


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus instance."""
    global _event_bus
    _event_bus = None
