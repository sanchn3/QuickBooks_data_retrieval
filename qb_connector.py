"""
qb_connector.py — QBXMLRP2 COM session manager.

IMPORTANT: Requires 32-bit Python and pywin32 installed.
QuickBooks Pro 2018 must be running with the company file open.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# QBXML version supported by QB 2018
QBXML_VERSION = "13.0"


class QBConnector:
    """Context manager that opens/closes a QuickBooks COM session."""

    def __init__(self, company_file: str = "", app_name: str = "QB Data Transfer"):
        self.company_file = company_file  # "" = use currently open file
        self.app_name = app_name
        self._rp = None      # RequestProcessor COM object
        self._ticket: str = ""

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self) -> "QBConnector":
        self.open_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False  # don't suppress exceptions

    # ── Session management ───────────────────────────────────────────────────

    def open_connection(self) -> None:
        """Initialise the QBXMLRP2 COM object and begin a QB session."""
        try:
            import win32com.client  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "pywin32 is not installed. Run: pip install pywin32\n"
                "Also ensure you are using 32-bit Python."
            ) from exc

        logger.info("Opening QuickBooks COM connection as '%s'", self.app_name)
        self._rp = win32com.client.Dispatch("QBXMLRP2.RequestProcessor")
        self._rp.OpenConnection2("", self.app_name, 1)  # 1 = localQBD

        # BeginSession mode 2 = qbFileOpenDoNotCare (use currently open file)
        self._ticket = self._rp.BeginSession(self.company_file, 2)
        logger.info("QuickBooks session opened (ticket=%s)", self._ticket[:8] + "...")

    def send_request(self, qbxml_str: str) -> str:
        """Send a QBXML request string and return the raw XML response."""
        if not self._ticket:
            raise RuntimeError("No open QB session. Call open_connection() first.")
        response = self._rp.ProcessRequest(self._ticket, qbxml_str)
        return response

    def close(self) -> None:
        """End the QB session and close the COM connection."""
        if self._rp is None:
            return
        try:
            if self._ticket:
                self._rp.EndSession(self._ticket)
                logger.info("QuickBooks session ended")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error ending QB session: %s", exc)
        finally:
            try:
                self._rp.CloseConnection()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error closing QB connection: %s", exc)
            self._rp = None
            self._ticket = ""


def test_connection(company_file: str = "", app_name: str = "QB Data Transfer") -> bool:
    """Quick connectivity test — opens a session then immediately closes it."""
    try:
        with QBConnector(company_file=company_file, app_name=app_name):
            logger.info("Connection test passed.")
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Connection test FAILED: %s", exc)
        return False
