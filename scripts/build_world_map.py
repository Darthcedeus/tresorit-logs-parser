"""Build the offline map from Natural Earth's public 50m country GeoJSON.

Usage: python scripts/build_world_map.py /path/to/ne_50m_admin_0_countries.geojson
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson
Natural Earth data is public domain. This script never reads application logs.
"""

import argparse
import json
import math
from pathlib import Path


def simplify(points, tolerance=0.12):
    if len(points) <= 3:
        return points
    start, end = points[0], points[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = dx * dx + dy * dy
    largest, index = 0, 0
    for i, point in enumerate(points[1:-1], 1):
        t = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length)) if length else 0
        distance = math.hypot(point[0] - start[0] - t * dx, point[1] - start[1] - t * dy)
        if distance > largest:
            largest, index = distance, i
    if largest > tolerance:
        return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)
    return [start, end]


def project(point):
    return ((point[0] + 180) * 1000 / 360, (90 - point[1]) * 500 / 180)


def build(source):
    countries = []
    for feature in source['features']:
        p, geometry = feature['properties'], feature['geometry']
        code = p['ISO_A2_EH'] if len(p['ISO_A2_EH']) == 2 else p['ADM0_A3']
        polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        paths = []
        for polygon in polygons:
            for ring in polygon:
                points = simplify(ring)
                if len(points) < 4:
                    points = ring
                # GeoJSON is already split at the antimeridian.
                projected = [project(point) for point in points]
                paths.append('M' + 'L'.join(f'{x:.2f},{y:.2f}' for x, y in projected) + 'Z')
        x, y = project([p['LABEL_X'], p['LABEL_Y']])
        countries.append({'code': code, 'name': p['NAME_EN'] or p['ADMIN'],
                          'x': round(x, 2), 'y': round(y, 2), 'path': ''.join(paths)})
    return {'width': 1000, 'height': 500, 'countries': countries}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'static' / 'world-map.json')
    args = parser.parse_args()
    args.output.write_text(json.dumps(build(json.loads(args.source.read_text(encoding='utf-8'))), ensure_ascii=False,
                                      separators=(',', ':')) + '\n', encoding='utf-8')
