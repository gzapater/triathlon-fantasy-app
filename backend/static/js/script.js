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


    // --- Race Participation Wizard Modal JavaScript ---
    const participateWizardModal = document.getElementById('participateWizardModal');
    const participateWizardModalDialog = document.getElementById('participateWizardModalDialog');
    const participateWizardModalTitle = document.getElementById('participateWizardModalTitle');
    const participateWizardModalContent = document.getElementById('participateWizardModalContent');
    const participateWizardNextButton = document.getElementById('participateWizardNextButton');
    const participateWizardModalError = document.getElementById('participateWizardModalError');

    let currentWizardRaceId = null;
    let currentWizardQuestion = null; // To store current question object if needed

    function openParticipateWizardModal(raceId, raceName) {
        if (!participateWizardModal || !participateWizardModalDialog) {
            console.error('Participate wizard modal elements not found!');
            return;
        }
        currentWizardRaceId = raceId;
        participateWizardModalTitle.textContent = `Participar en: ${raceName}`;
        participateWizardModalContent.innerHTML = '<p class="text-sm text-gray-500">Cargando primera pregunta...</p>';
        participateWizardModalError.classList.add('hidden');
        participateWizardModalError.querySelector('p').textContent = '';
        participateWizardNextButton.textContent = 'Siguiente';
        participateWizardNextButton.disabled = false;

        // Animation for modal
        participateWizardModal.classList.remove('hidden');
        setTimeout(() => {
            participateWizardModalDialog.classList.remove('opacity-0', 'translate-y-4', 'sm:translate-y-0', 'sm:scale-95');
            participateWizardModalDialog.classList.add('opacity-100', 'translate-y-0', 'sm:scale-100');
        }, 10); // Small delay to allow CSS transition

        // Fetch the first question
        // Replace with actual API endpoint when available
        // For now, simulate fetching a question
        setTimeout(() => {
            // Simulate API call success
            currentWizardQuestion = { id: 1, text: '¿Cuál es tu predicción para el ganador?', type: 'TEXT' };
            renderWizardQuestion(currentWizardQuestion);
        }, 1000);

        // TODO: Implement API call: fetch(`/api/race/${raceId}/wizard/start`)
        // .then(response => response.json())
        // .then(data => {
        //     if (data.error) throw new Error(data.error);
        //     currentWizardQuestion = data.question;
        //     renderWizardQuestion(currentWizardQuestion);
        // })
        // .catch(error => {
        //     console.error('Error starting participation wizard:', error);
        //     participateWizardModalContent.innerHTML = `<p class="text-sm text-red-500">Error al cargar la primera pregunta: ${error.message}</p>`;
        //     participateWizardNextButton.disabled = true;
        // });
    }

    function closeParticipateWizardModal() {
        if (!participateWizardModal || !participateWizardModalDialog) return;

        participateWizardModalDialog.classList.remove('opacity-100', 'translate-y-0', 'sm:scale-100');
        participateWizardModalDialog.classList.add('opacity-0', 'translate-y-4', 'sm:translate-y-0', 'sm:scale-95');
        setTimeout(() => {
            participateWizardModal.classList.add('hidden');
            // Reset content for next time
            participateWizardModalContent.innerHTML = '<p class="text-sm text-gray-500">Cargando pregunta...</p>';
            currentWizardRaceId = null;
            currentWizardQuestion = null;
        }, 300); // Match transition duration
    }

    function renderWizardQuestion(question) {
        participateWizardModalContent.innerHTML = ''; // Clear loading/previous content

        const questionText = document.createElement('p');
        questionText.classList.add('text-md', 'font-semibold', 'text-gray-700', 'mb-3');
        questionText.textContent = question.text;
        participateWizardModalContent.appendChild(questionText);

        if (question.type === 'TEXT') {
            const input = document.createElement('textarea');
            input.id = `wizard_q_${question.id}`;
            input.classList.add('w-full', 'p-2', 'border', 'border-gray-300', 'rounded-md', 'focus:ring-blue-500', 'focus:border-blue-500', 'mt-1');
            input.rows = 3;
            participateWizardModalContent.appendChild(input);
        } else if (question.type === 'MULTIPLE_CHOICE') {
            // Example:
            // question.options = [{id: 'opt1', text: 'Option 1'}, {id: 'opt2', text: 'Option 2'}];
            // question.is_multiple_select = false; // or true
            // Create radio buttons or checkboxes
        }
        // Add other question types as needed (SLIDER, ORDERING etc.)
        participateWizardNextButton.disabled = false;
    }

    if (participateWizardNextButton) {
        participateWizardNextButton.addEventListener('click', () => {
            if (!currentWizardRaceId || !currentWizardQuestion) return;

            participateWizardNextButton.disabled = true;
            participateWizardNextButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Procesando...';
            participateWizardModalError.classList.add('hidden');

            let answerData = {};
            // Collect answer based on question.type
            if (currentWizardQuestion.type === 'TEXT') {
                const textarea = document.getElementById(`wizard_q_${currentWizardQuestion.id}`);
                answerData = { question_id: currentWizardQuestion.id, answer_text: textarea.value.trim() };
            }
            // Add logic for other answer types

            // Simulate API call to submit answer and get next question
            console.log("Submitting answer:", answerData, "for race:", currentWizardRaceId);
            setTimeout(() => {
                // Simulate response
                const isLastQuestion = Math.random() > 0.7; // Simulate sometimes being the last question

                if (isLastQuestion) {
                    participateWizardModalContent.innerHTML = '<p class="text-green-600 font-semibold">¡Has completado la participación!</p>';
                    participateWizardNextButton.textContent = 'Finalizar';
                    participateWizardNextButton.onclick = () => { // Change action to close or finalize
                        // TODO: Call actual /api/race/<race_id>/wizard/finish endpoint
                        console.log("Finalizing participation for race:", currentWizardRaceId);
                        closeParticipateWizardModal();
                        // Potentially reload page or update UI
                        Swal.fire('¡Éxito!', 'Tu participación ha sido registrada.', 'success');
                    };
                    participateWizardNextButton.disabled = false; // Re-enable for "Finalizar"
                } else {
                    // Simulate getting a new question
                    const nextQuestionId = (currentWizardQuestion.id || 0) + 1;
                    currentWizardQuestion = { id: nextQuestionId, text: `Esta es la pregunta número ${nextQuestionId}. ¿Qué opinas?`, type: 'TEXT' };
                    renderWizardQuestion(currentWizardQuestion);
                    participateWizardNextButton.innerHTML = 'Siguiente';
                    participateWizardNextButton.disabled = false;
                }

            }, 1500);

            // TODO: Implement actual API call:
            // fetch(`/api/race/${currentWizardRaceId}/wizard/next`, {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify({ answer: answerData })
            // })
            // .then(response => response.json())
            // .then(data => {
            //     if (data.error) {
            //         throw new Error(data.error);
            //     }
            //     if (data.is_final_step) {
            //         participateWizardModalContent.innerHTML = `<p class="text-green-600 font-semibold">${data.completion_message || '¡Has completado la participación!'}</p>`;
            //         participateWizardNextButton.textContent = 'Finalizar';
            //         participateWizardNextButton.onclick = () => {
            //             // Call /api/race/<race_id>/wizard/finish if needed or just close
            //             closeParticipateWizardModal();
            //             Swal.fire('¡Éxito!', data.completion_message || 'Tu participación ha sido registrada.', 'success');
            //             // Optionally reload or update UI
            //         };
            //     } else {
            //         currentWizardQuestion = data.next_question;
            //         renderWizardQuestion(currentWizardQuestion);
            //         participateWizardNextButton.innerHTML = 'Siguiente';
            //     }
            //     participateWizardNextButton.disabled = false;
            // })
            // .catch(error => {
            //     console.error('Error processing wizard step:', error);
            //     participateWizardModalError.querySelector('p').textContent = `Error: ${error.message}`;
            //     participateWizardModalError.classList.remove('hidden');
            //     participateWizardNextButton.innerHTML = 'Siguiente';
            //     participateWizardNextButton.disabled = false;
            // });
        });
    }

    // Make openParticipateWizardModal and closeParticipateWizardModal globally accessible
    // if they are called from inline HTML onclick attributes.
    window.openParticipateWizardModal = openParticipateWizardModal;
    window.closeParticipateWizardModal = closeParticipateWizardModal;

    // --- End Race Participation Wizard Modal JavaScript ---
});
