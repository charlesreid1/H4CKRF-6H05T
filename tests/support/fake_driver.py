"""Test double satisfying HackrfDriver's DriverProtocol surface.

Extracted here so Parts 5 and 6 stop duplicating the class in their own test
files. Import from ``tests/support/fake_driver.py`` via the
``fake_driver`` conftest fixture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

from hackrf_agent.domain.models import DeviceInfo


@dataclass
class FakeDriver:
    """Test double satisfying HackrfDriver's DriverProtocol surface.

    Records every call in ``.calls`` as ``(method_name, kwargs)`` tuples.
    Return values are configurable via attributes:
      - ``device_info``: what get_device_info() returns.
      - ``sweep_result``: what sweep_spectrum() returns.
      - ``capture_bytes``: what capture_iq() writes to out_path.
      - ``transmit_error``: if set, transmit_iq() raises this.
    """

    device_info: DeviceInfo = field(
        default_factory=lambda: DeviceInfo(
            serial="fake-serial",
            firmware_version="0.0-fake",
            board_revision="fake-r1",
            part_id="fake-pid",
        )
    )
    calls: list[tuple[str, dict]] = field(default_factory=list)
    sweep_result: tuple[npt.NDArray[np.float32], npt.NDArray[np.float64]] = field(
        default_factory=lambda: (
            np.zeros(4096, dtype=np.float32),
            np.arange(4096, dtype=np.float64),
        )
    )
    capture_bytes: bytes = b"\x00\x00" * 1024
    transmit_error: Exception | None = None

    async def get_device_info(self) -> DeviceInfo:
        self.calls.append(("get_device_info", {}))
        return self.device_info

    async def sweep_spectrum(self, **kw) -> tuple:
        self.calls.append(("sweep_spectrum", kw))
        return self.sweep_result

    async def capture_iq(self, *, out_path: Path, **kw) -> Path:
        self.calls.append(("capture_iq", {"out_path": out_path, **kw}))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(self.capture_bytes)
        return out_path

    async def transmit_iq(self, **kw) -> None:
        self.calls.append(("transmit_iq", kw))
        if self.transmit_error is not None:
            raise self.transmit_error
