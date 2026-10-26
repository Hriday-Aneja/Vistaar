from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearby(origin, others, radius_km: float):
    found = []
    for other in others:
        if other.id == origin.id:
            continue
        distance = haversine_km(origin.lat, origin.lng, other.lat, other.lng)
        if distance <= radius_km:
            found.append((other, round(distance, 2)))
    return sorted(found, key=lambda pair: pair[1])
