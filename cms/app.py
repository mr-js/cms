from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from markupsafe import Markup, escape
from core import Message, Chat
import time
from secrets import token_hex
import webbrowser
import pathlib
import json
from base64 import  b64encode


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'C:\Test'
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg', '.gif', '.mp3', '.ogg', '.mp4', '.webm', '.txt', '.html', '.pdf','.zip'}
app.secret_key = token_hex(16)
chat = Chat(id='test')


@app.context_processor
def utility_processor():
    def external_media_fit(media_item):
        return media_fit(media_item)
    return dict(external_media_fit=external_media_fit)


def media_fit(media_item):
    media_code = ''
    ico = f'data:image/gif;base64, R0lGODlhAQABAIAAAP///wAAACwAAAAAAQABAAACAkQBADs='
    type, data, description = media_item.values()
    src = f'{type}, {data}'
    if any(filter(lambda media_type: media_type in type, ['png', 'jpg', 'gif'])):
        media_code = f'<a download="{description}" href="{src}"><img src="{src}" alt="{description}" class="message_media_source"></a><br>{description}'
    elif any(filter(lambda media_type: media_type in type, ['mp3', 'ogg'])):
        media_code = f'<audio controls src="{src}" alt="{description}" class="message_media_source"></audio><br>{description}'
    elif any(filter(lambda media_type: media_type in type, ['mp4', 'webm'])):
        media_code = f'<video controls src="{src}" alt="{description}" class="message_media_source"></audio><br>{description}'
    else:
        media_code = f'<a download="{description}" href="{src}"><embed src="{src}" alt="{description}" class="message_media_source"></a><br>{description}'

    media_code = f'<div class="message_media_item">{media_code}</div>'
    return media_code


@app.route('/', methods=['POST', 'GET'])
def page_main():
    global chat
    if request.method == 'GET':
        ...
    elif request.method == 'POST':
        if request.form['action'] == 'Switch':
            chat = Chat(request.form['chat_id'])
            chat.author = request.form['user_id']
        elif request.form['action'] == 'Erase':
            chat = Chat(request.form['chat_id'])
            chat.author = request.form['user_id']
            chat.erase()
        else:
            ...
    chat.check_inbox_messages()
    session['preview_history'] = True
    session['preview_media'] = True
    return render_template('main.html', chat=chat, media_item=None)


@app.get('/message_send')
def message_send():
    global chat
    chat.msg_draft.text = request.args.get('message_text')
    chat.msg_draft.author = chat.author
    chat.send()
    chat.msg_draft = Message()
    session['preview_history'] = True
    return jsonify(None)


@app.get('/history_update')
def history_update():
    global chat
    if 'preview_history' in session and session['preview_history'] == True:
        session['preview_history'] = False
        return render_template('history.html', chat=chat)
    else:
        return ''


@app.route('/media_update')
def media_update():
    if 'preview_media' in session and session['preview_media'] == True:
        session['preview_media'] = False
        items = [media_fit(media_item) for media_item in chat.msg_draft.media.values()]
        return jsonify(items=items)
    else:
        return ''


@app.route('/media_upload', methods = ['GET', 'POST'])
def media_upload():
    global chat
    media_item = None
    if request.method == 'GET':
        return render_template('upload.html')
    if request.method == 'POST':
        file = request.files['file']
        ext = pathlib.Path(file.filename).suffix
        if ext in app.config['ALLOWED_EXTENSIONS']:
            data = b64encode(file.read()).decode('utf-8')
            type = ext[1:]
            if any(filter(lambda media_type: media_type in type, ['png', 'jpg', 'gif'])):
                type = f'data:image/{type};base64'
            elif any(filter(lambda media_type: media_type in type, ['mp3', 'ogg'])):
                type = f'data:audio/{type};base64'
            elif any(filter(lambda media_type: media_type in type, ['mp4', 'webm'])):
                type = f'data:video/{type};base64'
            elif any(filter(lambda media_type: media_type in type, ['html'])):
                type = f'data:text/{type};base64'
            elif any(filter(lambda media_type: media_type in type, ['txt'])):
                type = f'data:text/plain;base64'
            elif any(filter(lambda media_type: media_type in type, ['pdf'])):
                type = f'data:application/{type};base64'
            elif any(filter(lambda media_type: media_type in type, ['zip'])):
                type = f'data:application/{type};base64'
            else:
                return render_template('upload.html', status=f'File {file.filename} not allowed. Close this tab (CTRL + W) or add next file.')
            media_item = {token_hex(16) : {"type": type, "data": data, "description": request.form['description']}}
            chat.msg_draft.media.update(media_item)
            session['preview_media'] = True
            return render_template('upload.html', status=f'File {file.filename} uploaded OK. Close this tab (CTRL + W) or add next file.')
        else:
            return render_template('upload.html', status=f'File {file.filename} not allowed. Close this tab (CTRL + W) or add next file.')


@app.get('/status_update')
def status_update():
    global chat
    new_inbox_msgs_counter = chat.check_inbox_messages()
    if new_inbox_msgs_counter > 0:
        session['preview_history'] = True
    return jsonify(status=f'New messages: {new_inbox_msgs_counter}')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port='5000')
