import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from analysis import analyze
from app import app, BoundedRequest
from import_limits import DEFAULT_LIMITS, ImportBudget, ImportLimitError, OutputBudget
from Parser import Parser, DuplicateReport
from test_dashboard import export, payload


class SecurityLimitsTests(unittest.TestCase):
    def test_compose_default_custom_port_and_local_override(self):
        root = Path(__file__).resolve().parents[1]
        compose = (root / 'docker-compose.yml').read_text()
        self.assertIn('"${APP_BIND_ADDRESS:-0.0.0.0}:${APP_PORT:-5000}:5000"', compose)
        for port in ['5000', '8080']:
            for address in ['0.0.0.0', '127.0.0.1']:
                rendered = compose.replace('${APP_PORT:-5000}', port).replace('${APP_BIND_ADDRESS:-0.0.0.0}', address)
                self.assertIn(f'"{address}:{port}:5000"', rendered)
        self.assertNotIn('ports:', (root / 'docker-compose.local.yml').read_text())
        for bound in ['mem_limit: 512m', 'cpus: 1.0', 'pids_limit: 128']:
            self.assertIn(bound, compose)

    def parse(self, data, **limits):
        return Parser().parse(data, budget=ImportBudget(replace(DEFAULT_LIMITS, **limits)))

    def test_compact_row_attack_default_boundary(self):
        header = export('folder_members')
        self.assertEqual(len(Parser().parse(header + b'a,,,\n' * 20_000)['rows']), 20_000)
        with self.assertRaisesRegex(ImportLimitError, 'row limit'):
            Parser().parse(header + b'a,,,\n' * 20_001)

    def test_blank_records_and_multiline_values(self):
        header = export('folder_members')
        self.assertEqual(self.parse(header + b'\n\n', max_rows_per_file=2)['rows'], [])
        with self.assertRaises(ImportLimitError):
            self.parse(header + b'\n\n\n', max_rows_per_file=2)
        data = export('folder_members', [{'User': 'a\nb', 'Tresor': 'x'}])
        self.assertEqual(self.parse(data, max_rows_per_file=1)['rows'][0]['User'], 'a\nb')

    def test_column_header_and_field_boundaries(self):
        self.parse(export('folder_members', extra=['x' * 128]))
        with self.assertRaisesRegex(ImportLimitError, 'column-name'):
            self.parse(export('folder_members', extra=['x' * 129]))
        self.parse(export('folder_members'), max_columns=4)
        with self.assertRaisesRegex(ImportLimitError, 'column limit'):
            self.parse(export('folder_members', extra=['extra']), max_columns=4)
        self.parse(export('folder_members', [{'User': 'x' * 8192}]))
        with self.assertRaisesRegex(ImportLimitError, 'field-length'):
            self.parse(export('folder_members', [{'User': 'x' * 8193}]))

    def test_delimiter_flood_rejected_before_csv_materialization(self):
        from Parser import bounded_lines
        with self.assertRaisesRegex(ImportLimitError, 'column limit'):
            next(bounded_lines(',' * 1_000_000, 64))
        with self.assertRaisesRegex(ImportLimitError, 'column limit'):
            Parser().parse(export('folder_members') + b',' * 1_000_000)
        value = 'commas,,, "quoted"\r\nmore,,,commas'
        data = export('folder_members', [{'User': value}])
        self.assertEqual(self.parse(data, max_columns=4)['rows'][0]['User'], value)

    def test_shared_budget_exact_boundaries(self):
        data = export('folder_members', [{'User': 'a'}])
        initial = ImportBudget()
        Parser().parse(data, budget=initial)
        for setting, amount in [('max_total_bytes', len(data)), ('max_total_rows', 1),
                                ('max_total_cells', initial.cells), ('max_total_chars', initial.chars),
                                ('max_files', 1)]:
            with self.subTest(setting=setting):
                budget = ImportBudget(replace(DEFAULT_LIMITS, **{setting: amount}))
                Parser().parse(data, budget=budget)
                with self.assertRaises(ImportLimitError) as caught:
                    Parser().parse(data, budget=budget)
                self.assertTrue(caught.exception.fatal)
        self.parse(data, max_file_bytes=len(data))
        with self.assertRaises(ImportLimitError):
            self.parse(data, max_file_bytes=len(data) - 1)

    def test_duplicates_rejected_before_body_and_failed_work_charged(self):
        budget = ImportBudget()
        with self.assertRaises(DuplicateReport):
            Parser().parse(export('folder_members') + b'"unterminated', budget=budget,
                           skip_kinds={'folder_members'})
        self.assertEqual(budget.rows, 0)
        self.assertGreater(budget.bytes, 0)
        with self.assertRaises(ValueError):
            Parser().parse(export('folder_members') + b'a,,,\nbad,row\n', budget=budget)
        self.assertEqual(budget.rows, 2)

    def test_legacy_entry_point_has_same_row_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, 'links.csv')
            source.write_bytes(export('shared_links') + b'a,,,,,,,\n' * 20_001)
            with self.assertRaisesRegex(ImportLimitError, 'row limit'):
                Parser().parseSharedLinks(source)

    def test_output_budget_counts_html_escapes_and_join_expansion(self):
        budget = OutputBudget(replace(DEFAULT_LIMITS, max_output_chars=100))
        with self.assertRaises(ImportLimitError):
            budget.add('<' * 20)
        links = Parser().parse(export('shared_links', [{'Link ID': 'a', 'Active': 'x' * 1000}]))
        events = Parser().parse(export('link_activity', [{'Link ID': 'a'}] * 20))
        self.assertEqual(len(analyze([links, events])['reports'][1]['rows']), 20)
        with self.assertRaisesRegex(ImportLimitError, 'output limit'):
            analyze([links, events], limits=replace(DEFAULT_LIMITS, max_output_chars=6000))


class SecurityRouteTests(unittest.TestCase):
    def setUp(self):
        original = app.config.copy()
        self.addCleanup(lambda: app.config.update(original))
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_rejected_file_is_atomic_and_previous_good_file_survives(self):
        app.config['IMPORT_LIMITS'] = replace(DEFAULT_LIMITS, max_rows_per_file=1)
        response = self.client.post('/process', data={'file': [
            (io.BytesIO(export('device_status')), 'good.csv'),
            (io.BytesIO(export('folder_members') + b'a,,,\n' * 2), 'bad.csv')]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['kind'] for r in payload(response)['reports']], ['device_status'])
        self.assertIn('row limit', response.get_data(as_text=True))

    def test_output_overflow_returns_error_without_partial_dataset(self):
        app.config['IMPORT_LIMITS'] = replace(DEFAULT_LIMITS, max_output_chars=100)
        response = self.client.post('/process', data={'file': (io.BytesIO(export('folder_members')), 'a.csv')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload(response)['reports'], [])
        self.assertIn('output limit', response.get_data(as_text=True))

    def test_multipart_limit_precedes_csv_parsing(self):
        with patch.object(BoundedRequest, 'max_form_parts', 2), patch.object(Parser, 'parse') as parse:
            response = self.client.post('/process', data={'file': [
                (io.BytesIO(export('folder_members')), f'{i}.csv') for i in range(3)]})
        self.assertEqual(response.status_code, 413)
        parse.assert_not_called()

    def test_valid_upload_spanning_multiple_multipart_chunks(self):
        data = export('folder_members', [{'User': 'user@example.com', 'Tresor': 'Folder',
                                          'Subscription Member': 'Yes', 'Permission': 'Owner'}] * 2000)
        self.assertGreater(len(data), 64 * 1024)
        response = self.client.post('/process', data={'file': (io.BytesIO(data), 'members.csv')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload(response)['reports'][0]['rows']), 2000)

    def test_local_limits_and_older_duplicate_body_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            app.config['LOG_DATA_DIR'] = tmp
            Path(tmp, 'members_z.csv').write_bytes(export('folder_members'))
            Path(tmp, 'members_a.csv').write_bytes(export('folder_members') + b'"unterminated')
            response = self.client.post('/load-local')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload(response)['reports'][0]['filename'], 'members_z.csv')
            self.assertNotIn('Invalid CSV', response.get_data(as_text=True))
            app.config['IMPORT_LIMITS'] = replace(DEFAULT_LIMITS, max_files=1)
            response = self.client.post('/load-local')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(payload(response)['reports'], [])


if __name__ == '__main__':
    unittest.main()
