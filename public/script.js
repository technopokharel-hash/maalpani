const API_URL = '/api';

// --- UTILS ---
function getToken() { return localStorage.getItem('token'); }
function setToken(token) { localStorage.setItem('token', token); }
function logout() { localStorage.removeItem('token'); window.location.href = '/login.html'; }

// --- SIDEBAR TOGGLE (New Change) ---
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.toggle('collapsed');
}

// --- AUTH ---
async function handleAuth(type, event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const btn = event.target.querySelector('button');
    const originalText = btn.innerText;
    
    btn.innerText = "Loading...";
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
                // Store username for the sidebar display
                localStorage.setItem('display_name', username);
                window.location.href = '/index.html';
            } else {
                alert('Account created! Please login.');
                window.location.href = '/login.html';
            }
        } else {
            alert(data.error);
        }
    } catch (err) {
        alert('Something went wrong.');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

// --- CHAT ---
if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
    if (!getToken()) window.location.href = '/login.html';
    
    // Updated IDs to match new GURU HTML
    const chatContainer = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const userDisplayName = document.getElementById('user-display-name');

    // Show the logged-in user's name in sidebar
    if (userDisplayName) {
        userDisplayName.innerText = localStorage.getItem('display_name') || 'Student User';
    }

    function appendMessage(role, text) {
        const div = document.createElement('div');
        // Updated classes to match the new school-themed CSS
        div.className = `message ${role === 'user' ? 'user' : 'ai'}`;
        div.innerHTML = `
            <div class="bubble">
                ${text}
            </div>
        `;
        chatContainer.appendChild(div);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return div.querySelector('.bubble');
    }

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        chatInput.value = '';
        appendMessage('user', message);
        
        const loadingDiv = appendMessage('ai', 'GURU is thinking...');
        loadingDiv.classList.add('typing');

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
            
            loadingDiv.classList.remove('typing');
            if (res.ok) {
                // Use innerText to keep it clean, or innerHTML if you want Gemini's Markdown
                loadingDiv.innerText = data.reply; 
            } else {
                loadingDiv.innerText = "Error: " + data.error;
            }
        } catch (err) {
            loadingDiv.classList.remove('typing');
            loadingDiv.innerText = "Error: Failed to connect to server.";
        }
    }

    document.getElementById('send-btn').addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}