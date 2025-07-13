from flask import Flask, render_template_string, request, jsonify, session
from flask_socketio import SocketIO, join_room, leave_room, emit
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key_2025'
socketio = SocketIO(app)

# دیتابیس SQLite
def init_db():
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        avatar TEXT,
        bio TEXT,
        online INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE,
        title TEXT,
        color TEXT,
        banner TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER,
        user_id INTEGER,
        text TEXT,
        timestamp TEXT,
        read INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS private_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER,
        text TEXT,
        timestamp TEXT,
        read INTEGER DEFAULT 0
    )''')
    default_rooms = [
        ('public', 'چت عمومی', 'bg-gradient-to-r from-blue-600 to-blue-400 text-white', 'https://source.unsplash.com/random/800x600?blue'),
        ('girls', 'دخترونه', 'bg-gradient-to-r from-pink-600 to-pink-400 text-white', 'https://source.unsplash.com/random/800x600?pink'),
        ('boys', 'پسرونه', 'bg-gradient-to-r from-gray-900 to-gray-700 text-white', 'https://source.unsplash.com/random/800x600?gray'),
        ('hackers', 'میتینگ هکرا', 'bg-gradient-to-r from-green-900 to-green-700 text-green-200', 'https://source.unsplash.com/random/800x600?green'),
        ('friendly', 'دوستانه', 'bg-gradient-to-r from-orange-600 to-orange-400 text-white', 'https://source.unsplash.com/random/800x600?orange')
    ]
    c.executemany('INSERT OR IGNORE INTO rooms (slug, title, color, banner) VALUES (?, ?, ?, ?)', default_rooms)
    conn.commit()
    conn.close()

init_db()

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="{{ 'fa' if session.get('lang', 'fa') == 'fa' else 'en' }}" dir="{{ 'rtl' if session.get('lang', 'fa') == 'fa' else 'ltr' }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>چت‌روم سوپر خفن</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@heroicons/vue@2.0.13/dist/heroicons-vue.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/emoji-picker-element@^1"></script>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <style>
        @import url('https://v1.fontapi.ir/css/Vazir');
        body { font-family: 'Vazir', sans-serif; background: linear-gradient(to bottom, #1a202c, #2d3748); color: white; }
        .chat-bubble { background: #4a5568; padding: 12px 16px; border-radius: 16px; margin: 12px 0; transition: all 0.3s ease; }
        .chat-bubble.me { background: linear-gradient(to right, #3b82f6, #60a5fa); margin-left: auto; max-width: 70%; }
        .notification { background: #2d3748; color: #a0aec0; text-align: center; border-radius: 12px; padding: 10px; }
        .dropdown-menu { transition: all 0.3s ease; }
        .dropdown-menu:hover { transform: scale(1.05); }
        .animate-slide-in { animation: slideIn 0.5s ease; }
        @keyframes slideIn { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .animate-fade-in { animation: fadeIn 0.5s ease; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .chat-container { max-height: calc(100vh - 200px); }
        .avatar { transition: transform 0.2s; }
        .avatar:hover { transform: scale(1.1); }
        .typing-indicator { font-size: 0.9rem; color: #a0aec0; }
        .emoji-picker { position: absolute; z-index: 100; }
        .badge { background: #ef4444; color: white; border-radius: 9999px; padding: 2px 8px; font-size: 0.75rem; }
        .voice-call-btn:hover { background: #10b981; }
    </style>
</head>
<body>
    <!-- هدر ثابت -->
    <header class="bg-gray-900 p-4 sticky top-0 z-50 shadow-xl">
        <div class="container mx-auto flex justify-between items-center">
            <div class="flex items-center space-x-4">
                <select id="language" class="bg-gray-800 text-white p-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="fa" {{ 'selected' if session.get('lang', 'fa') == 'fa' else '' }}>فارسی</option>
                    <option value="en" {{ 'selected' if session.get('lang', 'fa') == 'en' else '' }}>English</option>
                </select>
                <button id="theme-toggle" class="bg-gray-800 text-white p-2 rounded-lg hover:bg-gray-700 transition">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                </button>
            </div>
            <div class="relative">
                <button id="room-menu-btn" class="bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center hover:bg-blue-700 transition">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7"></path></svg>
                    {{ 'چت‌روم‌ها' if session.get('lang', 'fa') == 'fa' else 'Chat Rooms' }} <span id="unread-count" class="badge ml-2"></span>
                </button>
                <div id="room-menu" class="hidden absolute {{ 'right-0' if session.get('lang', 'fa') == 'fa' else 'left-0' }} mt-2 w-48 bg-gray-800 rounded-lg shadow-xl dropdown-menu">
                    {% for room in rooms %}
                    <a href="#" class="{{ room.color }} block px-4 py-2 hover:bg-gray-700 transition" onclick="joinRoom('{{ room.slug }}')">{{ room.title }} <span id="unread-{{ room.slug }}" class="badge"></span></a>
                    {% endfor %}
                </div>
            </div>
        </div>
    </header>

    <!-- صفحه ورود -->
    <div id="login-page" class="{{ 'hidden' if session.get('user') else '' }} min-h-screen flex items-center justify-center animate-fade-in">
        <div class="bg-gray-800 p-8 rounded-2xl shadow-2xl max-w-md w-full">
            <img src="/static/logo.png" alt="Logo" class="mx-auto h-20 mb-6 rounded-full shadow-lg" onerror="this.src='https://source.unsplash.com/random/100x100?logo';">
            <form id="login-form">
                <input type="text" id="username" placeholder="{{ 'نام کاربری یا ایمیل' if session.get('lang', 'fa') == 'fa' else 'Username or Email' }}" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                <input type="password" id="password" placeholder="{{ 'رمز عبور' if session.get('lang', 'fa') == 'fa' else 'Password' }}" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                <button type="submit" class="w-full bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 transition">{{ 'ورود' if session.get('lang', 'fa') == 'fa' else 'Login' }}</button>
            </form>
            <p class="mt-4 text-center text-gray-400">{{ 'حساب ندارید؟' if session.get('lang', 'fa') == 'fa' else 'No account?' }} <a href="#register" onclick="showRegister()" class="text-blue-400 hover:underline">{{ 'ثبت‌نام کنید' if session.get('lang', 'fa') == 'fa' else 'Register' }}</a></p>
        </div>
    </div>

    <!-- صفحه ثبت‌نام -->
    <div id="register-page" class="hidden min-h-screen flex items-center justify-center animate-fade-in">
        <div class="bg-gray-800 p-8 rounded-2xl shadow-2xl max-w-md w-full">
            <form id="register-form" enctype="multipart/form-data">
                <input type="text" id="reg-username" placeholder="{{ 'نام کاربری' if session.get('lang', 'fa') == 'fa' else 'Username' }}" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" required pattern="[A-Za-z0-9_]{3,20}">
                <input type="email" id="reg-email" placeholder="{{ 'ایمیل' if session.get('lang', 'fa') == 'fa' else 'Email' }}" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                <input type="password" id="reg-password" placeholder="{{ 'رمز عبور' if session.get('lang', 'fa') == 'fa' else 'Password' }}" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" required minlength="6">
                <input type="password" id="reg-confirm-password" placeholder="{{ 'تایید رمز عبور' if session.get('lang', 'fa') == 'fa' else 'Confirm Password' }}" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                <input type="file" id="reg-avatar" accept="image/*" class="w-full p-3 mb-4 rounded-lg bg-gray-700 text-white">
                <button type="submit" class="w-full bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 transition">{{ 'ثبت‌نام' if session.get('lang', 'fa') == 'fa' else 'Register' }}</button>
            </form>
            <p class="mt-4 text-center text-gray-400"><a href="#login" onclick="showLogin()" class="text-blue-400 hover:underline">{{ 'بازگشت به ورود' if session.get('lang', 'fa') == 'fa' else 'Back to Login' }}</a></p>
        </div>
    </div>

    <!-- صفحه اصلی -->
    <div id="main-page" class="{{ '' if session.get('user') else 'hidden' }} min-h-screen p-6 animate-slide-in">
        <h1 class="text-4xl font-bold mb-8 text-center text-blue-400">{{ 'سلام! به کدوم چت‌روم می‌خوای وارد شی؟' if session.get('lang', 'fa') == 'fa' else 'Hello! Which chat room do you want to join?' }}</h1>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for room in rooms %}
            <div class="{{ room.color }} p-6 rounded-2xl shadow-lg hover:scale-105 transition cursor-pointer" data-room="{{ room.slug }}" onclick="joinRoom('{{ room.slug }}')">
                <img src="{{ room.banner }}" alt="{{ room.title }}" class="h-40 w-full object-cover rounded-lg mb-4 shadow-md">
                <h2 class="text-2xl font-semibold">{{ room.title }}</h2>
            </div>
            {% endfor %}
        </div>
        <div class="mt-8 text-center">
            <a href="/profile" class="text-blue-400 hover:underline text-lg">{{ 'پروفایل' if session.get('lang', 'fa') == 'fa' else 'Profile' }}</a>
            {% if session.get('user') and session.get('user').get('is_admin') %}
            <a href="/admin" class="ml-4 text-blue-400 hover:underline text-lg">{{ 'پنل ادمین' if session.get('lang', 'fa') == 'fa' else 'Admin Panel' }}</a>
            {% endif %}
        </div>
    </div>

    <!-- صفحه چت‌روم -->
    <div id="chat-room" class="hidden min-h-screen flex animate-slide-in">
        <div class="w-1/4 bg-gray-800 p-6">
            <h2 class="text-lg font-bold mb-4 text-blue-400">{{ 'کاربران آنلاین' if session.get('lang', 'fa') == 'fa' else 'Online Users' }}</h2>
            <ul id="online-users" class="space-y-3"></ul>
        </div>
        <div class="flex-1 flex flex-col">
            <div id="room-header" class="bg-gray-900 text-white p-6 flex items-center shadow-lg">
                <img src="" id="room-banner" class="h-16 mr-4 rounded-lg shadow-md">
                <h2 id="room-title" class="text-2xl font-bold"></h2>
                <button id="voice-call-btn" class="ml-auto bg-green-600 text-white p-2 rounded-lg voice-call-btn transition">{{ 'تماس صوتی' if session.get('lang', 'fa') == 'fa' else 'Voice Call' }}</button>
            </div>
            <div id="chat-messages" class="flex-1 p-6 overflow-y-auto bg-gray-700 chat-container"></div>
            <div id="typing-indicator" class="p-2 text-gray-400"></div>
            <div class="p-6 bg-gray-800 flex items-center relative">
                <input id="message-input" type="text" class="flex-1 p-3 rounded-lg bg-gray-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="{{ 'پیام خود را بنویسید...' if session.get('lang', 'fa') == 'fa' else 'Type your message...' }}">
                <button id="emoji-btn" class="p-3 text-2xl hover:text-blue-400 transition">😊</button>
                <emoji-picker id="emoji-picker" class="hidden"></emoji-picker>
                <input type="file" id="file-input" accept="image/*,video/*" class="hidden">
                <button id="file-btn" class="p-3 text-2xl hover:text-blue-400 transition">📎</button>
                <button id="send-btn" class="bg-blue-600 text-white p-3 rounded-lg ml-2 hover:bg-blue-700 transition">{{ 'ارسال' if session.get('lang', 'fa') == 'fa' else 'Send' }}</button>
            </div>
        </div>
    </div>

    <!-- صفحه پروفایل -->
    <div id="profile-page" class="hidden min-h-screen p-6 animate-slide-in">
        <h1 class="text-4xl font-bold mb-8 text-blue-400">{{ 'پروفایل' if session.get('lang', 'fa') == 'fa' else 'Profile' }}</h1>
        <img src="{{ session.get('user').get('avatar') if session.get('user') else '' }}" alt="Avatar" class="h-32 rounded-full mb-6 shadow-lg avatar">
        <p class="mb-4 text-lg"><strong>{{ 'نام کاربری' if session.get('lang', 'fa') == 'fa' else 'Username' }}:</strong> {{ session.get('user').get('username') if session.get('user') else '' }}</p>
        <p class="mb-4 text-lg"><strong>{{ 'ایمیل' if session.get('lang', 'fa') == 'fa' else 'Email' }}:</strong> {{ session.get('user').get('email') if session.get('user') else '' }}</p>
        <p class="mb-4 text-lg"><strong>{{ 'بیوگرافی' if session.get('lang', 'fa') == 'fa' else 'Bio' }}:</strong> <input id="bio-input" value="{{ session.get('user').get('bio') if session.get('user') else '' }}" class="p-3 rounded-lg bg-gray-600 text-white w-full focus:outline-none focus:ring-2 focus:ring-blue-500"></p>
        <input type="file" id="avatar-input" accept="image/*" class="p-3 mb-4 rounded-lg bg-gray-600 text-white w-full">
        <button onclick="updateProfile()" class="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 transition">{{ 'ذخیره' if session.get('lang', 'fa') == 'fa' else 'Save' }}</button>
        <a href="/" class="mt-4 inline-block text-blue-400 hover:underline text-lg">{{ 'بازگشت' if session.get('lang', 'fa') == 'fa' else 'Back' }}</a>
    </div>

    <!-- صفحه ادمین -->
    <div id="admin-page" class="hidden min-h-screen p-6 animate-slide-in">
        <h1 class="text-4xl font-bold mb-8 text-blue-400">{{ 'پنل ادمین' if session.get('lang', 'fa') == 'fa' else 'Admin Panel' }}</h1>
        <h2 class="text-xl font-bold mb-4 text-blue-400">{{ 'مدیریت روم‌ها' if session.get('lang', 'fa') == 'fa' else 'Manage Rooms' }}</h2>
        <form id="room-form" class="space-y-4">
            <input id="room-title" placeholder="{{ 'عنوان' if session.get('lang', 'fa') == 'fa' else 'Title' }}" class="p-3 rounded-lg bg-gray-600 text-white w-full focus:outline-none focus:ring-2 focus:ring-blue-500">
            <input id="room-slug" placeholder="{{ 'شناسه' if session.get('lang', 'fa') == 'fa' else 'Slug' }}" class="p-3 rounded-lg bg-gray-600 text-white w-full focus:outline-none focus:ring-2 focus:ring-blue-500">
            <input id="room-color" placeholder="{{ 'رنگ (مثال: bg-blue-600)' if session.get('lang', 'fa') == 'fa' else 'Color (e.g., bg-blue-600)' }}" class="p-3 rounded-lg bg-gray-600 text-white w-full focus:outline-none focus:ring-2 focus:ring-blue-500">
            <input id="room-banner" placeholder="{{ 'آدرس بنر' if session.get('lang', 'fa') == 'fa' else 'Banner URL' }}" class="p-3 rounded-lg bg-gray-600 text-white w-full focus:outline-none focus:ring-2 focus:ring-blue-500">
            <button type="submit" class="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 transition">{{ 'ایجاد روم' if session.get('lang', 'fa') == 'fa' else 'Create Room' }}</button>
        </form>
        <ul id="room-list-admin" class="mt-6 space-y-3">
            {% for room in rooms %}
            <li class="{{ room.color }} p-4 rounded-lg shadow-md">{{ room.title }} <button onclick="deleteRoom('{{ room.slug }}')" class="text-red-400 ml-4 hover:underline">{{ 'حذف' if session.get('lang', 'fa') == 'fa' else 'Delete' }}</button></li>
            {% endfor %}
        </ul>
        <h2 class="text-xl font-bold mb-4 mt-6 text-blue-400">{{ 'مدیریت کاربران' if session.get('lang', 'fa') == 'fa' else 'Manage Users' }}</h2>
        <ul id="user-list-admin" class="mt-6 space-y-3">
            {% for user in users %}
            <li class="bg-gray-800 p-4 rounded-lg shadow-md">{{ user.username }} ({{ 'آنلاین' if user.online else 'آفلاین' if session.get('lang', 'fa') == 'fa' else 'Online' if user.online else 'Offline' }}) <button onclick="banUser('{{ user.id }}')" class="text-red-400 ml-4 hover:underline">{{ 'مسدود' if session.get('lang', 'fa') == 'fa' else 'Ban' }}</button></li>
            {% endfor %}
        </ul>
        <a href="/" class="mt-6 inline-block text-blue-400 hover:underline text-lg">{{ 'بازگشت' if session.get('lang', 'fa') == 'fa' else 'Back' }}</a>
    </div>

    <!-- مودال چت خصوصی -->
    <div id="private-chat-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-gray-800 p-6 rounded-2xl shadow-2xl max-w-md w-full">
            <h2 id="private-chat-title" class="text-xl font-bold mb-4 text-blue-400">{{ 'چت خصوصی' if session.get('lang', 'fa') == 'fa' else 'Private Chat' }}</h2>
            <div id="private-chat-messages" class="h-64 overflow-y-auto bg-gray-700 p-4 rounded-lg mb-4"></div>
            <div class="flex">
                <input id="private-message-input" type="text" class="flex-1 p-3 rounded-lg bg-gray-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="{{ 'پیام خود را بنویسید...' if session.get('lang', 'fa') == 'fa' else 'Type your message...' }}">
                <button id="private-send-btn" class="bg-blue-600 text-white p-3 rounded-lg ml-2 hover:bg-blue-700 transition">{{ 'ارسال' if session.get('lang', 'fa') == 'fa' else 'Send' }}</button>
            </div>
            <button onclick="closePrivateChat()" class="mt-4 text-blue-400 hover:underline">{{ 'بستن' if session.get('lang', 'fa') == 'fa' else 'Close' }}</button>
        </div>
    </div>

    <!-- مودال تماس صوتی -->
    <div id="voice-call-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-gray-800 p-6 rounded-2xl shadow-2xl max-w-md w-full">
            <h2 class="text-xl font-bold mb-4 text-blue-400">{{ 'تماس صوتی' if session.get('lang', 'fa') == 'fa' else 'Voice Call' }}</h2>
            <video id="local-video" autoplay muted class="h-32 w-full rounded-lg mb-4"></video>
            <video id="remote-video" autoplay class="h-32 w-full rounded-lg mb-4"></video>
            <button id="end-call-btn" class="bg-red-600 text-white p-3 rounded-lg hover:bg-red-700 transition">{{ 'پایان تماس' if session.get('lang', 'fa') == 'fa' else 'End Call' }}</button>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <script>
        const socket = io();
        const rooms = {{ rooms | tojson }};
        let currentPrivateChatUser = null;
        let currentRoom = null;
        let peerConnection = null;

        // تغییر تم (روشن/تیره)
        document.getElementById('theme-toggle').addEventListener('click', () => {
            document.body.classList.toggle('bg-gray-100');
            document.body.classList.toggle('text-gray-900');
            document.querySelectorAll('.bg-gray-800').forEach(el => {
                el.classList.toggle('bg-gray-200');
            });
            document.querySelectorAll('.text-white').forEach(el => {
                el.classList.toggle('text-gray-900');
            });
        });

        // منوی کشویی روم‌ها
        document.getElementById('room-menu-btn').addEventListener('click', () => {
            document.getElementById('room-menu').classList.toggle('hidden');
            updateUnreadCount();
        });

        // انتخابگر ایموجی
        document.getElementById('emoji-btn').addEventListener('click', () => {
            document.getElementById('emoji-picker').classList.toggle('hidden');
        });
        document.querySelector('emoji-picker').addEventListener('emoji-click', event => {
            document.getElementById('message-input').value += event.detail.unicode;
            document.getElementById('emoji-picker').classList.add('hidden');
        });

        // آپلود فایل
        document.getElementById('file-btn').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });
        document.getElementById('file-input').addEventListener('change', async () => {
            const file = document.getElementById('file-input').files[0];
            if (file && currentRoom) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('roomId', currentRoom);
                await fetch('/upload', {
                    method: 'POST',
                    body: formData
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        socket.emit('sendMessage', {
                            roomId: currentRoom,
                            message: `<a href="${data.fileUrl}" target="_blank">فایل: ${file.name}</a>`,
                            user: {{ session.get('user') | tojson }}
                        });
                    }
                });
            }
        });

        // تماس صوتی
        document.getElementById('voice-call-btn').addEventListener('click', async () => {
            document.getElementById('voice-call-modal').classList.remove('hidden');
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            document.getElementById('local-video').srcObject = stream;
            peerConnection = new RTCPeerConnection();
            stream.getTracks().forEach(track => peerConnection.addTrack(track, stream));
            peerConnection.ontrack = event => {
                document.getElementById('remote-video').srcObject = event.streams[0];
            };
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            socket.emit('voiceCallOffer', { roomId: currentRoom, offer });
        });

        document.getElementById('end-call-btn').addEventListener('click', () => {
            document.getElementById('voice-call-modal').classList.add('hidden');
            if (peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            document.getElementById('local-video').srcObject = null;
            document.getElementById('remote-video').srcObject = null;
        });

        socket.on('voiceCallOffer', async (data) => {
            if (!peerConnection) {
                peerConnection = new RTCPeerConnection();
                peerConnection.ontrack = event => {
                    document.getElementById('remote-video').srcObject = event.streams[0];
                };
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('local-video').srcObject = stream;
                stream.getTracks().forEach(track => peerConnection.addTrack(track, stream));
            }
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            socket.emit('voiceCallAnswer', { roomId: data.roomId, answer });
        });

        socket.on('voiceCallAnswer', async (data) => {
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
        });

        function showRegister() {
            document.getElementById('login-page').classList.add('hidden');
            document.getElementById('register-page').classList.remove('hidden');
            document.getElementById('main-page').classList.add('hidden');
            document.getElementById('chat-room').classList.add('hidden');
            document.getElementById('profile-page').classList.add('hidden');
            document.getElementById('admin-page').classList.add('hidden');
            document.getElementById('private-chat-modal').classList.add('hidden');
            document.getElementById('voice-call-modal').classList.add('hidden');
        }

        function showLogin() {
            document.getElementById('register-page').classList.add('hidden');
            document.getElementById('login-page').classList.remove('hidden');
            document.getElementById('main-page').classList.add('hidden');
            document.getElementById('chat-room').classList.add('hidden');
            document.getElementById('profile-page').classList.add('hidden');
            document.getElementById('admin-page').classList.add('hidden');
            document.getElementById('private-chat-modal').classList.add('hidden');
            document.getElementById('voice-call-modal').classList.add('hidden');
        }

        function joinRoom(slug) {
            currentRoom = slug;
            const room = rooms.find(r => r.slug === slug);
            socket.emit('joinRoom', { roomId: slug, user: {{ session.get('user') | tojson }} });
            document.getElementById('main-page').classList.add('hidden');
            document.getElementById('chat-room').classList.remove('hidden');
            document.getElementById('room-title').innerText = room.title;
            document.getElementById('room-banner').src = room.banner;
            document.getElementById('chat-messages').innerHTML = '';
            fetchMessages(slug);
            updateUnreadCount();
        }

        async function fetchMessages(roomId) {
            const res = await fetch(`/messages/${roomId}`);
            const messages = await res.json();
            messages.forEach(msg => displayMessage(msg));
        }

        function displayMessage(msg) {
            const messages = document.getElementById('chat-messages');
            const div = document.createElement('div');
            div.classList.add('chat-bubble', msg.user === '{{ session.get('user').get('username') if session.get('user') else '' }}' ? 'me' : '');
            if (msg.user === 'System') div.classList.add('notification');
            div.innerHTML = `<strong>${msg.user}</strong>: ${msg.text} <span class="text-xs text-gray-400">${new Date(msg.timestamp).toLocaleTimeString()}</span>`;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
            new Audio('/static/notification.mp3').play();
        }

        async function updateUnreadCount() {
            const res = await fetch('/unread-messages');
            const data = await res.json();
            let totalUnread = 0;
            for (const room of rooms) {
                const count = data[room.slug] || 0;
                document.getElementById(`unread-${room.slug}`).innerText = count > 0 ? count : '';
                totalUnread += count;
            }
            document.getElementById('unread-count').innerText = totalUnread > 0 ? totalUnread : '';
        }

        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            }).then(res => res.json());
            if (res.success) {
                window.location.reload();
            } else {
                alert(res.error || '{{ 'ورود ناموفق: نام کاربری یا رمز عبور اشتباه است' if session.get('lang', 'fa') == 'fa' else 'Login failed: Incorrect username or password' }}');
            }
        });

        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('reg-username').value;
            const email = document.getElementById('reg-email').value;
            const password = document.getElementById('reg-password').value;
            const confirmPassword = document.getElementById('reg-confirm-password').value;
            const avatar = document.getElementById('reg-avatar').files[0];
            if (password !== confirmPassword) {
                alert('{{ 'رمزهای عبور یکسان نیستند' if session.get('lang', 'fa') == 'fa' else 'Passwords do not match' }}');
                return;
            }
            const formData = new FormData();
            formData.append('username', username);
            formData.append('email', email);
            formData.append('password', password);
            if (avatar) formData.append('avatar', avatar);
            const res = await fetch('/register', {
                method: 'POST',
                body: formData
            }).then(res => res.json());
            if (res.success) {
                window.location.reload();
            } else {
                alert(res.error || '{{ 'ثبت‌نام ناموفق' if session.get('lang', 'fa') == 'fa' else 'Registration failed' }}');
            }
        });

        document.getElementById('message-input').addEventListener('input', () => {
            if (currentRoom) {
                socket.emit('typing', { roomId: currentRoom, user: '{{ session.get('user').get('username') if session.get('user') else '' }}' });
            }
        });

        document.getElementById('send-btn').addEventListener('click', () => {
            const message = document.getElementById('message-input').value;
            if (message && currentRoom) {
                socket.emit('sendMessage', { roomId: currentRoom, message, user: {{ session.get('user') | tojson }} });
                document.getElementById('message-input').value = '';
                socket.emit('stopTyping', { roomId: currentRoom });
            }
        });

        socket.on('message', (msg) => {
            displayMessage(msg);
            updateUnreadCount();
        });

        socket.on('typing', (data) => {
            if (data.roomId === currentRoom && data.user !== '{{ session.get('user').get('username') if session.get('user') else '' }}') {
                document.getElementById('typing-indicator').innerText = `${data.user} {{ 'در حال تایپ است...' if session.get('lang', 'fa') == 'fa' else 'is typing...' }}`;
                setTimeout(() => {
                    document.getElementById('typing-indicator').innerText = '';
                }, 3000);
            }
        });

        socket.on('stopTyping', (data) => {
            if (data.roomId === currentRoom) {
                document.getElementById('typing-indicator').innerText = '';
            }
        });

        socket.on('updateUsers', (users) => {
            const onlineUsers = document.getElementById('online-users');
            onlineUsers.innerHTML = '';
            users.forEach(user => {
                const li = document.createElement('li');
                li.classList.add('p-3', 'hover:bg-gray-700', 'rounded-lg', 'cursor-pointer', 'flex', 'items-center');
                li.innerHTML = `<img src="${user.avatar}" class="inline-block h-10 w-10 rounded-full mr-3 shadow-md avatar"> ${user.username}`;
                li.onclick = () => startPrivateChat(user.username);
                onlineUsers.appendChild(li);
            });
        });

        async function changeLanguage(lang) {
            await fetch('/set-language', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lang })
            }).then(() => window.location.reload());
        }

        async function updateProfile() {
            const bio = document.getElementById('bio-input').value;
            const avatar = document.getElementById('avatar-input').files[0];
            const formData = new FormData();
            formData.append('bio', bio);
            if (avatar) formData.append('avatar', avatar);
            await fetch('/profile', {
                method: 'POST',
                body: formData
            }).then(res => res.json()).then(() => window.location.reload());
        }

        async function deleteRoom(slug) {
            if (confirm('{{ 'آیا مطمئن هستید؟' if session.get('lang', 'fa') == 'fa' else 'Are you sure?' }}')) {
                await fetch(`/admin/rooms/${slug}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                }).then(() => window.location.reload());
            }
        }

        async function banUser(userId) {
            if (confirm('{{ 'آیا مطمئن هستید؟' if session.get('lang', 'fa') == 'fa' else 'Are you sure?' }}')) {
                await fetch(`/admin/users/${userId}/ban`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                }).then(() => window.location.reload());
            }
        }

        function startPrivateChat(username) {
            currentPrivateChatUser = username;
            document.getElementById('private-chat-modal').classList.remove('hidden');
            document.getElementById('private-chat-title').innerText = `{{ 'چت خصوصی با' if session.get('lang', 'fa') == 'fa' else 'Private Chat with' }} ${username}`;
            document.getElementById('private-chat-messages').innerHTML = '';
            socket.emit('joinPrivateRoom', { user1: '{{ session.get('user').get('username') if session.get('user') else '' }}', user2: username });
            fetchPrivateMessages(username);
        }

        async function fetchPrivateMessages(toUser) {
            const res = await fetch(`/private-messages/${toUser}`);
            const messages = await res.json();
            messages.forEach(msg => {
                const messages = document.getElementById('private-chat-messages');
                const div = document.createElement('div');
                div.classList.add('chat-bubble', msg.from === '{{ session.get('user').get('username') if session.get('user') else '' }}' ? 'me' : '');
                div.innerHTML = `<strong>${msg.from}</strong>: ${msg.text} <span class="text-xs text-gray-400">${new Date(msg.timestamp).toLocaleTimeString()}</span>`;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            });
        }

        function closePrivateChat() {
            document.getElementById('private-chat-modal').classList.add('hidden');
            currentPrivateChatUser = null;
        }

        document.getElementById('private-send-btn').addEventListener('click', () => {
            const message = document.getElementById('private-message-input').value;
            if (message && currentPrivateChatUser) {
                socket.emit('sendPrivateMessage', {
                    to: currentPrivateChatUser,
                    message,
                    user: {{ session.get('user') | tojson }}
                });
                document.getElementById('private-message-input').value = '';
            }
        });

        socket.on('privateMessage', (msg) => {
            if (msg.from === currentPrivateChatUser || msg.from === '{{ session.get('user').get('username') if session.get('user') else '' }}') {
                const messages = document.getElementById('private-chat-messages');
                const div = document.createElement('div');
                div.classList.add('chat-bubble', msg.from === '{{ session.get('user').get('username') if session.get('user') else '' }}' ? 'me' : '');
                div.innerHTML = `<strong>${msg.from}</strong>: ${msg.text} <span class="text-xs text-gray-400">${new Date(msg.timestamp).toLocaleTimeString()}</span>`;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
                new Audio('/static/notification.mp3').play();
            }
        });
    </script>
</body>
</html>
'''

# Routes
@app.route('/')
def index():
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT * FROM rooms')
    rooms = [{'slug': r[1], 'title': r[2], 'color': r[3], 'banner': r[4]} for r in c.fetchall()]
    conn.close()
    return render_template_string(HTML_TEMPLATE, rooms=rooms)

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username))
    user = c.fetchone()
    if user and check_password_hash(user[3], password):
        session['user'] = {'id': user[0], 'username': user[1], 'email': user[2], 'avatar': user[4], 'bio': user[5], 'is_admin': user[0] == 1}
        c.execute('UPDATE users SET online = 1 WHERE id = ?', (user[0],))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    conn.close()
    return jsonify({'success': False, 'error': 'نام کاربری یا رمز عبور اشتباه است' if session.get('lang', 'fa') == 'fa' else 'Incorrect username or password'}), 401

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    avatar = request.files.get('avatar')
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    avatar_path = '/static/avatars/default.jpg'
    if avatar:
        avatar_filename = f"{username}_{avatar.filename}"
        avatar_path = f"/static/avatars/{avatar_filename}"
        avatar.save(os.path.join('static/avatars', avatar_filename))
    try:
        c.execute('INSERT INTO users (username, email, password, avatar, bio, online) VALUES (?, ?, ?, ?, ?, ?)',
                  (username, email, generate_password_hash(password), avatar_path, '', 1))
        conn.commit()
        session['user'] = {'username': username, 'email': email, 'avatar': avatar_path, 'bio': '', 'is_admin': False}
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError as e:
        conn.close()
        error_msg = 'نام کاربری یا ایمیل قبلاً ثبت شده است' if session.get('lang', 'fa') == 'fa' else 'Username or email already exists'
        return jsonify({'success': False, 'error': error_msg}), 400

@app.route('/set-language', methods=['POST'])
def set_language():
    session['lang'] = request.json.get('lang', 'fa')
    return jsonify({'success': True})

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if not session.get('user'):
        return jsonify({'success': False}), 401
    if request.method == 'POST':
        bio = request.form.get('bio')
        avatar = request.files.get('avatar')
        conn = sqlite3.connect('chatroom.db')
        c = conn.cursor()
        if avatar:
            avatar_filename = f"{session['user']['username']}_{avatar.filename}"
            avatar_path = f"/static/avatars/{avatar_filename}"
            avatar.save(os.path.join('static/avatars', avatar_filename))
            c.execute('UPDATE users SET bio = ?, avatar = ? WHERE id = ?', (bio, avatar_path, session['user']['id']))
            session['user']['avatar'] = avatar_path
        else:
            c.execute('UPDATE users SET bio = ? WHERE id = ?', (bio, session['user']['id']))
        conn.commit()
        session['user']['bio'] = bio
        conn.close()
        return jsonify({'success': True})
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT * FROM rooms')
    rooms = [{'slug': r[1], 'title': r[2], 'color': r[3], 'banner': r[4]} for r in c.fetchall()]
    conn.close()
    return render_template_string(HTML_TEMPLATE, rooms=rooms)

@app.route('/admin', methods=['GET'])
def admin():
    if not session.get('user') or not session.get('user').get('is_admin'):
        return jsonify({'success': False}), 403
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT * FROM rooms')
    rooms = [{'slug': r[1], 'title': r[2], 'color': r[3], 'banner': r[4]} for r in c.fetchall()]
    c.execute('SELECT * FROM users')
    users = [{'id': u[0], 'username': u[1], 'email': u[2], 'online': u[6], 'avatar': u[4]} for u in c.fetchall()]
    conn.close()
    return render_template_string(HTML_TEMPLATE, rooms=rooms, users=users)

@app.route('/admin/rooms/<slug>', methods=['DELETE'])
def delete_room(slug):
    if not session.get('user') or not session.get('user').get('is_admin'):
        return jsonify({'success': False}), 403
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('DELETE FROM rooms WHERE slug = ?', (slug,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/users/<user_id>/ban', methods=['POST'])
def ban_user(user_id):
    if not session.get('user') or not session.get('user').get('is_admin'):
        return jsonify({'success': False}), 403
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/messages/<room_id>', methods=['GET'])
def get_messages(room_id):
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT u.username, m.text, m.timestamp FROM messages m JOIN users u ON m.user_id = u.id JOIN rooms r ON m.room_id = r.id WHERE r.slug = ?', (room_id,))
    messages = [{'user': r[0], 'text': r[1], 'timestamp': r[2]} for r in c.fetchall()]
    c.execute('UPDATE messages SET read = 1 WHERE room_id = (SELECT id FROM rooms WHERE slug = ?) AND read = 0', (room_id,))
    conn.commit()
    conn.close()
    return jsonify(messages)

@app.route('/private-messages/<to_user>', methods=['GET'])
def get_private_messages(to_user):
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT u1.username, pm.text, pm.timestamp FROM private_messages pm '
              'JOIN users u1 ON pm.from_user_id = u1.id '
              'JOIN users u2 ON pm.to_user_id = u2.id '
              'WHERE (u1.username = ? AND u2.username = ?) OR (u1.username = ? AND u2.username = ?)',
              (session['user']['username'], to_user, to_user, session['user']['username']))
    messages = [{'from': r[0], 'text': r[1], 'timestamp': r[2]} for r in c.fetchall()]
    c.execute('UPDATE private_messages SET read = 1 WHERE to_user_id = (SELECT id FROM users WHERE username = ?) AND from_user_id = (SELECT id FROM users WHERE username = ?) AND read = 0',
              (session['user']['username'], to_user))
    conn.commit()
    conn.close()
    return jsonify(messages)

@app.route('/unread-messages', methods=['GET'])
def get_unread_messages():
    if not session.get('user'):
        return jsonify({}), 401
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT r.slug, COUNT(m.id) FROM messages m JOIN rooms r ON m.room_id = r.id WHERE m.read = 0 GROUP BY r.slug')
    unread = {r[0]: r[1] for r in c.fetchall()}
    conn.close()
    return jsonify(unread)

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    room_id = request.form.get('roomId')
    if file and room_id:
        file_filename = f"{session['user']['username']}_{file.filename}"
        file_path = f"/static/uploads/{file_filename}"
        file.save(os.path.join('static/uploads', file_filename))
        return jsonify({'success': True, 'fileUrl': file_path})
    return jsonify({'success': False, 'error': 'فایل یا روم انتخاب نشده' if session.get('lang', 'fa') == 'fa' else 'No file or room selected'}), 400

@socketio.on('joinRoom')
def on_join_room(data):
    join_room(data['roomId'])
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT username, avatar FROM users WHERE online = 1')
    users = [{'username': u[0], 'avatar': u[1]} for u in c.fetchall()]
    conn.close()
    emit('updateUsers', users, room=data['roomId'])
    emit('message', {
        'user': 'System',
        'text': f"{data['user']['username']} joined the room!",
        'timestamp': datetime.now().isoformat()
    }, room=data['roomId'])

@socketio.on('joinPrivateRoom')
def on_join_private_room(data):
    room_id = f"private_{min(data['user1'], data['user2'])}_{max(data['user1'], data['user2'])}"
    join_room(room_id)
    emit('privateRoomJoined', {'roomId': room_id}, to=room_id)

@socketio.on('sendMessage')
def on_send_message(data):
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('SELECT id FROM rooms WHERE slug = ?', (data['roomId'],))
    room = c.fetchone()
    if room:
        room_id = room[0]
        c.execute('INSERT INTO messages (room_id, user_id, text, timestamp) VALUES (?, (SELECT id FROM users WHERE username = ?), ?, ?)',
                  (room_id, data['user']['username'], data['message'], datetime.now().isoformat()))
        conn.commit()
        emit('message', {
            'user': data['user']['username'],
            'text': data['message'],
            'timestamp': datetime.now().isoformat()
        }, room=data['roomId'])
    conn.close()

@socketio.on('sendPrivateMessage')
def on_send_private_message(data):
    conn = sqlite3.connect('chatroom.db')
    c = conn.cursor()
    c.execute('INSERT INTO private_messages (from_user_id, to_user_id, text, timestamp) VALUES '
              '((SELECT id FROM users WHERE username = ?), (SELECT id FROM users WHERE username = ?), ?, ?)',
              (data['user']['username'], data['to'], data['message'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    room_id = f"private_{min(data['user']['username'], data['to'])}_{max(data['user']['username'], data['to'])}"
    emit('privateMessage', {
        'from': data['user']['username'],
        'text': data['message'],
        'timestamp': datetime.now().isoformat()
    }, room=room_id)

@socketio.on('typing')
def on_typing(data):
    emit('typing', data, room=data['roomId'], broadcast=True)

@socketio.on('stopTyping')
def on_stop_typing(data):
    emit('stopTyping', data, room=data['roomId'], broadcast=True)

if __name__ == '__main__':
    os.makedirs('static/avatars', exist_ok=True)
    os.makedirs('static/uploads', exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=5000)