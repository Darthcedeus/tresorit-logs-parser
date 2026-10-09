import unittest
import io

from analysis import analyze
from app import app
from Parser import Parser
from locations import location_sources, recorded_location
from test_dashboard import export


class LocationTests(unittest.TestCase):
    def test_activity_normalization_and_missing_fields(self):
        source = location_sources('link_activity', ['Country', 'City', 'IpAddress'])[0]
        self.assertEqual(recorded_location({'Country': ' nl ', 'City': ' Synthetic City '}, source),
                         {'country': 'NL', 'city': 'Synthetic City'})
        self.assertEqual(recorded_location({'Country': 'N/A', 'City': 'N/A'}, source), {'country': '', 'city': ''})
        self.assertEqual(recorded_location({'Country': 'UK'}, source)['country'], 'GB')
        self.assertEqual(recorded_location({'Country': '<script>'}, source)['country'], '')

    def test_device_sources_and_multicomponent_location(self):
        sources = location_sources('device_status', ['Latest Activity Location', 'Creation Location', 'Revocation Location'])
        self.assertEqual([item['key'] for item in sources], ['latest', 'creation', 'revocation'])
        self.assertEqual(recorded_location({'Latest Activity Location': 'Synthetic City, Synthetic Region, us'}, sources[0]),
                         {'country': 'US', 'city': 'Synthetic City, Synthetic Region'})
        self.assertEqual(recorded_location({'Creation Location': 'N/A'}, sources[1]), {'country': '', 'city': ''})
        self.assertEqual(recorded_location({'Revocation Location': 'Synthetic City'}, sources[2]),
                         {'country': '', 'city': 'Synthetic City'})

    def test_optional_columns_and_snapshot_separation(self):
        self.assertEqual(location_sources('device_status', []), [])
        self.assertEqual(location_sources('folder_members', ['Country']), [])
        report = Parser().parse(export('device_status', [{'Email': 'synthetic@example.com',
            'Latest Activity Location': 'Synthetic One, NL', 'Creation Location': 'Synthetic Two, GB',
            'Revocation Location': 'N/A'}], ['Latest Activity Location', 'Creation Location', 'Revocation Location']))
        result = analyze([report])['reports'][0]
        geo = result['rows'][0]['locations']
        self.assertEqual(geo['latest']['country'], 'NL')
        self.assertEqual(geo['creation']['country'], 'GB')
        self.assertEqual(geo['revocation']['country'], '')
        self.assertEqual(result['rows'][0]['cells']['Email'], 'synthetic@example.com')

    def test_activity_missing_country_retained_and_safe_serialization(self):
        report = Parser().parse(export('link_activity', [
            {'Link ID': 'synthetic', 'Country': 'NL', 'City': '</script><script>synthetic</script>'},
            {'Link ID': 'synthetic-unknown', 'Country': 'N/A'}], ['Country', 'City']))
        result = analyze([report])['reports'][0]
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual(result['rows'][1]['locations']['activity']['country'], '')
        self.assertEqual(result['rows'][0]['locations']['activity']['city'], '</script><script>synthetic</script>')
        response = app.test_client().post('/process', data={'file': (io.BytesIO(export('link_activity', [
            {'Link ID': 'synthetic', 'Country': 'NL', 'City': '</script><script>synthetic</script>'}], ['Country', 'City'])), 'synthetic.csv')})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('</script><script>synthetic', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
