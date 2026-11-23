"""Real bundled server: permissions, streaming, indexing, moves, and private writes."""
import base64
import importlib.util
import json
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='mediawrt-test-')
        cls.base = Path(cls.tmp.name)
        cls.executable = cls.base / 'mediawrt.py'
        shutil.copyfile(ROOT / 'mediawrt.py', cls.executable)
        cls.media = cls.base / 'movies'
        cls.media.mkdir()
        (cls.media / 'Target').mkdir()
        (cls.media / 'Movie.mp4').write_bytes(b'0123456789' * 100)
        (cls.media / 'Movie.cs.srt').write_text('subtitle')
        (cls.media / '.private.mp4').write_bytes(b'secret')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.url = 'http://127.0.0.1:' + str(cls.port)
        cls.cfg = cls.base / 'config.json'
        cls.cfg.write_text(json.dumps({'media': str(cls.media), 'state_dir': str(cls.base / 'state'),
            'port': cls.port, 'reserve_private_state': True,
            'runtime_dir': str(cls.base / 'runtime'), 'temp_dir': str(cls.base / 'temp'),
            'database_dir': str(cls.media / '.mediawrt/database'),
            'users': [{'name': 'editor', 'password': 'test-password', 'permissions': 'rwm'}]}))
        cls.start()

    @classmethod
    def start(cls):
        cls.output = (cls.base / 'server.log').open('a')
        cls.process = subprocess.Popen([sys.executable, '-I', '-S', str(cls.executable), '--config', str(cls.cfg)],
                                      stdout=cls.output, stderr=cls.output, cwd=cls.base)
        for _ in range(200):
            try:
                if cls.api('movies')['total'] >= 1 and not cls.api('status')['scanning']:
                    return
            except (OSError, ValueError):
                pass
            if cls.process.poll() is not None:
                break
            time.sleep(.1)
        cls.stop()
        raise AssertionError((cls.base / 'server.log').read_text(errors='replace'))

    @classmethod
    def stop(cls):
        cls.process.terminate()
        try: cls.process.wait(10)
        except subprocess.TimeoutExpired: cls.process.kill(); cls.process.wait()
        cls.output.close()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    @classmethod
    def request(cls, path, method='GET', data=None, editor=False, headers=None):
        hdr = dict(headers or {})
        if editor:
            hdr['Authorization'] = 'Basic ' + base64.b64encode(b'editor:test-password').decode()
        return urllib.request.urlopen(urllib.request.Request(cls.url + path, data=data, method=method, headers=hdr), timeout=15)

    @classmethod
    def api(cls, path, **kwargs):
        with cls.request('/.cpr/media/v1/' + path, **kwargs) as res:
            return json.load(res)

    def test_01_catalog_and_range(self):
        items = self.api('movies')['items']
        self.assertEqual([i['name'] for i in items], ['Movie.mp4'])
        self.assertEqual(len(items[0]['id']), 32)
        with self.request('/media/Movie.mp4', headers={'Range': 'bytes=10-19'}) as res:
            self.assertEqual(res.status, 206)
            self.assertEqual(res.read(), b'0123456789')
        for path in ['/media/', '/app/js/app.js', '/app/js/translations.js', '/app/css/base.css',
                     '/media/?native=1', '/.cpr/browser.js', '/.cpr/browser.css', '/.cpr/deps/mini-fa.woff']:
            with self.request(path) as res: self.assertEqual(res.status, 200)

    def test_02_permission_and_origin(self):
        self.assertFalse(self.api('config')['upload'])
        self.assertTrue(self.api('config', editor=True)['move'])
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/media/rejected.mp4', 'PUT', b'no')
        for headers in [{'X-Copyparty-Media': '1'}, {}, {'X-Copyparty-Media': '1', 'Origin': 'http://evil.invalid'}]:
            with self.assertRaises(urllib.error.HTTPError):
                self.api('scan', method='POST', data=b'', headers=headers)
        with self.assertRaises(urllib.error.HTTPError):
            self.api('move-preview?source=Movie.mp4&target=Target/Movie.mp4')
        self.assertFalse((self.media / 'rejected.mp4').exists())

    def test_03_move_sidecars_identity_and_conflicts(self):
        item = self.api('movies')['items'][0]
        params = urllib.parse.urlencode({'source': 'Movie.mp4', 'target': 'Target/Renamed.mp4'})
        plan = self.api('move-preview?' + params, editor=True)
        self.assertEqual(len(plan['files']), 2)
        result = self.api('move?token=' + plan['token'], method='POST', data=b'', editor=True,
                          headers={'X-Copyparty-Media': '1'})
        self.assertEqual(len(result['completed']), 2)
        self.assertTrue((self.media / 'Target/Renamed.cs.srt').exists())
        items = self.api('movies?ids=' + item['id'])['items']
        self.assertEqual(items[0]['path'], 'Target/Renamed.mp4')
        with self.assertRaises(urllib.error.HTTPError):
            self.api('move?token=' + plan['token'], method='POST', data=b'', editor=True,
                     headers={'X-Copyparty-Media': '1'})
        with self.assertRaises(urllib.error.HTTPError):
            self.api('move-preview?source=Target/Renamed.mp4&target=Target/Renamed.mp4', editor=True)
        with self.assertRaises(urllib.error.HTTPError):
            self.api('move-preview?source=Target/Renamed.mp4&target=../escaped.mp4', editor=True)

    def test_04_private_state_and_upload(self):
        with self.request('/media/Uploaded.mp4', 'PUT', b'uploaded', editor=True) as res:
            self.assertLess(res.status, 300)
        self.assertEqual((self.media / 'Uploaded.mp4').read_bytes(), b'uploaded')
        self.assertFalse((self.media / '.hist').exists())
        self.assertTrue(list((self.media / '.mediawrt/database').rglob('up2k.db')))
        self.assertTrue((self.media / '.mediawrt/database/library-indexed-v1').exists())
        for path in ['/media/.mediawrt/', '/media/.mediawrt/database/library-indexed-v1']:
            with self.assertRaises(urllib.error.HTTPError): self.request(path)
            with self.assertRaises(urllib.error.HTTPError): self.request(path, editor=True)
        self.assertFalse(list((self.base / 'state/logs').iterdir()))

    def test_05_restart_does_not_scan(self):
        self.stop()
        (self.media / 'External.mp4').write_bytes(b'external')
        self.start()
        self.assertEqual(self.api('movies?q=External')['total'], 0)
        self.api('scan', method='POST', data=b'', editor=True, headers={'X-Copyparty-Media': '1'})
        for _ in range(100):
            if self.api('movies?q=External')['total'] == 1:
                break
            time.sleep(.1)
        self.assertEqual(self.api('movies?q=External')['total'], 1)

    def center(self, path, **kwargs):
        with self.request('/.cpr/media/v2/' + path, **kwargs) as res:
            return json.load(res)

    def scan(self):
        for _ in range(100):
            if not self.api('status')['scanning']: break
            time.sleep(.1)
        self.api('scan', method='POST', data=b'', editor=True, headers={'X-Copyparty-Media': '1'})
        for _ in range(100):
            if not self.api('status')['scanning']: return
            time.sleep(.1)
        self.fail('Scan timeout')

    def test_06_media_center_catalog_and_subtitles(self):
        (self.media / 'Music/Artist/Album').mkdir(parents=True)
        (self.media / 'Music/Artist/Album/01 Song.mp3').write_bytes(b'music')
        (self.media / 'Show S01E02.mp4').write_bytes(b'episode')
        (self.media / 'Show S01E02.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nSubtitle\n')
        (self.media / 'Photo.jpg').write_bytes(b'image')
        self.scan()
        self.assertEqual(self.api('movies?q=Show')['total'], 1)
        movies = self.center('catalog?kind=movies')
        self.assertNotIn('Show S01E02.mp4', [x['name'] for x in movies['items']])
        shows = self.center('catalog?kind=series')['items']
        self.assertTrue(shows, self.center('catalog?kind=all'))
        show = shows[0]
        self.assertEqual((show['series'], show['season'], show['episode']), ('Show', 1, 2))
        self.assertIsNotNone(show['added'])
        albums = self.center('catalog?kind=music&group=album')['items']
        self.assertEqual((albums[0]['title'], albums[0]['artist'], albums[0]['count']), ('Album', 'Artist', 1))
        self.assertEqual(self.center('catalog?kind=pictures')['total'], 1)
        detail = self.center('detail?id=' + show['id'])
        self.assertEqual(detail['subtitles'][0]['path'], 'Show S01E02.srt')
        with self.request('/.cpr/media/v2/subtitle?path=Show%20S01E02.srt') as res:
            text = res.read().decode()
            self.assertTrue(text.startswith('WEBVTT'))
            self.assertIn('00:00:01.000', text)
        with self.request('/media/') as res:
            self.assertIn(b'/app/js/app.js', res.read())
        with self.request('/app/js/app.js') as res:
            self.assertIn(b'MediaWrt 2', res.read())

    def test_07_center_write_permissions_and_folder_move(self):
        self.assertFalse(self.center('config', editor=True)['admin'])
        self.assertEqual(self.center('config', editor=True)['paths'], {})
        for path in ['mkdir?path=Created', 'override?id=anything&title=Changed']:
            with self.assertRaises(urllib.error.HTTPError):
                self.center(path, method='POST', data=b'', editor=True)
        with self.request('/.cpr/media/v2/mkdir?path=Created', 'POST', b'', editor=True,
                          headers={'X-MediaWrt':'1'}) as res:
            self.assertEqual(res.status, 201)
        self.assertTrue((self.media / 'Created').is_dir())
        with self.assertRaises(urllib.error.HTTPError):
            self.center('override?id=anything&title=Changed', method='POST', data=b'', editor=True,
                        headers={'X-MediaWrt':'1'})
        for path in ['subtitle?path=../secret.srt', 'artwork?path=.mediawrt/database/sessions.db']:
            with self.assertRaises(urllib.error.HTTPError): self.center(path)
        plan = self.api('move-preview?source=Music&target=Created/Music', editor=True)
        self.api('move?token=' + plan['token'], method='POST', data=b'', editor=True,
                 headers={'X-Copyparty-Media':'1'})
        self.assertTrue((self.media / 'Created/Music/Artist/Album/01 Song.mp3').is_file())

    def test_08_sidecar_selection(self):
        (self.media / 'Choice.mp4').write_bytes(b'test')
        (self.media / 'Choice.srt').write_bytes(b'test')
        self.scan()
        plan = self.api('move-preview?source=Choice.mp4&target=Target/Choice.mp4', editor=True)
        query = urllib.parse.urlencode({'token':plan['token'], 'include':json.dumps(['Choice.mp4'])})
        self.api('move?' + query, method='POST', data=b'', editor=True, headers={'X-Copyparty-Media':'1'})
        self.assertTrue((self.media / 'Choice.srt').is_file())
        self.assertTrue((self.media / 'Target/Choice.mp4').is_file())

    def test_09_palette_assets_and_private_routes(self):
        for palette in (ROOT / 'src/web/css/palettes').glob('*.css'):
            with self.request('/app/css/palettes/' + palette.name) as response:
                self.assertIn('text/css', response.headers['Content-Type'])
                self.assertEqual(response.read(), palette.read_text(encoding='utf-8').encode())
        for route in ('/app/server/launcher.py', '/app/../library.py'):
            with self.assertRaises(urllib.error.HTTPError):
                self.request(route)

class Configuration(unittest.TestCase):
    def test_private_state_cannot_be_shared(self):
        spec = importlib.util.spec_from_file_location('launcher', ROOT / 'src/server/launcher.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps({'media': tmp, 'state_dir': tmp}))
            with self.assertRaises(ValueError): launcher.configuration(path)

    def test_paths_follow_config_and_mount_fails_closed(self):
        spec = importlib.util.spec_from_file_location('launcher', ROOT / 'src/server/launcher.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / 'media').mkdir()
            path = base / 'config.json'
            path.write_text(json.dumps({'media': 'media'}))
            _, media, paths = launcher.configuration(path)
            self.assertEqual(media, base / 'media')
            self.assertEqual(paths['database'], base / 'state/database')
            self.assertFalse((base / 'state').exists())
            self.assertNotIn(base / 'state', paths['runtime'].parents)
            path.write_text(json.dumps({'media': 'media', 'required_mount': 'media'}))
            with self.assertRaises(ValueError): launcher.configuration(path)

if __name__ == '__main__':
    unittest.main()
