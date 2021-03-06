# Copyright (c) 2017  Janus Development Team
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import slackclient
import time
import traceback
from . import User, Message


class SlackMessage(Message):

    def __init__(self, backend, data, text=None):
        # Convert the user information.
        user = backend.get_user(data['user'])
        user = User(data['user'], user['name'])

        if text is None:
            text = data['text']

        # Generate a unique message ID.
        message_id = data['channel'] + data['user'] + data['ts']
        Message.__init__(self, message_id, text, user)
        self.channel = data['channel']
        self.backend = backend

    def reply(self, text):
        self.backend.reply(self.channel, text)


class SlackBackend(object):
    """
    Reacts on messages pointing to the bot user.
    """

    def __init__(self, botname, token, handler, mode='im', debug=False, read_delay=1):
        assert mode in ('im', 'mention')
        self.botname = botname
        self.mode = mode
        self.token = token
        self.client = slackclient.SlackClient(token)
        self.handler = handler
        self.read_delay = read_delay
        self.debug = debug
        self.botid = None
        self.botim = None

    def parse_slack_output(self, slack_rtm_output):
        """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
        """
        # https://www.fullstackpython.com/blog/build-first-slack-bot-python.html

        AT_BOT = '<@' + self.botid + '>'
        output_list = slack_rtm_output
        if output_list and len(output_list) > 0:
            for output in output_list:
                if output and 'text' in output and AT_BOT in output['text']:
                    # return text after the @ mention, whitespace removed
                    return output['text'].split(AT_BOT)[1].strip().lower(), \
                        output['channel']
        return None, None

    def get_users(self, force_update=False):
        if not hasattr(self, '_users') or force_update:
            result = {}
            for user in self.client.api_call('users.list')['members']:
                result[user['id']] = user
            self._users = result
        return self._users

    def get_user(self, id):
        if id not in getattr(self, '_users', {}):
            self.get_users(True)
        return self._users[id]

    def get_channels(self):
        result = {}
        for channel in self.client.api_call('channels.list')['channels']:
            result[channel['id']] = channel
        return result

    def get_im(self):
        result = {}
        for channel in self.client.api_call('im.list')['ims']:
            result[channel['id']] = channel
        return result

    def reply(self, channel, text):
        self.client.api_call(
            'chat.postMessage',
            token=self.token,
            channel=channel,
            username=self.botname,
            text=text
        )

    def start(self):
        if not self.client.rtm_connect():
            raise RuntimeError('Connection failed. Invalid Slack token or bot ID?')

        # Find the ID of the chatbot.
        users = self.get_users()
        for user in users.values():
            print(user['name'], user['id'])
        for user in users.values():
            if user['name'] == self.botname:
                self.botid = user['id']
                break
        else:
            raise ValueError('could not determine Bot ID')

        # Find the chatbot's channel.
        for im  in self.get_im().values():
            if im['user'] == self.botid:
                self.botim = im
                break
        else:
            raise ValueError('could31 not determine Bot Channel')

        tbegin = time.time()

        while True:
            for data in self.client.rtm_read():
                if data['type'] != 'message': continue
                if 'text' not in data: continue
                if 'subtype' in data: continue  # TODO: Anything to handle here?

                # Slack sends the last message again. We don't want to process
                # it, though. This is a very dirty way that skips all messages
                # received in the first 0.5 seconds on startup. ¯\_(ツ)_/¯
                if (time.time() - tbegin) < 0.5:
                    print('Skipping initial message')
                    continue

                handle = False
                if self.mode == 'im' and data['channel'] == self.botim['id']:
                    print(data)
                    handle = True
                    text = data['text']
                elif self.mode == 'mention' and data['text'].startswith('<@{}>'.format(self.botid)):
                    text = data['text'][len(self.botid) + 3:]
                if handle:
                    message = SlackMessage(self, data, text)
                    try:
                        self.handler.handle_message(message)
                    except:
                        traceback.print_exc()
                        if self.debug:
                            message.reply('```\n' + traceback.format_exc() + '\n```')
