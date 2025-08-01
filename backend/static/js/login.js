document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const messageArea = document.getElementById('messageArea');
    const usernameInput = document.getElementById('username');

    // Leer el parámetro 'next' de la URL al cargar la página
    const queryParams = new URLSearchParams(window.location.search);
    const nextUrlFromQuery = queryParams.get('next');
    if (nextUrlFromQuery) {
        console.log('Login page loaded with next URL from query:', nextUrlFromQuery);
    }
    const passwordInput = document.getElementById('password');
    const rememberMeCheckbox = document.getElementById('remember-me');

    // Pre-fill form on page load if "Remember me" was checked previously
    if (localStorage.getItem('rememberedUser') && localStorage.getItem('rememberedPassword')) {
        usernameInput.value = localStorage.getItem('rememberedUser');
        passwordInput.value = localStorage.getItem('rememberedPassword');
        rememberMeCheckbox.checked = true;
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        // Hide message area initially on new submit, then clear content and classes
        messageArea.style.display = 'none';
        messageArea.textContent = '';
        messageArea.className = 'message'; // Base class, specific (e.g., error, success) added below
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        showLoadingBar();
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
                messageArea.style.display = 'block'; // Show success message

                // Handle "Remember me" functionality
                if (rememberMeCheckbox.checked) {
                    localStorage.setItem('rememberedUser', username);
                    localStorage.setItem('rememberedPassword', password);
                    console.warn("Storing password in localStorage is not recommended for production environments due to security risks.");
                } else {
                    localStorage.removeItem('rememberedUser');
                    localStorage.removeItem('rememberedPassword');
                }
                
                // Esperar un poco más para asegurar que las cookies se establecen
                setTimeout(() => {
                    console.log('Cookies antes de redirect:', document.cookie);
                    if (nextUrlFromQuery && nextUrlFromQuery.startsWith('/')) {
                        console.log('Redirecting to nextUrlFromQuery:', nextUrlFromQuery);
                        window.location.href = nextUrlFromQuery;
                    } else {
                        if (nextUrlFromQuery) {
                            console.warn('nextUrlFromQuery is present but invalid (not starting with /):', nextUrlFromQuery, 'Defaulting to /Hello-world.');
                        } else {
                            console.log('No valid nextUrlFromQuery found. Redirecting to default /Hello-world.');
                        }
                        window.location.href = '/Hello-world';
                    }
                }, 2000); // Mantener el timeout si es necesario por las cookies
            } else {
                if (response.status === 401) {
                    messageArea.textContent = "Las crdenciales son incorrectas, por favor prueba de nuevo.";
                } else {
                    messageArea.textContent = result.message || 'Login failed. Please check your input or try again later.';
                }
                messageArea.classList.add('error');
                messageArea.style.display = 'block'; // Show error message
            }
        } catch (error) {
            console.error('Login error:', error);
            messageArea.textContent = 'An error occurred during login. Please try again.';
            messageArea.classList.add('error');
            messageArea.style.display = 'block'; // Show catch block error message
        } finally {
            hideLoadingBar();
        }
    });
});
