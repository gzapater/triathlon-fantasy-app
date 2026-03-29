document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const messageArea = document.getElementById('messageArea');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const rememberMeCheckbox = document.getElementById('remember-me');
    const googleSection = document.getElementById('google-login-section');
    const googleClientId = googleSection?.dataset.googleClientId;

    const queryParams = new URLSearchParams(window.location.search);
    const nextUrlFromQuery = queryParams.get('next');
    if (nextUrlFromQuery) {
        console.log('Login page loaded with next URL from query:', nextUrlFromQuery);
    }

    function showMessage(text, type) {
        messageArea.style.display = 'block';
        messageArea.textContent = text;
        messageArea.className = 'mt-4 text-center text-sm';
        if (type) {
            messageArea.classList.add(type);
        }
    }

    function clearMessage() {
        messageArea.style.display = 'none';
        messageArea.textContent = '';
        messageArea.className = 'mt-4 text-center text-sm';
    }

    function redirectAfterLogin() {
        setTimeout(() => {
            console.log('Cookies before redirect:', document.cookie);
            if (nextUrlFromQuery && nextUrlFromQuery.startsWith('/')) {
                window.location.href = nextUrlFromQuery;
                return;
            }

            if (nextUrlFromQuery) {
                console.warn('Ignoring invalid next URL:', nextUrlFromQuery);
            }
            window.location.href = '/Hello-world';
        }, 1200);
    }

    async function submitGoogleCredential(credential) {
        clearMessage();
        showLoadingBar();

        try {
            const response = await fetch('/api/login/google', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ credential }),
            });

            const result = await response.json();
            if (!response.ok) {
                showMessage(result.message || 'No se pudo iniciar sesión con Google.', 'error');
                return;
            }

            showMessage(result.message || 'Login successful! Redirecting...', 'success');
            redirectAfterLogin();
        } catch (error) {
            console.error('Google login error:', error);
            showMessage('Ha ocurrido un error al iniciar sesión con Google. Vuelve a intentarlo.', 'error');
        } finally {
            hideLoadingBar();
        }
    }

    function handleGoogleLoginSuccess(response) {
        if (!response?.credential) {
            showMessage('Google no ha devuelto una credencial válida.', 'error');
            return;
        }
        submitGoogleCredential(response.credential);
    }

    function initializeGoogleSignIn(retries = 20) {
        if (!googleClientId || !googleSection) {
            return;
        }

        if (!window.google?.accounts?.id) {
            if (retries > 0) {
                window.setTimeout(() => initializeGoogleSignIn(retries - 1), 300);
            } else {
                showMessage('No hemos podido cargar el acceso con Google. Recarga la página e inténtalo de nuevo.', 'error');
            }
            return;
        }

        google.accounts.id.initialize({
            client_id: googleClientId,
            callback: handleGoogleLoginSuccess,
            auto_select: false,
            cancel_on_tap_outside: true,
        });

        google.accounts.id.renderButton(
            document.getElementById('googleSignInButton'),
            {
                theme: 'outline',
                size: 'large',
                shape: 'rectangular',
                text: 'signin_with',
                width: 320,
                logo_alignment: 'left',
            }
        );
    }

    if (localStorage.getItem('rememberedUser') && localStorage.getItem('rememberedPassword')) {
        usernameInput.value = localStorage.getItem('rememberedUser');
        passwordInput.value = localStorage.getItem('rememberedPassword');
        rememberMeCheckbox.checked = true;
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearMessage();
        const username = usernameInput.value;
        const password = passwordInput.value;
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

            console.log('=== LOGIN RESPONSE DEBUG ===');
            console.log('Status:', response.status);
            console.log('Headers:');
            for (const [key, value] of response.headers.entries()) {
                console.log(`  ${key}: ${value}`);
            }
            console.log('Cookies después del login:', document.cookie);
            console.log('==========================');

            const result = await response.json();
            if (response.ok) {
                showMessage(result.message || 'Login successful! Redirecting...', 'success');

                if (rememberMeCheckbox.checked) {
                    localStorage.setItem('rememberedUser', username);
                    localStorage.setItem('rememberedPassword', password);
                    console.warn('Storing password in localStorage is not recommended for production environments due to security risks.');
                } else {
                    localStorage.removeItem('rememberedUser');
                    localStorage.removeItem('rememberedPassword');
                }

                redirectAfterLogin();
                return;
            }

            if (response.status === 401) {
                showMessage('Las credenciales son incorrectas, por favor prueba de nuevo.', 'error');
            } else {
                showMessage(result.message || 'Login failed. Please check your input or try again later.', 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            showMessage('An error occurred during login. Please try again.', 'error');
        } finally {
            hideLoadingBar();
        }
    });

    initializeGoogleSignIn();
});
