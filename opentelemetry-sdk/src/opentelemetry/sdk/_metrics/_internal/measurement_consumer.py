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

# pylint: disable=unused-import

from abc import ABC, abstractmethod
from threading import Lock
from typing import Iterable, List, Mapping

# This kind of import is needed to avoid Sphinx errors.
import opentelemetry.sdk._metrics
import opentelemetry.sdk._metrics._internal.instrument
import opentelemetry.sdk._metrics._internal.sdk_configuration
from opentelemetry._metrics._internal.instrument import CallbackOptions
from opentelemetry.sdk._metrics._internal.measurement import Measurement
from opentelemetry.sdk._metrics._internal.metric_reader_storage import (
    MetricReaderStorage,
)
from opentelemetry.sdk._metrics._internal.point import Metric


class MeasurementConsumer(ABC):
    @abstractmethod
    def consume_measurement(self, measurement: Measurement) -> None:
        pass

    @abstractmethod
    def register_asynchronous_instrument(
        self,
        instrument: (
            "opentelemetry.sdk._metrics._internal.instrument_Asynchronous"
        ),
    ):
        pass

    @abstractmethod
    def collect(
        self,
        metric_reader: "opentelemetry.sdk._metrics.MetricReader",
    ) -> Iterable[Metric]:
        pass


class SynchronousMeasurementConsumer(MeasurementConsumer):
    def __init__(
        self,
        sdk_config: "opentelemetry.sdk._metrics._internal.SdkConfiguration",
    ) -> None:
        self._lock = Lock()
        self._sdk_config = sdk_config
        # should never be mutated
        self._reader_storages: Mapping[
            "opentelemetry.sdk._metrics.MetricReader", MetricReaderStorage
        ] = {
            reader: MetricReaderStorage(
                sdk_config,
                reader._instrument_class_temporality,
                reader._instrument_class_aggregation,
            )
            for reader in sdk_config.metric_readers
        }
        self._async_instruments: List[
            "opentelemetry.sdk._metrics._internal.instrument._Asynchronous"
        ] = []

    def consume_measurement(self, measurement: Measurement) -> None:
        for reader_storage in self._reader_storages.values():
            reader_storage.consume_measurement(measurement)

    def register_asynchronous_instrument(
        self,
        instrument: (
            "opentelemetry.sdk._metrics._internal.instrument._Asynchronous"
        ),
    ) -> None:
        with self._lock:
            self._async_instruments.append(instrument)

    def collect(
        self,
        metric_reader: "opentelemetry.sdk._metrics.MetricReader",
    ) -> Iterable[Metric]:
        with self._lock:
            metric_reader_storage = self._reader_storages[metric_reader]
            # for now, just use the defaults
            callback_options = CallbackOptions()
            for async_instrument in self._async_instruments:
                for measurement in async_instrument.callback(callback_options):
                    metric_reader_storage.consume_measurement(measurement)
        return self._reader_storages[metric_reader].collect()
