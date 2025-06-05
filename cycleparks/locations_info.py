import json
import logging
import numpy as np
import os
import urllib.request

from typing import List

from sklearn.neighbors import BallTree



logger = logging.getLogger(__name__)


class LocationsInfo:
    location_data: List
    location_tree: BallTree
    DEFAULT_LOCATIONS_LIMIT = 3
    MAX_LOCATIONS_LIMIT = 10

    @classmethod
    def read_cycle_parks(cls, cycleparks_url: str):
        cache_file_name = 'cycleparks.json'
        if not os.path.exists(cache_file_name):
            logger.info(
                'Cycle park json is not cached; loading from %s',
                cycleparks_url)
            req = urllib.request.Request(
                cycleparks_url, headers={
                    'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as url:
                data = json.load(url)
                cls.location_data = data['features']
                logger.info(
                    'Loaded cycle parks data from %s; Saving to %s',
                    cycleparks_url,
                    cache_file_name)
                with open(cache_file_name, 'w') as f:
                    json.dump(data, f, indent=2)

        else:
            with open(cache_file_name) as f:
                cls.location_data = json.load(f)['features']
        cls.location_data = [
            entry for entry in cls.location_data if entry['properties']['PRK_HANGAR'] != 'TRUE']
        coords = np.radians(
            [list(reversed(entry["geometry"]['coordinates'])) for entry in cls.location_data])
        cls.location_tree = BallTree(coords, metric="haversine")

    @classmethod
    def get_nearest_cycleparks(cls, lat, lon, k=DEFAULT_LOCATIONS_LIMIT):
        target_rad = np.radians([lat, lon]).reshape(1, -1)
        distances, indices = cls.location_tree.query(target_rad, k=k)
        distances_meters = distances[0] * 6371000  # Convert to meters
        closest_entries = [cls.location_data[i] for i in indices[0]]
        return closest_entries, distances_meters
