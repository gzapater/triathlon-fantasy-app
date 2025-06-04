document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const messageArea = document.getElementById('messageArea');
    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        messageArea.textContent = '';
        messageArea.className = 'message';
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ username, password }),
            });
            
            // DEBUG: Loggear headers de respuesta
            console.log('=== LOGIN RESPONSE DEBUG ===');
            console.log('Status:', response.status);
            console.log('Headers:');
            for (let [key, value] of response.headers.entries()) {
                console.log(`  ${key}: ${value}`);
            }
            console.log('Cookies después del login:', document.cookie);
            console.log('==========================');
            
            const result = await response.json();
            if (response.ok) {
                messageArea.textContent = result.message || 'Login successful! Redirecting...';
                messageArea.classList.add('success');
                
                // Esperar un poco más para asegurar que las cookies se establecen
                setTimeout(() => {
                    console.log('Cookies antes de redirect:', document.cookie);
                    window.location.href = '/Hello-world';
                }, 2000); // Aumentado a 2 segundos
            } else {
                messageArea.textContent = result.message || 'Login failed. Check username or password.';
                messageArea.classList.add('error');
            }
        } catch (error) {
            console.error('Login error:', error);
            messageArea.textContent = 'An error occurred during login. Please try again.';
            messageArea.classList.add('error');
        }
    });
});
