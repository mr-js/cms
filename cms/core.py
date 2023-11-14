import json
import codecs
import os, shutil
from secrets import token_hex, randbits
from datetime import datetime
import hashlib
import logging
import traceback


DEBUG = False
logging_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(handlers=[logging.StreamHandler(), logging.FileHandler('journal.log', 'w', 'utf-8')], format='%(asctime)s %(levelname)s %(message)s [%(funcName)s]', datefmt='%Y.%m.%d %H:%M:%S', level=logging_level)
log = logging.getLogger(__name__)


class Message:
    def __init__(self):
        self.id = token_hex(16)
        self.text = ''
        self.media = {}
        self.author = ''
        self.time = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        self.hash = ''


    def __eq__(self, other):
        return ((self.id, self.hash) == (other.id, other.hash))


    def __contains__(self, item):
        return any(filter(lambda msg: item.hash == msg.hash, self.msgs))


    def update_hash(self):
        log.debug(self.media)
        hashable = self.text if (self.media == {}) else self.text + ''.join(v.get('data') for k, v in self.media.items())
        self.hash = hashlib.md5(hashable.encode('utf-8')).hexdigest()


    def from_dict(self, msg_id=None, msg_values=None):
        if msg_id and msg_values:
            try:
                self.id, self.text, self.media, self.author, self.time, self.hash = msg_id, *msg_values.values()
                log.debug(f'msg {self.id}, {self.text}, {self.media}, {self.author}, {self.time}, {self.hash} created')
            except Exception as e:
                log.error(e)
        self.update_hash()


    def write(self, text, media, author):
        self.text = text
        self.media = media
        self.author = author
        self.update_hash()


    def to_json(self):
        self.update_hash()
        msg_json=None
        try:
            msg_json = json.dumps(self, ensure_ascii=False, indent=4, default=lambda obj: obj.__dict__)
        except Exception as e:
            log.error(e)
        return msg_json


class Chat:
    def __init__(self, id='', name=''):
        if id == '' and name != 'temp':
            self.id = token_hex(16)
        else:
            self.id = id
        self.name = name
        self.author = ''
        self.new_inbox_msgs = []
        self.new_outbox_msgs = []
        self.msg_draft = Message()
        self.msgs = []
        self.locked = False
        self.modified = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        self.hash = ''
        # (filename,line_number,function_name,text)=traceback.extract_stack()[-2]
        # self.name = text[:text.find('=')].strip()
        log.debug(f'chat {self.id}/{self.name} initialized')


    def __eq__(self, other):
        log.debug(f'chat {self.id}/{self.name} == chat {other.id}/{other.name}: {((self.hash) == (other.hash))}')
        return ((self.hash) == (other.hash))


    def __sub__(self, other):
        diff_msgs = []
        for self_msg in self.msgs:
            if self_msg not in other.msgs:
                diff_msgs.append(self_msg)
        log.debug(f'chat {self.id}/{self.name} - chat {other.id}/{other.name} ({[msg.id for msg in self.msgs]} - {[msg.id for msg in other.msgs]}) = {diff_msgs}')
        return diff_msgs


    def update_properties(self):
        self.locked = False
        hashable = ''.join(msg.hash for msg in self.msgs)
        self.hash = hashlib.md5(hashable.encode('utf-8')).hexdigest()
        self.modified = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        log.debug(f'chat {self.id}/{self.name} properties updated')


    def check_inbox_messages(self):
        temp = Chat(id=self.id, name='temp')
        temp.load()
        self.new_inbox_msgs = temp - self
        self.msgs += self.new_inbox_msgs
        new_inbox_msgs_counter = len(self.new_inbox_msgs)
        log.debug(f'chat {self.id}/{self.name} checked ({new_inbox_msgs_counter}: {[msg.id for msg in self.new_inbox_msgs]})')
        if new_inbox_msgs_counter > 0:
            self.display_sync()
        return new_inbox_msgs_counter


    def add_new_message(self, msg_id, msg_dict):
        msg = Message()
        msg.from_dict(msg_id, msg_dict['messages'].get(msg_id))
        self.msgs.append(msg)
        self.new_outbox_msgs.append(msg)
        log.debug(f'chat {self.id}/{self.name} msg {msg.id} ({msg.text}) added')
        self.display_sync()


    def send(self):
        self.msgs.append(self.msg_draft)
        self.new_outbox_msgs.append(self.msg_draft)
        log.debug(f'chat {self.id}/{self.name} msg {self.msg_draft.id} ({self.msg_draft.text}) added')
        self.display_sync()
        self.save()


    def load(self):
        chat_dict = None
        filename = f'{self.id}.json'
        try:
            if not os.path.isfile(filename) and self.name != 'temp':
                shutil.copy('default.json', filename)
                log.info(f'chat {self.id} not exist: created')
            with codecs.open(filename, 'r', 'utf-8') as f:
                chat_dict = json.load(f)
                log.debug(f'chat {self.id}/{self.name} loaded')
            for msg_id in chat_dict['messages']:
                msg = Message()
                msg.from_dict(msg_id, chat_dict['messages'].get(msg_id))
                if msg not in self.msgs:
                    self.msgs.append(msg)
                    self.new_inbox_msgs.append(msg)
                    log.debug(f'chat {self.id}/{self.name} msg {msg.id} added')
                else:
                    log.debug(f'chat {self.id}/{self.name} msg {msg.id} passed')

            self.locked, self.modified, self.hash = chat_dict['properties'].values()
            log.debug(f'chat {self.id}/{self.name} parsed')
        except Exception as e:
            log.error(e)
        return chat_dict


    def erase(self):
        chat_dict = None
        filename = f'{self.id}.json'
        try:
            if os.path.isfile(filename):
                os.remove(filename)
                shutil.copy('default.json', filename)
                self.load()
                self.save()
                log.info(f'chat {self.id} erased')
        except Exception as e:
            log.error(e)
        return True


    def save(self):
        chat_dict=None
        filename = f'{self.id}.json'
        self.update_properties()
        self.check_inbox_messages()
        try:
            prop_dict = {'locked' : self.locked, 'modified' : self.modified, 'hash' : self.hash}
            msgs_dict = {}
            for msg in self.msgs:
                msgs_dict[msg.id] = {'text' : msg.text, 'media' : msg.media, 'author' : msg.author, 'time' : msg.time, 'hash' : msg.hash}
            log.debug(f'chat {self.id}/{self.name} prepared')
            chat_dict = {'messages' : msgs_dict, 'properties' : prop_dict}
            with codecs.open(filename, 'w', 'utf-8') as f:
                json.dump(chat_dict, f, ensure_ascii=False, indent = 4, default=lambda obj: obj.__dict__)
        except Exception as e:
            log.error(e)
        log.debug(f'chat {self.id}/{self.name} saved')
        return chat_dict


    def display_sync(self):
        info = 40*'-' + ' DISPLAY ' + 40*'-' + '\n'
        for msg in self.new_inbox_msgs:
            info += f'new_inbox_msg: {msg.id} ({msg.text} / {msg.media})' + '\n'
            log.debug(f'msg {msg.id} dispayed as inbox')
        for msg in self.new_outbox_msgs:
            info += f'new_outbox_msg: {msg.id} ({msg.text} / {msg.media})' + '\n'
            log.debug(f'msg {msg.id} dispayed as outbox')
        info += 40*'-' + ' ------- ' + 40*'-' + '\n'
        log.info(info)
        self.new_inbox_msgs = []
        self.new_outbox_msgs = []


    def to_json(self):
        self.update_properties()
        chat_json=None
        try:
            chat_json = json.dumps(self, ensure_ascii=False, indent=4, default=lambda obj: obj.__dict__)
        except Exception as e:
            log.error(e)
        return chat_json
