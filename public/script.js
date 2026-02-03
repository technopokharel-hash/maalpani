const API_URL = '/api';

// --- UTILS ---
function getToken() { return localStorage.getItem('token'); }
function setToken(token) { localStorage.setItem('token', token); }
function logout() { localStorage.removeItem('token'); window.location.href = '/login.html'; }

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
    
    const chatContainer = document.getElementById('chat-container');
    const chatInput = document.getElementById('chat-input');

    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `message-row ${role === 'user' ? 'user' : 'ai'}`;
        div.innerHTML = `
            <div class="message-content">
                <div class="avatar ${role === 'user' ? 'user-avatar' : 'ai-avatar'}">
                    ${role === 'user' ? '👤' : '🤖'}
                </div>
                <div class="text">${text}</div>
            </div>
        `;
        chatContainer.appendChild(div);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return div.querySelector('.text');
    }

    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        chatInput.value = '';
        appendMessage('user', message);
        
        const loadingDiv = appendMessage('ai', 'Thinking...');
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
                loadingDiv.innerText = data.reply; // Using innerText handles basic formatting safer
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