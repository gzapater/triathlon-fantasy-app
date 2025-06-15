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

        // Event Listener for Save Button
        saveOfficialAnswersBtn.addEventListener('click', async function() {
            const selectedRaceId = officialAnswersRaceSelect.value;
            if (!selectedRaceId) {
                alert('Please select a race first.');
                return;
            }

            const officialAnswersPayload = {};
            const questionDivs = officialAnswersQuestionsContainer.querySelectorAll('div[data-question-id]');

            questionDivs.forEach(qDiv => {
                const questionId = qDiv.dataset.questionId;
                const questionType = qDiv.dataset.questionType;
                const isMcMultipleCorrect = qDiv.dataset.isMcMultipleCorrect === 'true';
                let answerData = {};

                switch (questionType) {
                    case 'FREE_TEXT':
                        const textarea = qDiv.querySelector('textarea');
                        answerData.answer_text = textarea ? textarea.value.trim() : null;
                        break;
                    case 'MULTIPLE_CHOICE':
                        if (isMcMultipleCorrect) {
                            const checkedBoxes = qDiv.querySelectorAll('input[type="checkbox"]:checked');
                            answerData.selected_option_ids = Array.from(checkedBoxes).map(cb => parseInt(cb.value));
                        } else {
                            const selectedRadio = qDiv.querySelector('input[type="radio"]:checked');
                            answerData.selected_option_id = selectedRadio ? parseInt(selectedRadio.value) : null;
                        }
                        break;
                    case 'ORDERING':
                        const orderingTextarea = qDiv.querySelector('textarea');
                        answerData.ordered_options_text = orderingTextarea ? orderingTextarea.value.trim() : null;
                        break;
                    default:
                        console.warn(`Unsupported question type ${questionType} for question ID ${questionId}. Skipping.`);
                        return; // Skip this question
                }
                officialAnswersPayload[questionId] = answerData;
            });

            // console.log('Payload to send:', JSON.stringify(officialAnswersPayload, null, 2)); // For debugging

            saveOfficialAnswersBtn.disabled = true;
            saveOfficialAnswersBtn.textContent = 'Saving...';
            let messageElement = officialAnswersQuestionsContainer.querySelector('.save-message');
            if (messageElement) messageElement.remove(); // Remove old message

            messageElement = document.createElement('p');
            messageElement.classList.add('mt-4', 'text-center', 'save-message');
            officialAnswersQuestionsContainer.appendChild(messageElement);


            try {
                const response = await fetch(`/api/races/${selectedRaceId}/official_answers`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // Include CSRF token if needed by your Flask setup
                    },
                    body: JSON.stringify(officialAnswersPayload)
                });

                const responseData = await response.json();

                if (response.ok) {
                    messageElement.textContent = `Official answers saved successfully for race ${selectedRaceId}!`;
                    messageElement.classList.remove('text-red-500');
                    messageElement.classList.add('text-green-600', 'font-semibold');
                     // Optionally, reload answers to reflect any backend processing or new IDs
                    // officialAnswersRaceSelect.dispatchEvent(new Event('change'));
                } else {
                    messageElement.textContent = `Error: ${responseData.message || response.statusText}`;
                    messageElement.classList.remove('text-green-600');
                    messageElement.classList.add('text-red-500', 'font-semibold');
                }
            } catch (error) {
                console.error('Error saving official answers:', error);
                messageElement.textContent = 'An unexpected error occurred while saving. Please check console and try again.';
                messageElement.classList.remove('text-green-600');
                messageElement.classList.add('text-red-500', 'font-semibold');
            } finally {
                saveOfficialAnswersBtn.disabled = false;
                saveOfficialAnswersBtn.textContent = 'Guardar Respuestas Oficiales';
                // Auto-remove message after a few seconds
                setTimeout(() => {
                    if (messageElement) messageElement.remove();
                }, 7000);
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

    // --- End of Official Answers Section Logic ---
});
