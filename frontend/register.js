document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('registerForm');
    const messageArea = document.getElementById('messageArea');

    registerForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        messageArea.textContent = ''; // Clear previous messages
        messageArea.className = 'message'; // Reset class

        const name = document.getElementById('name').value;
        const username = document.getElementById('username').value;
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name, username, email, password }),
            });

            const result = await response.json();

            if (response.ok) {
                messageArea.textContent = result.message || 'Registration successful! Redirecting to login...';
                messageArea.classList.add('success');
                // Redirect to login page after a short delay
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else {
                messageArea.textContent = result.message || 'Registration failed.';
                messageArea.classList.add('error');
            }
        } catch (error) {
            console.error('Registration error:', error);
            messageArea.textContent = 'An error occurred during registration. Please try again.';
            messageArea.classList.add('error');
        }
    });
});
