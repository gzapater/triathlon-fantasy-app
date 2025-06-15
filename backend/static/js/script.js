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

    // --- Official Answers Section Logic ---
    const officialAnswersRaceSelect = document.getElementById('official-answers-race-select');
    const officialAnswersQuestionsContainer = document.getElementById('official-answers-questions-container');
    const saveOfficialAnswersBtn = document.getElementById('save-official-answers-btn');

    if (officialAnswersRaceSelect && officialAnswersQuestionsContainer && saveOfficialAnswersBtn) {
        // Populate Race Dropdown
        if (typeof RACES_FOR_OFFICIAL_ANSWERS !== 'undefined' && RACES_FOR_OFFICIAL_ANSWERS.length > 0) {
            RACES_FOR_OFFICIAL_ANSWERS.forEach(race => {
                const option = document.createElement('option');
                option.value = race.id;
                option.textContent = race.title; // Assuming race objects have 'id' and 'title'
                officialAnswersRaceSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.textContent = 'No races available for official answers';
            option.disabled = true;
            officialAnswersRaceSelect.appendChild(option);
        }

        // Event Listener for Race Selection
        officialAnswersRaceSelect.addEventListener('change', async function() {
            const selectedRaceId = this.value;
            officialAnswersQuestionsContainer.innerHTML = ''; // Clear previous questions
            saveOfficialAnswersBtn.style.display = 'none'; // Hide save button

            if (!selectedRaceId) {
                return; // No race selected or "-- Select a Race --" chosen
            }

            try {
                // Show some loading state in officialAnswersQuestionsContainer
                officialAnswersQuestionsContainer.innerHTML = '<p class="text-gray-500">Loading questions...</p>';

                const [questionsResponse, existingAnswersResponse] = await Promise.all([
                    fetch(`/api/races/${selectedRaceId}/questions`),
                    fetch(`/api/races/${selectedRaceId}/official_answers`)
                ]);

                if (!questionsResponse.ok) {
                    const errorData = await questionsResponse.json();
                    throw new Error(`Failed to fetch questions: ${errorData.message || questionsResponse.statusText}`);
                }
                if (!existingAnswersResponse.ok) {
                    // It's okay if official answers don't exist yet (404), but other errors should be thrown
                    if (existingAnswersResponse.status !== 404) {
                        const errorData = await existingAnswersResponse.json();
                        throw new Error(`Failed to fetch official answers: ${errorData.message || existingAnswersResponse.statusText}`);
                    }
                }

                const questions = await questionsResponse.json();
                let existingAnswers = {};
                if (existingAnswersResponse.status !== 404) { // Only parse if not 404
                    existingAnswers = await existingAnswersResponse.json();
                }


                officialAnswersQuestionsContainer.innerHTML = ''; // Clear loading message

                if (questions.length === 0) {
                    officialAnswersQuestionsContainer.innerHTML = '<p class="text-gray-500">This race has no questions configured yet.</p>';
                    return;
                }

                questions.forEach(question => {
                    const questionDiv = document.createElement('div');
                    questionDiv.classList.add('mb-6', 'p-4', 'border', 'border-gray-200', 'rounded-lg');
                    questionDiv.dataset.questionId = question.id;
                    questionDiv.dataset.questionType = question.question_type;
                    if (question.question_type === 'MULTIPLE_CHOICE') {
                        questionDiv.dataset.isMcMultipleCorrect = question.is_mc_multiple_correct;
                    }


                    const questionText = document.createElement('p');
                    questionText.classList.add('font-semibold', 'text-gray-700', 'mb-2');
                    questionText.textContent = `${question.id}: ${question.text}`;
                    questionDiv.appendChild(questionText);

                    const existingAnswerForQuestion = existingAnswers[question.id.toString()];

                    switch (question.question_type) {
                        case 'FREE_TEXT':
                            const textarea = document.createElement('textarea');
                            textarea.classList.add('w-full', 'px-3', 'py-2', 'border', 'border-gray-300', 'rounded-md', 'focus:ring-orange-500', 'focus:border-orange-500');
                            textarea.name = `question_${question.id}`;
                            // Changed rows from 3 to 4
                            textarea.rows = 4;
                            // Updated placeholder to Spanish and to match wizard
                            textarea.placeholder = 'Escribe tu respuesta...';
                            // Aligned classes to wizard's textarea
                            textarea.className = 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent';
                            if (existingAnswerForQuestion && existingAnswerForQuestion.answer_text) {
                                textarea.value = existingAnswerForQuestion.answer_text;
                            }
                            questionDiv.appendChild(textarea);
                            break;
                        case 'MULTIPLE_CHOICE':
                            const mcOptionsContainer = document.createElement('div');
                            // Removed 'mt-2' as new label style includes padding. Kept 'space-y-2' for spacing between options.
                            mcOptionsContainer.classList.add('space-y-2');
                            question.options.forEach(option => {
                                const label = document.createElement('label'); // Wrap input and span in a label
                                label.classList.add('flex', 'items-center', 'space-x-3', 'cursor-pointer', 'hover:bg-gray-100', 'p-2', 'rounded-md', 'border', 'border-gray-200', 'hover:border-orange-300');

                                const input = document.createElement('input');
                                // No explicit ID needed as label wraps input
                                input.value = option.id;
                                input.name = `question_${question.id}`; // Group radios/checkboxes
                                // Applied new classes, kept h-4, w-4, border-gray-300
                                input.classList.add('text-orange-600', 'focus:ring-orange-400', 'focus:ring-offset-0', 'h-4', 'w-4', 'border-gray-300');

                                if (question.is_mc_multiple_correct) {
                                    input.type = 'checkbox';
                                    input.classList.add('rounded'); // Add rounded for checkboxes
                                    if (existingAnswerForQuestion && existingAnswerForQuestion.selected_options) {
                                        if (existingAnswerForQuestion.selected_options.some(oa_opt => oa_opt.option_id === option.id)) {
                                            input.checked = true;
                                        }
                                    }
                                } else {
                                    input.type = 'radio';
                                    if (existingAnswerForQuestion && existingAnswerForQuestion.selected_option_id === option.id) {
                                        input.checked = true;
                                    }
                                }

                                const span = document.createElement('span');
                                span.classList.add('text-gray-700');
                                span.textContent = option.option_text;

                                label.appendChild(input);
                                label.appendChild(span);
                                mcOptionsContainer.appendChild(label);
                            });
                            questionDiv.appendChild(mcOptionsContainer);
                            break;
                        case 'ORDERING':
                            // Removed old orderingInstructions and orderingOptionsDisplay
                            // New: Display options to be ordered more clearly
                            const orderingListContainer = document.createElement('div');
                            orderingListContainer.classList.add('space-y-1', 'mb-3', 'p-2', 'border', 'rounded-md');
                            if (question.options && question.options.length > 0) {
                                question.options.forEach(opt => {
                                    const itemDiv = document.createElement('div');
                                    itemDiv.classList.add('bg-gray-100', 'p-2', 'rounded', 'text-sm', 'mb-1');
                                    itemDiv.textContent = opt.option_text;
                                    orderingListContainer.appendChild(itemDiv);
                                });
                            } else {
                                const noOptionsMsg = document.createElement('p');
                                noOptionsMsg.classList.add('text-sm', 'text-gray-500');
                                noOptionsMsg.textContent = 'No options available for ordering.';
                                orderingListContainer.appendChild(noOptionsMsg);
                            }
                            questionDiv.appendChild(orderingListContainer);

                            const orderingTextarea = document.createElement('textarea');
                            // Aligned classes to wizard's textarea
                            orderingTextarea.className = 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent';
                            orderingTextarea.name = `question_${question.id}`;
                            // Changed rows from 2 to 3
                            orderingTextarea.rows = 3;
                            // Updated placeholder to Spanish and to match wizard
                            orderingTextarea.placeholder = 'Ej: Item C, Item A, Item B';
                            // Pre-fill logic remains the same, using answer_text as per existing GET response structure
                            if (existingAnswerForQuestion && existingAnswerForQuestion.answer_text) {
                                orderingTextarea.value = existingAnswerForQuestion.answer_text;
                            }
                            questionDiv.appendChild(orderingTextarea);
                            break;
                        default:
                            const unsupportedText = document.createElement('p');
                            unsupportedText.classList.add('text-red-500');
                            unsupportedText.textContent = `Unsupported question type: ${question.question_type}`;
                            questionDiv.appendChild(unsupportedText);
                    }
                    officialAnswersQuestionsContainer.appendChild(questionDiv);
                });

                saveOfficialAnswersBtn.style.display = 'inline-block'; // Show save button
                saveOfficialAnswersBtn.disabled = false;

            } catch (error) {
                console.error('Error loading questions or official answers:', error);
                officialAnswersQuestionsContainer.innerHTML = `<p class="text-red-500">Error loading data: ${error.message}. Please try again.</p>`;
                saveOfficialAnswersBtn.style.display = 'none';
            }
        });
    }
    // --- End of Official Answers Section Logic ---
});
