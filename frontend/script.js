document.addEventListener('DOMContentLoaded', () => {
    const helloButton = document.getElementById('helloButton');
    const messageArea = document.getElementById('messageArea');
    const logoutButton = document.getElementById('logoutButton'); // Get the logout button

    if (helloButton) { // Ensure helloButton exists
        helloButton.addEventListener('click', () => {
            // The existing fetch to /api/hello will be updated later
            // to ensure it sends credentials if needed (e.g. for @login_required)
            // For now, assuming it might work or will be fixed in Step 5
            fetch('/api/hello') // Assuming this is the correct endpoint for the hello message
                .then(response => {
                    if (response.status === 401) { // Unauthorized
                        window.location.href = '/login'; // Redirect to login
                        return; // Stop processing
                    }
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data) { // Check if data is not undefined (e.g. after a redirect)
                       messageArea.textContent = data.message;
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    messageArea.textContent = 'Error fetching message from backend. You might need to login.';
                });
        });
    }

    if (logoutButton) { // Ensure logoutButton exists
        logoutButton.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/logout', {
                    method: 'POST',
                    headers: {
                        // If using CSRF tokens with Flask-Login, they might need to be included here.
                        // For now, assuming basic session cookie authentication.
                        'Content-Type': 'application/json',
                    }
                });

                if (response.ok) {
                    // Successfully logged out
                    messageArea.textContent = 'Logout successful. Redirecting to login...';
                    // Clear any stored auth tokens if using JWT (though we are using sessions here)
                    // localStorage.removeItem('authToken');
                    setTimeout(() => {
                        window.location.href = '/login'; // Redirect to login page
                    }, 1500);
                } else {
                    // Handle errors, e.g., if the session had already expired server-side
                    const result = await response.json().catch(() => null); // Try to parse error
                    messageArea.textContent = result ? result.message : 'Logout failed. Please try again.';
                    console.error('Logout failed:', result ? result.message : response.status);
                     // If logout fails due to not being logged in (e.g. session expired), still redirect to login.
                    if(response.status === 401){
                         setTimeout(() => {
                            window.location.href = '/login';
                        }, 1500);
                    }
                }
            } catch (error) {
                console.error('Logout request error:', error);
                messageArea.textContent = 'An error occurred during logout.';
            }
        });
    }
});
