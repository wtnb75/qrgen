import unittest
from unittest.mock import patch, ANY
from click.testing import CliRunner
from qrgen.main import cli


class TestCLI(unittest.TestCase):
    def test_help(self):
        res = CliRunner().invoke(cli, ["--help"])
        self.assertEqual(0, res.exit_code)
        self.assertIn("server", res.output)
        self.assertIn("--version", res.output)

    def test_version(self):
        res = CliRunner().invoke(cli, ["--version"])
        self.assertEqual(0, res.exit_code)
        self.assertIn("qrgen", res.output)
        self.assertIn("version", res.output)

    def test_bad_subcommand(self):
        res = CliRunner().invoke(cli, ["notexists", "--help"])
        self.assertEqual(2, res.exit_code)
        self.assertIn("Usage: ", res.output)

    def test_server(self):
        with patch("uvicorn.run") as run:
            res = CliRunner().invoke(
                cli, ["server", "--host", "1.2.3.4", "--port", "3000"])
            run.assert_called_once_with(
                ANY, host="1.2.3.4", port=3000, log_config=ANY)
            self.assertEqual(0, res.exit_code)

    def test_server_verbose(self):
        from logging import getLogger, DEBUG
        with patch("uvicorn.run"):
            res = CliRunner().invoke(cli, ["server", "--verbose"])
            self.assertEqual(DEBUG, getLogger().level)
            self.assertEqual(0, res.exit_code)

    def test_server_quiet(self):
        from logging import getLogger, WARNING
        with patch("uvicorn.run"):
            CliRunner().invoke(cli, ["server", "--quiet"])
            self.assertEqual(WARNING, getLogger().level)

    def test_server_normal(self):
        from logging import getLogger, INFO
        with patch("uvicorn.run"):
            CliRunner().invoke(cli, ["server"])
            self.assertEqual(INFO, getLogger().level)

    def test_server_help(self):
        res = CliRunner().invoke(cli, ["server", "--help"])
        self.assertEqual(0, res.exit_code)
        self.assertIn("--verbose", res.output)
        self.assertIn("--quiet", res.output)
        self.assertIn("--host", res.output)
        self.assertIn("--port", res.output)
