document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const messageArea = document.getElementById('messageArea');

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        messageArea.textContent = ''; // Clear previous messages
        messageArea.className = 'message'; // Reset class

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            const result = await response.json();

            if (response.ok) {
                messageArea.textContent = result.message || 'Login successful! Redirecting...';
                messageArea.classList.add('success');
                // Store token if using JWT, or rely on session cookie if using Flask-Login
                if (result.token) { // Example for JWT
                    localStorage.setItem('authToken', result.token);
                }
                // Redirect to the Hello-world page
                setTimeout(() => {
                    window.location.href = '/Hello-world';
                }, 1500);
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
