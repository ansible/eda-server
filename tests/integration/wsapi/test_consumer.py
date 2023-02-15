from unittest.mock import patch

import pytest
from channels.testing import WebsocketCommunicator

from aap_eda.wsapi.consumers import AnsibleRulebookConsumer


@pytest.mark.asyncio
async def test_ansible_rulebook_consumer():
    communicator = WebsocketCommunicator(
        AnsibleRulebookConsumer.as_asgi(), "ws/"
    )
    connected, _ = await communicator.connect()
    assert connected

    test_payloads = [
        {"handle_workers": {"type": "Worker", "activation_id": "1"}},
        {"handle_actions": {"type": "Action", "action": "run_playbook"}},
        {"handle_jobs": {"type": "Job", "name": "ansible.eda.hello"}},
        {"handle_events": {"type": "AnsibleEvent", "event": {}}},
    ]

    for payload in test_payloads:
        for key, value in payload.items():
            with patch.object(AnsibleRulebookConsumer, key) as mocker:
                await communicator.send_json_to(value)
                response = await communicator.receive_json_from()

                mocker.assert_called_once_with(value)

    assert response["type"] == "Hello"

    await communicator.disconnect()
