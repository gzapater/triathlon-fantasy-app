// Global Loading Bar Elements
const loadingOverlay = document.getElementById('loading-overlay');
const loadingProgress = document.getElementById('loading-progress');
let _loadingInterval = null;

function showLoadingBar() {
    if (!loadingOverlay || !loadingProgress) {
        console.error('Loading bar elements not found!');
        return;
    }
    let width = 0;
    loadingProgress.style.width = '0%';
    loadingProgress.textContent = '0%';
    loadingOverlay.style.display = 'flex'; // Use flex to center content

    // Clear any existing interval
    if (_loadingInterval) {
        clearInterval(_loadingInterval);
    }

    _loadingInterval = setInterval(() => {
        if (width >= 100) {
            width = 0; // Reset and loop for visual effect if loading takes longer
        }
        width += 5; // Increment width
        loadingProgress.style.width = width + '%';
        loadingProgress.textContent = width + '%';
    }, 100); // Adjust timing for smoother or faster animation
}

function hideLoadingBar() {
    if (!loadingOverlay || !loadingProgress) {
        console.error('Loading bar elements not found!');
        return;
    }
    clearInterval(_loadingInterval);
    _loadingInterval = null;
    loadingProgress.style.width = '100%'; // Complete the bar
    loadingProgress.textContent = '100%';

    // Give a brief moment to see the bar complete before hiding
    setTimeout(() => {
        loadingOverlay.style.display = 'none';
        loadingProgress.style.width = '0%'; // Reset for next time
        loadingProgress.textContent = '0%';
    }, 150); // Short delay
}


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
            showLoadingBar();
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
                })
                .finally(() => {
                    hideLoadingBar();
                });
        });
    }

    if (logoutButton) {
        logoutButton.addEventListener('click', async () => {
            showLoadingBar();
            try {
                // Clear remembered user credentials on logout
                localStorage.removeItem('rememberedUser');
                localStorage.removeItem('rememberedPassword');

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
            } finally {
                hideLoadingBar();
            }
        });

        // Event Listener for Save Button
        // Assuming saveOfficialAnswersBtn, officialAnswersRaceSelect, and officialAnswersQuestionsContainer are defined elsewhere or this code is conditional
        if (
            typeof saveOfficialAnswersBtn !== 'undefined' && saveOfficialAnswersBtn &&
            typeof officialAnswersRaceSelect !== 'undefined' && officialAnswersRaceSelect &&
            typeof officialAnswersQuestionsContainer !== 'undefined' && officialAnswersQuestionsContainer
        ) {
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

                saveOfficialAnswersBtn.disabled = true;
                saveOfficialAnswersBtn.textContent = 'Saving...';
                let messageElement = officialAnswersQuestionsContainer.querySelector('.save-message');
                if (messageElement) messageElement.remove();

                messageElement = document.createElement('p');
                messageElement.classList.add('mt-4', 'text-center', 'save-message');
                officialAnswersQuestionsContainer.appendChild(messageElement);

                showLoadingBar();
                try {
                    const response = await fetch(`/api/races/${selectedRaceId}/official_answers`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(officialAnswersPayload)
                    });

                    const responseData = await response.json();

                    if (response.ok) {
                        messageElement.textContent = `Official answers saved successfully for race ${selectedRaceId}!`;
                        messageElement.classList.remove('text-red-500');
                        messageElement.classList.add('text-green-600', 'font-semibold');
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
                    hideLoadingBar();
                    saveOfficialAnswersBtn.disabled = false;
                    saveOfficialAnswersBtn.textContent = 'Guardar Respuestas Oficiales';
                    setTimeout(() => {
                        if (messageElement) messageElement.remove();
                    }, 7000);
                }
            });
        }
    }

    async function fetchAndDisplayUserDetails() {
        if (!userRoleDisplay) {
            console.log("User role display element not found.");
            return;
        }
        if(generalAdminDataButton) generalAdminDataButton.style.display = 'none';
        if(leagueAdminDataButton) leagueAdminDataButton.style.display = 'none';
        if(userDataButton) userDataButton.style.display = 'none';

        showLoadingBar();
        try {
            const response = await fetch('/api/user/me');
            if (response.ok) {
                const data = await response.json();
                userRoleDisplay.textContent = `Welcome, ${data.username}! You are logged in as a ${data.role}.`;

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
        } finally {
            hideLoadingBar();
        }
    }

    async function fetchDataForButton(endpoint, buttonElement) {
        if (!buttonElement) return;
        messageArea.textContent = 'Fetching data...';
        showLoadingBar();
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
        } finally {
            hideLoadingBar();
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

    // --- TriCal Events List Logic ---
    async function fetchAndDisplayTriCalEvents() {
        const loadingDiv = document.getElementById('trical-events-loading');
        const listDiv = document.getElementById('trical-events-list');
        const errorDiv = document.getElementById('trical-events-error');

        if (!loadingDiv || !listDiv || !errorDiv) {
            console.error('TriCal event display elements not found!');
            return;
        }

        loadingDiv.style.display = 'block';
        listDiv.style.display = 'none';
        errorDiv.style.display = 'none';
        listDiv.innerHTML = ''; // Clear previous content

        try {
            const response = await fetch('/api/events');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const events = await response.json();

            if (events && events.length > 0) {
                const table = document.createElement('table');
                table.className = 'w-full table-hover';
                const thead = document.createElement('thead');
                thead.innerHTML = `
                    <tr class="gradient-orange text-white">
                        <th class="px-6 py-4 text-left font-semibold">Nombre del Evento</th>
                        <th class="px-6 py-4 text-left font-semibold">Fecha</th>
                        <th class="px-6 py-4 text-left font-semibold">Ubicación</th>
                    </tr>
                `;
                table.appendChild(thead);

                const tbody = document.createElement('tbody');
                tbody.className = 'divide-y divide-gray-200';

                events.forEach(event => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="px-6 py-4 text-gray-900">${event.name}</td>
                        <td class="px-6 py-4 text-gray-700">${event.event_date || 'N/A'}</td>
                        <td class="px-6 py-4 text-gray-700">${event.city || 'N/A'}, ${event.province || 'N/A'}</td>
                    `;
                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);
                listDiv.appendChild(table);
                listDiv.style.display = 'block';
            } else {
                listDiv.innerHTML = '<p class="text-center text-gray-500 py-10">No hay eventos disponibles por el momento.</p>';
                listDiv.style.display = 'block';
            }
        } catch (error) {
            console.error('Error fetching TriCal events:', error);
            errorDiv.style.display = 'block';
        } finally {
            loadingDiv.style.display = 'none';
        }
    }

    // Call the function to fetch events when the page loads
    // Ensure this is called after the DOM is fully loaded.
    // The main DOMContentLoaded listener is already present, so this will be executed within it.
    fetchAndDisplayTriCalEvents();
    // --- End TriCal Events List Logic ---
});
