document.addEventListener('DOMContentLoaded', () => {
    const helloButton = document.getElementById('helloButton');
    const messageArea = document.getElementById('messageArea');
    const logoutButton = document.getElementById('logoutButton'); 
    const userRoleDisplay = document.getElementById('user-role-display');

    // Buttons for role-specific data
    const generalAdminDataButton = document.getElementById('general-admin-data-button');
    const leagueAdminDataButton = document.getElementById('league-admin-data-button');
    const userDataButton = document.getElementById('user-data-button');

    // Initially hide all role-specific buttons (though CSS also does this)
    if(generalAdminDataButton) generalAdminDataButton.style.display = 'none';
    if(leagueAdminDataButton) leagueAdminDataButton.style.display = 'none';
    if(userDataButton) userDataButton.style.display = 'none';

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

    if (logoutButton) { 
        logoutButton.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/logout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                if(userRoleDisplay) userRoleDisplay.textContent = '';
                if(generalAdminDataButton) generalAdminDataButton.style.display = 'none';
                if(leagueAdminDataButton) leagueAdminDataButton.style.display = 'none';
                if(userDataButton) userDataButton.style.display = 'none';
                messageArea.textContent = 'Logout successful. Redirecting to login...';
                setTimeout(() => { window.location.href = '/login'; }, 1500);
            } catch (error) {
                console.error('Logout request error:', error);
                messageArea.textContent = 'An error occurred during logout.';
            }
        });
    }

    async function fetchAndDisplayUserDetails() {
        if (!userRoleDisplay) {
            console.log("User role display element not found.");
            return; 
        }
        // Hide all buttons initially before fetching details
        if(generalAdminDataButton) generalAdminDataButton.style.display = 'none';
        if(leagueAdminDataButton) leagueAdminDataButton.style.display = 'none';
        if(userDataButton) userDataButton.style.display = 'none';

        try {
            const response = await fetch('/api/user/me');
            if (response.ok) {
                const data = await response.json();
                userRoleDisplay.textContent = `Welcome, ${data.username}! You are logged in as a ${data.role}.`;

                // Show buttons based on role
                if (data.role === 'general_admin') {
                    if(generalAdminDataButton) generalAdminDataButton.style.display = 'inline-block';
                    if(leagueAdminDataButton) leagueAdminDataButton.style.display = 'inline-block';
                } else if (data.role === 'league_admin') {
                    if(leagueAdminDataButton) leagueAdminDataButton.style.display = 'inline-block';
                } else if (data.role === 'user') {
                    if(userDataButton) userDataButton.style.display = 'inline-block';
                }
            } else {
                userRoleDisplay.textContent = ''; 
                if (response.status === 401) {
                   console.log("User not authenticated, /api/user/me returned 401. Page should redirect via Flask @login_required.");
                }
            }
        } catch (error) {
            console.error('Error fetching user details:', error);
            if(userRoleDisplay) userRoleDisplay.textContent = 'An error occurred while fetching user details.';
        }
    }

    async function fetchDataForButton(endpoint, buttonElement) {
        if (!buttonElement) return;
        messageArea.textContent = 'Fetching data...';
        try {
            const response = await fetch(endpoint);
            const result = await response.json();
            if (response.ok) {
                messageArea.textContent = result.message;
            } else {
                messageArea.textContent = `Error: ${result.message || response.statusText}`;
            }
        } catch (error) {
            console.error(`Error fetching from ${endpoint}:`, error);
            messageArea.textContent = `Failed to fetch data from ${endpoint}.`;
        }
    }

    if(generalAdminDataButton) {
        generalAdminDataButton.addEventListener('click', () => fetchDataForButton('/api/admin/general_data', generalAdminDataButton));
    }
    if(leagueAdminDataButton) {
        leagueAdminDataButton.addEventListener('click', () => fetchDataForButton('/api/admin/league_data', leagueAdminDataButton));
    }
    if(userDataButton) {
        userDataButton.addEventListener('click', () => fetchDataForButton('/api/user/personal_data', userDataButton));
    }

    fetchAndDisplayUserDetails();
});
