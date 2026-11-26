"""HTTP transport with bounded retries."""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpClient:
    """Retrieve bytes with a finite timeout and retry budget."""

    def __init__(self, timeout: float = 30, attempts: int = 3) -> None:
        """Configure transport.

        Args:
            timeout: Timeout in seconds per request.
            attempts: Maximum attempts per request.
        """
        # Store bounded transport settings.
        self.timeout: float = timeout
        self.attempts: int = attempts

    def request(self, request: Request) -> bytes:
        """Execute a request, retrying temporary failures.

        Args:
            request: Prepared HTTP request.

        Returns:
            Response bytes.

        Raises:
            OSError: When the request fails or exhausts retries.
        """
        # Retry only transient errors within the delay budget.
        for attempt in range(self.attempts):
            retry_delay: float = float(2 ** attempt)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload: bytes = response.read()
                return payload
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == self.attempts - 1:
                    raise OSError(f"HTTP {error.code} from {request.host}") from error
                retry_after: str | None = error.headers.get("Retry-After")
                if retry_after:
                    try:
                        retry_delay = float(retry_after)
                    except ValueError:
                        try:
                            retry_date: datetime = parsedate_to_datetime(retry_after)
                            retry_delay = (retry_date - datetime.now(timezone.utc)).total_seconds()
                        except (ValueError, TypeError):
                            pass
                if retry_delay > 30:
                    raise OSError("Server requested a retry beyond the 30-second delay budget") from error
            except (URLError, TimeoutError) as error:
                if attempt == self.attempts - 1:
                    raise OSError(f"Request to {request.host} failed: {error}") from error
            time.sleep(max(0, retry_delay))
        raise OSError("HTTP retry budget exhausted")
