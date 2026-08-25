########################################################################
# Copyright (c) 2025 Robert Bosch GmbH
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
#
# SPDX-License-Identifier: Apache-2.0
########################################################################

import asyncio
import queue
import uuid

import grpc
import pytest

import kuksa_client.grpc.aio as aio_mod
from kuksa_client.cli_backend import grpc as grpc_backend
from kuksa_client.grpc import Field
from kuksa_client.grpc import SubscribeEntry
from kuksa_client.grpc import View
from kuksa_client.grpc import VSSClientError


def _not_found_error():
    return VSSClientError(
        error={
            "code": grpc.StatusCode.NOT_FOUND.value[0],
            "reason": grpc.StatusCode.NOT_FOUND.value[1],
            "message": "Path not found",
        },
        errors=[],
    )


def _unimplemented_error():
    return VSSClientError(
        error={
            "code": grpc.StatusCode.UNIMPLEMENTED.value[0],
            "reason": grpc.StatusCode.UNIMPLEMENTED.value[1],
            "message": "Not implemented",
        },
        errors=[],
    )


class TestGrpcCliBackend:
    @staticmethod
    def _backend():
        return grpc_backend.Backend(
            {
                "protocol": "grpc",
                "ip": "127.0.0.1",
                "port": 55555,
                "insecure": True,
            }
        )

    @staticmethod
    def _subscribe_request(paths, entries):
        return {
            "paths": paths,
            "entries": entries,
            "callback": lambda updates: None,
        }

    async def _process(self, backend, vss_client, request):
        response_queue = queue.Queue(maxsize=1)
        backend.sendMsgQueue.put(("subscribe", request, response_queue))
        task = asyncio.create_task(backend._grpcHandler(vss_client))
        try:
            for _ in range(100):
                try:
                    return response_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
            pytest.fail("No response received from _grpcHandler")
        finally:
            backend.run = False
            await task

    @pytest.mark.asyncio
    async def test_subscribe_leaf_path(self, mocker):
        backend = self._backend()
        vss_client = mocker.MagicMock()
        vss_client.v2_subscribe.return_value = "v2_stream"
        subscriber_manager = mocker.MagicMock()
        sub_id = uuid.uuid4()
        subscriber_manager.add_subscriber = mocker.AsyncMock(return_value=sub_id)
        mocker.patch.object(aio_mod, "SubscriberManager", return_value=subscriber_manager)

        entries = [SubscribeEntry("Vehicle.Speed", View.CURRENT_VALUE, (Field.VALUE,))]
        resp, error = await self._process(
            backend, vss_client, self._subscribe_request(["Vehicle.Speed"], entries)
        )

        assert error is None
        assert resp == {"subscriptionId": str(sub_id)}
        vss_client.v2_subscribe.assert_called_once_with(paths=["Vehicle.Speed"])
        vss_client._expand_v2_branch_paths.assert_not_called()
        vss_client.subscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_subscribe_expands_branch_paths_on_not_found(self, mocker):
        backend = self._backend()
        vss_client = mocker.MagicMock()
        vss_client.v2_subscribe.side_effect = ["v2_stream_first", "v2_stream_second"]
        vss_client._expand_v2_branch_paths = mocker.AsyncMock(
            return_value=["Vehicle.Speed", "Vehicle.ADAS.ABS.IsActive"]
        )
        subscriber_manager = mocker.MagicMock()
        sub_id = uuid.uuid4()
        subscriber_manager.add_subscriber = mocker.AsyncMock(
            side_effect=[_not_found_error(), sub_id]
        )
        mocker.patch.object(aio_mod, "SubscriberManager", return_value=subscriber_manager)

        entries = [SubscribeEntry("Vehicle", View.CURRENT_VALUE, (Field.VALUE,))]
        resp, error = await self._process(
            backend, vss_client, self._subscribe_request(["Vehicle"], entries)
        )

        assert error is None
        assert resp == {"subscriptionId": str(sub_id)}
        assert vss_client.v2_subscribe.call_args_list == [
            mocker.call(paths=["Vehicle"]),
            mocker.call(paths=["Vehicle.Speed", "Vehicle.ADAS.ABS.IsActive"]),
        ]
        vss_client._expand_v2_branch_paths.assert_called_once_with(["Vehicle"])
        vss_client.subscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_subscribe_falls_back_to_v1_on_unimplemented(self, mocker):
        backend = self._backend()
        vss_client = mocker.MagicMock()
        vss_client.v2_subscribe.return_value = "v2_stream"
        vss_client.subscribe.return_value = "v1_stream"
        subscriber_manager = mocker.MagicMock()
        sub_id = uuid.uuid4()
        subscriber_manager.add_subscriber = mocker.AsyncMock(
            side_effect=[_unimplemented_error(), sub_id]
        )
        mocker.patch.object(aio_mod, "SubscriberManager", return_value=subscriber_manager)

        entries = [SubscribeEntry("Vehicle.Speed", View.CURRENT_VALUE, (Field.VALUE,))]
        resp, error = await self._process(
            backend, vss_client, self._subscribe_request(["Vehicle.Speed"], entries)
        )

        assert error is None
        assert resp == {"subscriptionId": str(sub_id)}
        vss_client.v2_subscribe.assert_called_once_with(paths=["Vehicle.Speed"])
        vss_client.subscribe.assert_called_once_with(entries=entries)
        vss_client._expand_v2_branch_paths.assert_not_called()
