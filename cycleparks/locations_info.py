import json
import logging
import numpy as np
import os
import asyncio

from typing import List
from datetime import datetime, timedelta

from sklearn.neighbors import BallTree

from sqlalchemy import select

from cycleparks.db import get_session
from cycleparks.models import CyclePark


logger = logging.getLogger(__name__)


class LocationsInfo:
    location_data: List
    location_tree: BallTree
    DEFAULT_LOCATIONS_LIMIT = 3
    MAX_LOCATIONS_LIMIT = 10
    REFRESH_THROTTLE_SECONDS = 60
    last_refresh_time: datetime = None
    refresh_pending: bool = False
    refresh_task: asyncio.Task = None

    @classmethod
    async def read_cycle_parks(cls):
        async with get_session() as session:
            result = await session.execute(
                select(CyclePark).where(CyclePark.prk_hangar == False)
            )
            cycleparks = result.scalars().all()

        cls.location_data = [
            {
                "longitude": cp.longitude,
                "latitude": cp.latitude,
                "photo1_url": cp.photo1_url,
                "photo2_url": cp.photo2_url,
            }
            for cp in cycleparks
        ]

        if cls.location_data:
            coords = np.radians(
                [[entry["latitude"], entry["longitude"]] for entry in cls.location_data]
            )
            cls.location_tree = BallTree(coords, metric="haversine")
        else:
            logger.warning("No cycle parks data available, location tree will be None")
            cls.location_tree = None
        
        cls.last_refresh_time = datetime.now()

    @classmethod
    async def refresh_cycle_parks(cls):
        """Refresh cycle parks data with throttling to prevent frequent updates."""
        now = datetime.now()

        # Check if enough time has passed since last refresh
        if cls.last_refresh_time is not None:
            time_since_refresh = now - cls.last_refresh_time
            if time_since_refresh < timedelta(seconds=cls.REFRESH_THROTTLE_SECONDS):
                logger.debug(
                    f"Throttling refresh: only {time_since_refresh.total_seconds():.1f}s since last refresh. "
                    f"Scheduling deferred refresh in {cls.REFRESH_THROTTLE_SECONDS - time_since_refresh.total_seconds():.1f}s"
                )
                cls.refresh_pending = True

                # Cancel existing deferred refresh task if any
                if cls.refresh_task is not None:
                    cls.refresh_task.cancel()

                # Schedule deferred refresh after throttle period
                sleep_seconds = (
                    cls.REFRESH_THROTTLE_SECONDS - time_since_refresh.total_seconds()
                )
                cls.refresh_task = asyncio.create_task(
                    cls._deferred_refresh(sleep_seconds)
                )
                return

        logger.info("Refreshing cycle parks data...")
        await cls.read_cycle_parks()
        cls.refresh_pending = False
        if cls.refresh_task is not None:
            cls.refresh_task.cancel()
            cls.refresh_task = None

    @classmethod
    async def _deferred_refresh(cls, delay_seconds: float):
        """Helper to perform a deferred refresh after a delay."""
        try:
            await asyncio.sleep(delay_seconds)
            if cls.refresh_pending:
                logger.info("Executing deferred cycle parks refresh...")
                await cls.read_cycle_parks()
                cls.refresh_pending = False
        except asyncio.CancelledError:
            logger.debug("Deferred refresh was cancelled")
            pass

    @classmethod
    def get_nearest_cycleparks(cls, lat, lon, k=DEFAULT_LOCATIONS_LIMIT):
        if cls.location_tree is None or not cls.location_data:
            logger.warning("Location tree not initialized or no cycle parks data available")
            return [], []
        
        target_rad = np.radians([lat, lon]).reshape(1, -1)
        distances, indices = cls.location_tree.query(target_rad, k=k)
        distances_meters = distances[0] * 6371000  # Convert to meters
        closest_entries = [cls.location_data[i] for i in indices[0]]
        return closest_entries, distances_meters
