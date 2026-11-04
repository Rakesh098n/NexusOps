import unittest

from streamlit.testing.v1 import AppTest


class ThemeTests(unittest.TestCase):
    def test_light_and_dark_palettes_rerender(self):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        self.assertFalse(list(app.exception))
        self.assertIn("color-scheme: light", app.markdown[0].value)

        app.toggle[0].set_value(True).run()
        self.assertFalse(list(app.exception))
        self.assertTrue(app.toggle[0].value)
        self.assertIn("color-scheme: dark", app.markdown[0].value)
        self.assertIn("#111915", app.markdown[0].value)

        app.toggle[0].set_value(False).run()
        self.assertFalse(app.toggle[0].value)
        self.assertIn("color-scheme: light", app.markdown[0].value)


if __name__ == "__main__":
    unittest.main()