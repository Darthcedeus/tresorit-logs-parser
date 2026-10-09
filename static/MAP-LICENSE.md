The country outlines in `world-map.json` are simplified from Natural Earth's
1:50 million Admin 0 Countries dataset. They contain public geography only,
never Tresorit log data. The projection is equirectangular.

Natural Earth data is in the public domain:
https://www.naturalearthdata.com/about/terms-of-use/

Source GeoJSON:
https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson

Regenerate with `python scripts/build_world_map.py <source.geojson>`.
Boundaries follow Natural Earth's de facto depiction and are simplified for
an overview; they do not express a position on disputed boundaries.
