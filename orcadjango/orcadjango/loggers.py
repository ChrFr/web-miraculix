import logging
from asgiref.sync import async_to_sync
import channels.layers


class OrcaChannelHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = 'log_orca'

    def emit(self, record):
        channel_layer = channels.layers.get_channel_layer()
        async_to_sync(channel_layer.group_send)(self.group, {
            'message': record.getMessage(),
            'type': 'log_message'
        })


class ScenarioHandler(OrcaChannelHandler):
    def __init__(self, scenario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = f'log_{self.scenario.id}'
