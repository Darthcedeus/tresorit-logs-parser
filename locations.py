"""Read export-provided locations without geocoding or external IP lookups."""

import re

from Parser import MISSING


SOURCES = {
    "link_activity": (
        {"key": "activity", "label": "Link activity", "country": "Country", "city": "City", "ip": "IpAddress", "date": "Timestamp"},
    ),
    "device_status": (
        {"key": "latest", "label": "Latest device activity", "location": "Latest Activity Location", "ip": "Latest Activity IP Address", "date": "Latest Activity Date"},
        {"key": "creation", "label": "Device creation", "location": "Creation Location", "ip": "Creation IP Address", "date": "Creation Date"},
        {"key": "revocation", "label": "Device revocation", "location": "Revocation Location", "ip": "Revocation IP Address", "date": "Revocation Date"},
    ),
}


def location_sources(kind, columns):
    return [source for source in SOURCES.get(kind, ()) if source.get("country", source.get("location")) in columns]


def recorded_location(row, source):
    if "location" in source:
        raw = row.get(source["location"], "").strip()
        city, separator, country = raw.rpartition(",")
        if not separator:
            city, country = raw, ""
    else:
        country, city = row.get(source["country"], ""), row.get(source["city"], "")
    country, city = country.strip().upper(), city.strip()
    country = {"UK": "GB", "EL": "GR"}.get(country, country)
    if not re.fullmatch(r"[A-Z]{2}", country):
        country = ""
    if city.lower() in MISSING:
        city = ""
    return {"country": country, "city": city}
