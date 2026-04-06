import socket
import unittest
from argparse import Namespace
from types import SimpleNamespace
from unittest import mock

import main


class StartApiServerTests(unittest.TestCase):
    def test_start_api_server_raises_when_port_is_already_in_use(self) -> None:
        config = SimpleNamespace(log_level="INFO")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            occupied_port = sock.getsockname()[1]

            with self.assertRaises(RuntimeError):
                main.start_api_server("127.0.0.1", occupied_port, config)

    def test_main_returns_error_when_serve_only_startup_fails(self) -> None:
        args = Namespace(
            debug=False,
            dry_run=False,
            stocks=None,
            no_notify=False,
            single_notify=False,
            workers=None,
            schedule=False,
            overnight_brief=False,
            no_run_immediately=False,
            market_review=False,
            no_market_review=False,
            force_run=False,
            webui=False,
            webui_only=False,
            serve=False,
            serve_only=True,
            port=8000,
            host="127.0.0.1",
            no_context_snapshot=False,
            backtest=False,
            backtest_code=None,
            backtest_days=None,
            backtest_force=False,
        )
        config = SimpleNamespace(
            log_dir="logs",
            webui_enabled=False,
            schedule_enabled=False,
            run_immediately=False,
            log_level="INFO",
            validate=lambda: [],
        )

        with (
            mock.patch.object(main, "parse_arguments", return_value=args),
            mock.patch.object(main, "get_config", return_value=config),
            mock.patch.object(main, "setup_logging"),
            mock.patch.object(main, "prepare_webui_frontend_assets", return_value=True),
            mock.patch.object(main, "start_api_server", side_effect=RuntimeError("port busy")),
            mock.patch.object(main, "time") as mocked_time,
        ):
            mocked_time.sleep.side_effect = AssertionError("serve-only loop should not run on startup failure")
            self.assertEqual(main.main(), 1)


if __name__ == "__main__":
    unittest.main()
