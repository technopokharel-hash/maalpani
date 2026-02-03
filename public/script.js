const API_URL = '/api';

// --- UTILS ---
function getToken() { return localStorage.getItem('token'); }
function setToken(token) { localStorage.setItem('token', token); }
function logout() { 
    localStorage.removeItem('token'); 
    localStorage.removeItem('display_name');
    window.location.href = '/login.html'; 
}

// --- SIDEBAR & UI CONTROLS ---
function toggleSidebar() {
    const sb = document.getElementById('sidebar');
    if (sb) {
        sb.classList.toggle('w-0');
        sb.classList.toggle('opacity-0');
        sb.classList.toggle('-translate-x-full');
    }
}

function toggleDarkMode() {
    const html = document.documentElement;
    const isDark = html.classList.toggle('dark');
    const icon = document.getElementById('dark-mode-icon');
    if (icon) icon.innerText = isDark ? '☀️' : '🌙';
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// --- AUTHENTICATION ---
async function handleAuth(type, event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const btn = event.target.querySelector('button');
    const originalText = btn.innerText;
    
    btn.innerText = "Verifying...";
    btn.disabled = true;

    try {
        const res = await fetch(`${API_URL}/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await res.json();
        
        if (res.ok) {
            if (type === 'login') {
                setToken(data.token);
                localStorage.setItem('display_name', username);
                window.location.href = '/index.html';
            } else {
                alert('Account created! Welcome to Xavier\'s.');
                window.location.href = '/login.html';
            }
        } else {
            alert(data.error || "Authentication failed");
        }
    } catch (err) {
        alert('Server connection error.');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

// --- CHAT LOGIC ---
if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
    // Redirect if not logged in
    if (!getToken()) window.location.href = '/login.html';
    
    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const userDisplayName = document.getElementById('user-display-name');

    // Set User Name in Sidebar
    if (userDisplayName) {
        userDisplayName.innerText = localStorage.getItem('display_name') || 'Student';
    }

    // Function to add a message bubble to the UI
    function appendMessage(role, text) {
        const div = document.createElement('div');
        // Tailwind classes for message layout
        div.className = `flex gap-4 ${role === 'user' ? 'flex-row-reverse' : ''}`;
        
        const bgColor = role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-zinc-800 dark:text-gray-100';
        const rounded = role === 'user' ? 'rounded-2xl rounded-tr-none' : 'rounded-2xl rounded-tl-none';
        const icon = role === 'user' ? 'U' : 'G';
        const iconColor = role === 'user' ? 'bg-gray-500' : 'bg-amber-500';

        div.innerHTML = `
            <div class="w-8 h-8 rounded-lg ${iconColor} flex-shrink-0 flex items-center justify-center text-white text-xs font-bold shadow-sm">${icon}</div>
            <div class="${bgColor} ${rounded} p-4 max-w-[80%] shadow-sm text-sm transition-all animate-in fade-in slide-in-from-bottom-2">
                ${text}
            </div>
        `;
        
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
        return div.querySelector('div:last-child'); // Returns the bubble element
    }

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        chatInput.value = '';
        appendMessage('user', message);
        
        // Show Typing State
        const loadingDiv = appendMessage('ai', 'GURU is thinking...');
        loadingDiv.classList.add('animate-pulse', 'italic', 'text-gray-400');

        try {
            const res = await fetch(`${API_URL}/chat`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${getToken()}` 
                },
                body: JSON.stringify({ message })
            });
            
            const data = await res.json();
            loadingDiv.classList.remove('animate-pulse', 'italic', 'text-gray-400');

            if (res.status === 429) {
                loadingDiv.innerHTML = "⚠️ <b>Quota Exceeded:</b> GURU is getting too many questions right now! Please wait 60 seconds and try again.";
                loadingDiv.classList.add('text-red-500', 'bg-red-50', 'dark:bg-red-900/20');
            } else if (res.ok) {
                loadingDiv.innerText = data.reply;
            } else {
                loadingDiv.innerText = "Error: " + (data.error || "Something went wrong.");
            }
        } catch (err) {
            loadingDiv.classList.remove('animate-pulse');
            loadingDiv.innerText = "Connection lost. Please check your network.";
        }
    }

    // Event Listeners
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Initialize Theme on Load
    if (localStorage.getItem('theme') === 'dark') {
        document.documentElement.classList.add('dark');
        const icon = document.getElementById('dark-mode-icon');
        if (icon) icon.innerText = '☀️';
    }

    // In your script.js fetch calls:
const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: userMessage }),
    credentials: 'include' // <--- ADD THIS LINE
});
}