# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=too-many-ancestors, unused-import

from logging import getLogger
from typing import Dict, Generator, Iterable, List, Optional, Union

# This kind of import is needed to avoid Sphinx errors.
import opentelemetry.sdk._metrics
from opentelemetry._metrics import CallbackT
from opentelemetry._metrics import Counter as APICounter
from opentelemetry._metrics import Histogram as APIHistogram
from opentelemetry._metrics import ObservableCounter as APIObservableCounter
from opentelemetry._metrics import ObservableGauge as APIObservableGauge
from opentelemetry._metrics import (
    ObservableUpDownCounter as APIObservableUpDownCounter,
)
from opentelemetry._metrics import UpDownCounter as APIUpDownCounter
from opentelemetry._metrics._internal.instrument import CallbackOptions
from opentelemetry.sdk._metrics._internal.measurement import Measurement
from opentelemetry.sdk.util.instrumentation import InstrumentationScope

_logger = getLogger(__name__)


_ERROR_MESSAGE = (
    "Expected ASCII string of maximum length 63 characters but got {}"
)


class _Synchronous:
    def __init__(
        self,
        name: str,
        instrumentation_scope: InstrumentationScope,
        measurement_consumer: "opentelemetry.sdk._metrics.MeasurementConsumer",
        unit: str = "",
        description: str = "",
    ):
        # pylint: disable=no-member
        is_name_valid, is_unit_valid = self._check_name_and_unit(name, unit)

        if not is_name_valid:
            raise Exception(_ERROR_MESSAGE.format(name))

        if not is_unit_valid:
            raise Exception(_ERROR_MESSAGE.format(unit))
        self.name = name.lower()
        self.unit = unit
        self.description = description
        self.instrumentation_scope = instrumentation_scope
        self._measurement_consumer = measurement_consumer
        super().__init__(name, unit=unit, description=description)


class _Asynchronous:
    def __init__(
        self,
        name: str,
        instrumentation_scope: InstrumentationScope,
        measurement_consumer: "opentelemetry.sdk._metrics.MeasurementConsumer",
        callbacks: Optional[Iterable[CallbackT]] = None,
        unit: str = "",
        description: str = "",
    ):
        # pylint: disable=no-member
        is_name_valid, is_unit_valid = self._check_name_and_unit(name, unit)

        if not is_name_valid:
            raise Exception(_ERROR_MESSAGE.format(name))

        if not is_unit_valid:
            raise Exception(_ERROR_MESSAGE.format(unit))
        self.name = name.lower()
        self.unit = unit
        self.description = description
        self.instrumentation_scope = instrumentation_scope
        self._measurement_consumer = measurement_consumer
        super().__init__(name, callbacks, unit=unit, description=description)

        self._callbacks: List[CallbackT] = []

        if callbacks is not None:

            for callback in callbacks:

                if isinstance(callback, Generator):

                    # advance generator to it's first yield
                    next(callback)

                    def inner(
                        options: CallbackOptions,
                        callback=callback,
                    ) -> Iterable[Measurement]:
                        try:
                            return callback.send(options)
                        except StopIteration:
                            return []

                    self._callbacks.append(inner)
                else:
                    self._callbacks.append(callback)

    def callback(
        self, callback_options: CallbackOptions
    ) -> Iterable[Measurement]:
        for callback in self._callbacks:
            try:
                for api_measurement in callback(callback_options):
                    yield Measurement(
                        api_measurement.value,
                        instrument=self,
                        attributes=api_measurement.attributes,
                    )
            except Exception:  # pylint: disable=broad-except
                _logger.exception(
                    "Callback failed for instrument %s.", self.name
                )


class Counter(_Synchronous, APICounter):
    def add(
        self, amount: Union[int, float], attributes: Dict[str, str] = None
    ):
        if amount < 0:
            _logger.warning(
                "Add amount must be non-negative on Counter %s.", self.name
            )
            return
        self._measurement_consumer.consume_measurement(
            Measurement(amount, self, attributes)
        )


class UpDownCounter(_Synchronous, APIUpDownCounter):
    def add(
        self, amount: Union[int, float], attributes: Dict[str, str] = None
    ):
        self._measurement_consumer.consume_measurement(
            Measurement(amount, self, attributes)
        )


class ObservableCounter(_Asynchronous, APIObservableCounter):
    pass


class ObservableUpDownCounter(_Asynchronous, APIObservableUpDownCounter):
    pass


class Histogram(_Synchronous, APIHistogram):
    def record(
        self, amount: Union[int, float], attributes: Dict[str, str] = None
    ):
        if amount < 0:
            _logger.warning(
                "Record amount must be non-negative on Histogram %s.",
                self.name,
            )
            return
        self._measurement_consumer.consume_measurement(
            Measurement(amount, self, attributes)
        )


class ObservableGauge(_Asynchronous, APIObservableGauge):
    pass
