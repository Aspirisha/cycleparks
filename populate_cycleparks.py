#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import urllib.request
from datetime import datetime

from sqlalchemy import select, func

from cycleparks.db import init_db, get_session
from cycleparks.models import CyclePark

logger = logging.getLogger(__name__)


async def populate_cycleparks():
    # Load config (assuming config.yml is available)
    import yaml

    with open("config.yml") as f:
        config = yaml.safe_load(f)

    cycleparks_url = config["cycleparks_url"]
    cache_file_name = "cycleparks.json"

    # Download JSON if not cached
    if not os.path.exists(cache_file_name):
        logger.info("Cycle park json is not cached; loading from %s", cycleparks_url)
        req = urllib.request.Request(
            cycleparks_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req) as url:
            data = json.load(url)
            logger.info(
                "Loaded cycle parks data from %s; Saving to %s",
                cycleparks_url,
                cache_file_name,
            )
            with open(cache_file_name, "w") as f:
                json.dump(data, f, indent=2)
    else:
        with open(cache_file_name) as f:
            data = json.load(f)

    # Initialize DB
    init_db(config["postgres"])

    async with get_session() as session:
        result = await session.execute(select(func.count()).select_from(CyclePark))
        count = result.scalar()
        if count > 0:
            print("Cycleparks table already populated, skipping.")
            return

        for feature in data["features"]:
            props = feature["properties"]
            coords = feature["geometry"]["coordinates"]

            # Parse boolean strings
            def parse_bool(s):
                return s.upper() == "TRUE"

            # Parse date
            svdate = None
            if props.get("SVDATE"):
                try:
                    svdate = datetime.strptime(props["SVDATE"], "%Y-%m-%d").date()
                except ValueError:
                    pass  # Leave as None if invalid

            cyclepark = CyclePark(
                feature_id=props["FEATURE_ID"],
                svdate=svdate,
                prk_carr=parse_bool(props["PRK_CARR"]),
                prk_cover=parse_bool(props["PRK_COVER"]),
                prk_secure=parse_bool(props["PRK_SECURE"]),
                prk_locker=parse_bool(props["PRK_LOCKER"]),
                prk_sheff=parse_bool(props["PRK_SHEFF"]),
                prk_mstand=parse_bool(props["PRK_MSTAND"]),
                prk_pstand=parse_bool(props["PRK_PSTAND"]),
                prk_hoop=parse_bool(props["PRK_HOOP"]),
                prk_post=parse_bool(props["PRK_POST"]),
                prk_buterf=parse_bool(props["PRK_BUTERF"]),
                prk_wheel=parse_bool(props["PRK_WHEEL"]),
                prk_hangar=parse_bool(props["PRK_HANGAR"]),
                prk_tier=parse_bool(props["PRK_TIER"]),
                prk_other=parse_bool(props["PRK_OTHER"]),
                prk_provis=props.get("PRK_PROVIS"),
                prk_cpt=props.get("PRK_CPT"),
                borough=props.get("BOROUGH"),
                photo1_url=props.get("PHOTO1_URL"),
                photo2_url=props.get("PHOTO2_URL"),
                longitude=coords[0],
                latitude=coords[1],
            )

            session.add(cyclepark)

        await session.commit()
        print(f"Inserted {len(data['features'])} cycleparks into the database.")


if __name__ == "__main__":
    asyncio.run(populate_cycleparks())
