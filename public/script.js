// --- CONFIGURATION ---
const API_URL = '/api';

// --- AUTHENTICATION (Login/Signup) ---
async function handleAuth(type, event) {
    event.preventDefault(); // FIX: Stops the "?" question mark/page refresh bug
    
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const submitBtn = document.getElementById(`${type}-btn`);

    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();

    if (!username || !password) return;

    submitBtn.innerText = "Verifying...";
    submitBtn.disabled = true;

    try {
        const res = await fetch(`${API_URL}/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
            credentials: 'include' // Allows browser to save the login cookie
        });
        
        const data = await res.json();
        
        if (res.ok) {
            localStorage.setItem('display_name', username);
            if (type === 'login') {
                window.location.href = '/index.html';
            } else {
                alert('Account created! You can now log in.');
                window.location.href = '/login.html';
            }
        } else {
            alert(data.error || "Authentication failed");
        }
    } catch (err) {
        alert('GURU Server Connection Error');
    } finally {
        submitBtn.innerText = type === 'login' ? 'Log In' : 'Register';
        submitBtn.disabled = false;
    }
}

// --- CHAT LOGIC ---
async function sendMessage() {
    const chatInput = document.getElementById('user-input'); // Changed to match your index.html
    const chatBox = document.getElementById('chat-container');
    const message = chatInput.value.trim();

    if (!message) return;

    chatInput.value = '';
    appendMessage('user', message);
    
    // Create GURU thinking bubble
    const loadingDiv = appendMessage('model', 'GURU is thinking...');
    loadingDiv.classList.add('animate-pulse', 'italic', 'text-gray-400');

    try {
        const res = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
            credentials: 'include' // Important for session history
        });
        
        const data = await res.json();
        
        // Remove the pulse/thinking text once the reply is ready
        loadingDiv.classList.remove('animate-pulse', 'italic', 'text-gray-400');

        if (res.status === 429) {
            loadingDiv.innerHTML = "⚠️ <b>GURU is resting:</b> Daily limit reached. Try again in 60 seconds.";
            loadingDiv.classList.add('text-amber-600');
        } else if (res.ok) {
            loadingDiv.innerText = data.reply;
        } else {
            if (res.status === 401) window.location.href = '/login.html';
            loadingDiv.innerText = "Error: " + (data.error || "Something went wrong.");
        }
    } catch (err) {
        loadingDiv.innerText = "Connection lost. Please check your network.";
    }
}

// --- MESSAGE RENDERING ---
function appendMessage(role, text) {
    const chatContainer = document.getElementById('chat-container');
    const isAI = role === 'model';
    
    const div = document.createElement('div');
    div.className = `flex gap-4 ${!isAI ? 'flex-row-reverse' : ''} mb-4`;
    
    div.innerHTML = `
        <div class="w-8 h-8 rounded-lg ${isAI ? 'bg-blue-600' : 'bg-slate-500'} flex-shrink-0 flex items-center justify-center text-white text-xs font-bold shadow-sm">
            ${isAI ? 'G' : 'U'}
        </div>
        <div class="${isAI ? 'bg-white dark:bg-zinc-800 text-slate-800 dark:text-slate-100 rounded-tl-none border border-slate-100 dark:border-zinc-700' : 'bg-blue-600 text-white rounded-tr-none'} p-4 rounded-2xl max-w-[85%] shadow-sm text-sm transition-all">
            ${text}
        </div>
    `;
    
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return div.querySelector('div:last-child p') || div.querySelector('div:last-child');
}

// --- EVENT LISTENER INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    // Determine which page we are on and attach the correct listener
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const chatForm = document.getElementById('chat-form');

    if (loginForm) loginForm.addEventListener('submit', (e) => handleAuth('login', e));
    if (signupForm) signupForm.addEventListener('submit', (e) => handleAuth('signup', e));
    
    if (chatForm) {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            sendMessage();
        });
    }

    // Load User Name
    const display = document.getElementById('display-name');
    if (display) display.innerText = localStorage.getItem('display_name') || 'Student';
});

function formatText(text) {
    // Simple logic to convert **text** to <b>text</b> and new lines to <br>
    return text
        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') 
        .replace(/\n/g, '<br>');
}

// Then in your appendMessage use:
// div.innerHTML = `... <p>${formatText(text)}</p> ...`;