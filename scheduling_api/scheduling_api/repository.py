"""Repository protocol and in-memory implementation for appointments.

The ``AppointmentRepository`` Protocol defines the storage interface so
tests can inject a mock and production can swap to a persistent backend
without touching route handlers.

Design by Contract (plan.md § Design by Contract):
  InMemoryAppointmentRepository.add Post — appointment reachable via get(id).
  InMemoryAppointmentRepository.list Post — returns slice [offset:offset+limit]
      and total == len(store).
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from .models import Appointment


def generate_appointment_id() -> str:
    """Generate a unique appointment ID.

    Post: returned string is non-empty and URL-safe.
    """
    return f"apt-{uuid.uuid4().hex[:12]}"


@runtime_checkable
class AppointmentRepository(Protocol):
    """Storage interface for appointment records.

    Invariant: implementations must be thread-safe for the async event loop
    (single-threaded by default in uvicorn).
    """

    def add(self, appt: Appointment) -> None:
        """Persist a new appointment.

        Pre: appt.id is unique within the store.
        Post: get(appt.id) returns appt.
        """
        ...

    def get(self, id_: str) -> Appointment | None:
        """Return the appointment with the given ID, or None if absent.

        Pre: id_ is a non-empty string.
        Post: returns None when not found (never raises).
        """
        ...

    def list_all(self, limit: int, offset: int) -> tuple[list[Appointment], int]:
        """Return a page of appointments and the total count.

        Pre: limit >= 1, offset >= 0.
        Post: len(items) <= limit; total == count of all stored appointments.
        """
        ...


class InMemoryAppointmentRepository:
    """In-memory dict-backed implementation of AppointmentRepository.

    Acceptable for MVP — interface allows future swap to durable storage.

    Invariant: ``_store`` keys equal ``appointment.id`` for every value.
    """

    def __init__(self) -> None:
        self._store: dict[str, Appointment] = {}

    def add(self, appt: Appointment) -> None:
        """Store appointment by its ID.

        Pre: appt.id not already in store (caller generates unique IDs).
        Post: len(store) increased by 1; get(appt.id) == appt.
        """
        self._store[appt.id] = appt

    def get(self, id_: str) -> Appointment | None:
        """Return appointment or None."""
        return self._store.get(id_)

    def list_all(self, limit: int, offset: int) -> tuple[list[Appointment], int]:
        """Return paginated slice and total count.

        Post: items are ordered by insertion (dict preserves insertion order in CPython 3.7+).
        """
        all_items = list(self._store.values())
        total = len(all_items)
        page = all_items[offset : offset + limit]
        return page, total
