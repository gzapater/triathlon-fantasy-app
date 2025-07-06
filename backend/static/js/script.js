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
});


// --- Global Notification Modal Logic ---
// Ensure the HTML for notificationModal, notificationModalTitle, notificationModalMessage,
// closeNotificationModalBtn, acceptNotificationModalBtn is present in the base template or included.
function showNotificationModal(title, message, type = 'info') {
    const notificationModal = document.getElementById('notificationModal');
    const notificationModalTitle = document.getElementById('notificationModalTitle');
    const notificationModalMessage = document.getElementById('notificationModalMessage');
    if (!notificationModal || !notificationModalTitle || !notificationModalMessage) {
        console.error("Notification modal elements not found. Cannot display message:", title, message);
        alert(`${title}: ${message}`); // Fallback to alert
        return;
    }

    notificationModalTitle.textContent = title;
    notificationModalMessage.textContent = message;

    notificationModalTitle.classList.remove('text-green-600', 'text-red-600', 'text-orange-600', 'text-blue-600', 'text-gray-800');
    switch (type) {
        case 'success': notificationModalTitle.classList.add('text-green-600'); break;
        case 'error': notificationModalTitle.classList.add('text-red-600'); break;
        case 'validation': notificationModalTitle.classList.add('text-orange-600'); break;
        case 'info': default: notificationModalTitle.classList.add('text-blue-600'); break;
    }
    notificationModal.style.display = 'flex';
}

function closeNotificationModal() {
    const notificationModal = document.getElementById('notificationModal');
    if (notificationModal) notificationModal.style.display = 'none';
}

// Attach listeners for notification modal if its buttons are present globally (e.g. in a base template)
document.addEventListener('DOMContentLoaded', () => {
    const closeNotificationModalBtn = document.getElementById('closeNotificationModalBtn');
    const acceptNotificationModalBtn = document.getElementById('acceptNotificationModalBtn');
    if (closeNotificationModalBtn) closeNotificationModalBtn.addEventListener('click', closeNotificationModal);
    if (acceptNotificationModalBtn) acceptNotificationModalBtn.addEventListener('click', closeNotificationModal);
});


// --- Question Wizard Global Variables ---
let currentRaceIdForWizard = null;
let currentQuinielaCloseDateForWizard = null;
let currentRaceTitleForWizard = null; // Added for consistency if wizard title needs it
let wizardAllRaceQuestions = []; // Renamed to avoid conflict if allRaceQuestions is used elsewhere
let wizardCurrentQuestionIndex = 0;
let wizardUserAnswers = {}; // Stores answers as { question_id: { ...answer_data } }


// --- Function to be called from HTML to open the wizard ---
function openQuestionWizard(raceId, quinielaCloseDateStr, raceTitleStr) {
    console.log(`openQuestionWizard called with raceId: ${raceId}, quinielaCloseDate: ${quinielaCloseDateStr}, raceTitle: ${raceTitleStr}`);
    currentRaceIdForWizard = raceId;
    currentQuinielaCloseDateForWizard = quinielaCloseDateStr;
    currentRaceTitleForWizard = raceTitleStr; // Store the race title

    if (typeof initAndShowMainWizard === 'function') {
        initAndShowMainWizard();
    } else {
        console.error('initAndShowMainWizard function is not defined. Make sure it is included in script.js and loaded.');
        showNotificationModal('Error', 'La funcionalidad de la quiniela no está completamente cargada.', 'error');
    }
}

// --- Core Question Wizard Logic (Moved from race_detail.html) ---
function initAndShowMainWizard() {
    // Use currentQuinielaCloseDateForWizard and currentRaceIdForWizard
    if (currentQuinielaCloseDateForWizard && new Date(currentQuinielaCloseDateForWizard) < new Date()) {
        showNotificationModal("Quiniela Cerrada", "La quiniela ya está cerrada y no se puede participar.", "info");
        return;
    }

    const questionWizardModal = document.getElementById('questionWizardModal');
    if (!questionWizardModal) {
        console.error("Question Wizard Modal HTML element not found.");
        showNotificationModal('Error', 'No se pudo cargar el modal de la quiniela.', 'error');
        return;
    }

    // Show loading indicator in modal or on button
    const wizardTriggerButton = document.getElementById('participateInPoolBtn') || document.querySelector(`button[onclick*="openQuestionWizard('${currentRaceIdForWizard}'"]`);
    let originalButtonText = '';
    if (wizardTriggerButton) {
        originalButtonText = wizardTriggerButton.innerHTML;
        wizardTriggerButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Cargando...';
        wizardTriggerButton.disabled = true;
    }

    fetch(`/api/races/${currentRaceIdForWizard}/questions`)
        .then(response => {
            if (!response.ok) throw new Error(`Error ${response.status}: ${response.statusText}`);
            return response.json();
        })
        .then(questions => {
            wizardAllRaceQuestions = questions;
            if (!wizardAllRaceQuestions || wizardAllRaceQuestions.length === 0) {
                showNotificationModal("Sin Preguntas", "No hay preguntas disponibles para esta carrera en este momento.", "info");
                if (wizardTriggerButton) {
                    wizardTriggerButton.innerHTML = originalButtonText;
                    wizardTriggerButton.disabled = false;
                }
                return;
            }
            wizardCurrentQuestionIndex = 0;
            wizardUserAnswers = {};
            displayWizardQuestion(wizardCurrentQuestionIndex);
            questionWizardModal.style.display = 'flex';
        })
        .catch(error => {
            console.error('Error fetching questions for wizard:', error);
            showNotificationModal("Error", `Error al cargar las preguntas de la quiniela: ${error.message}. Inténtalo de nuevo.`, "error");
        })
        .finally(() => {
            if (wizardTriggerButton) {
                wizardTriggerButton.innerHTML = originalButtonText; // Restore button text
                wizardTriggerButton.disabled = false;
            }
        });
}

function closeWizard() {
    const questionWizardModal = document.getElementById('questionWizardModal');
    if (questionWizardModal) questionWizardModal.style.display = 'none';
}

function displayWizardQuestion(index) {
    const questionWizardModal = document.getElementById('questionWizardModal');
    const wizardQuestionProgress = document.getElementById('wizardQuestionProgress');
    const wizardQuestionText = document.getElementById('wizardQuestionText');
    const wizardAnswerOptions = document.getElementById('wizardAnswerOptions');
    const wizardPrevBtn = document.getElementById('wizardPrevBtn');
    const wizardNextBtn = document.getElementById('wizardNextBtn');
    const wizardFinishBtn = document.getElementById('wizardFinishBtn');

    if (!questionWizardModal || !wizardQuestionProgress || !wizardQuestionText || !wizardAnswerOptions || !wizardPrevBtn || !wizardNextBtn || !wizardFinishBtn) {
        console.error("One or more wizard DOM elements are missing.");
        showNotificationModal("Error", "No se pudieron cargar los elementos del wizard.", "error");
        return;
    }

    wizardAnswerOptions.innerHTML = '<p class="text-center text-gray-500 py-4"><i class="fas fa-spinner fa-spin mr-2"></i>Cargando pregunta...</p>';

    if (!wizardAllRaceQuestions || wizardAllRaceQuestions.length === 0) {
        wizardQuestionText.textContent = 'Error';
        wizardAnswerOptions.innerHTML = '<p class="text-red-500 text-center py-4">Error: No hay preguntas disponibles.</p>';
        wizardNextBtn.style.display = 'none';
        wizardFinishBtn.style.display = 'none';
        return;
    }
    if (index < 0 || index >= wizardAllRaceQuestions.length) {
        wizardQuestionText.textContent = 'Error';
        wizardAnswerOptions.innerHTML = '<p class="text-red-500 text-center py-4">Error: Índice de pregunta no válido.</p>';
        wizardNextBtn.style.display = 'none';
        wizardFinishBtn.style.display = 'none';
        return;
    }

    const question = wizardAllRaceQuestions[index];
    if (!question) {
        wizardQuestionText.textContent = 'Error';
        wizardAnswerOptions.innerHTML = '<p class="text-red-500 text-center py-4">Error: No se pudo cargar esta pregunta.</p>';
        wizardNextBtn.style.display = 'none';
        wizardFinishBtn.style.display = 'none';
        return;
    }
    const existingAnswer = wizardUserAnswers[question.id];

    wizardQuestionProgress.textContent = `Pregunta ${index + 1} de ${wizardAllRaceQuestions.length}`;
    wizardQuestionText.textContent = `${index + 1}-${question.text}`;
    wizardAnswerOptions.innerHTML = ''; // Clear previous

    try {
        switch (question.question_type) {
            case 'FREE_TEXT':
                const textarea = document.createElement('textarea');
                textarea.id = `wizardFreeTextAnswer_${question.id}`;
                textarea.className = 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent';
                textarea.rows = 4;
                textarea.placeholder = 'Escribe tu respuesta...';
                textarea.value = existingAnswer?.answer_text || '';
                wizardAnswerOptions.appendChild(textarea);
                break;
            case 'MULTIPLE_CHOICE':
                if (!question.options || !Array.isArray(question.options)) {
                    throw new Error('Datos de opciones de Opción Múltiple no válidos.');
                }
                question.options.forEach(opt => {
                    const label = document.createElement('label');
                    label.className = 'flex items-center space-x-3 cursor-pointer hover:bg-gray-50 p-2 rounded-md border border-gray-200 hover:border-orange-300';
                    const input = document.createElement('input');
                    input.type = question.is_mc_multiple_correct ? 'checkbox' : 'radio';
                    input.name = `wizard_q_${question.id}`;
                    input.value = opt.id;
                    input.className = 'text-orange-500 focus:ring-orange-400 focus:ring-offset-0';
                    if (question.is_mc_multiple_correct) {
                        input.classList.add('rounded');
                        if (existingAnswer?.selected_option_ids?.includes(opt.id)) input.checked = true;
                    } else {
                        if (existingAnswer?.selected_option_id == opt.id) input.checked = true;
                    }
                    const span = document.createElement('span');
                    span.className = 'text-gray-700';
                    span.textContent = opt.option_text;
                    label.appendChild(input);
                    label.appendChild(span);
                    wizardAnswerOptions.appendChild(label);
                });
                break;
            case 'ORDERING':
                const orderingListContainer = document.createElement('ul');
                orderingListContainer.id = `wizardOrderingList_${question.id}`;
                orderingListContainer.className = 'list-none p-0 m-0 space-y-2';
                if (question.options && question.options.length > 0) {
                    let orderedOptions = [...question.options];
                    if (existingAnswer && existingAnswer.ordered_options_text) {
                        const savedOrderIds = existingAnswer.ordered_options_text.split(',').map(id => parseInt(id.trim(), 10));
                        const optionsMap = new Map(question.options.map(opt => [opt.id, opt]));
                        const newOrderedOptions = [];
                        const addedOptionIds = new Set();
                        savedOrderIds.forEach(id => {
                            if (optionsMap.has(id)) {
                                newOrderedOptions.push(optionsMap.get(id));
                                addedOptionIds.add(id);
                            }
                        });
                        question.options.forEach(opt => {
                            if (!addedOptionIds.has(opt.id)) newOrderedOptions.push(opt);
                        });
                        orderedOptions = newOrderedOptions;
                    }
                    orderedOptions.forEach(opt => {
                        const listItem = document.createElement('li');
                        listItem.dataset.optionId = opt.id;
                        listItem.className = 'p-3 border rounded-md bg-gray-50 flex justify-between items-center shadow-sm';
                        const textSpan = document.createElement('span');
                        textSpan.className = 'text-gray-700';
                        textSpan.textContent = opt.option_text;
                        listItem.appendChild(textSpan);
                        const buttonContainer = document.createElement('div');
                        buttonContainer.className = 'space-x-1';
                        const moveUpBtn = document.createElement('button');
                        moveUpBtn.innerHTML = '↑';
                        moveUpBtn.type = 'button';
                                moveUpBtn.className = 'wizard-move-up-btn px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-300';
                                moveUpBtn.addEventListener('click', () => {
                                    const currentLi = moveUpBtn.closest('li');
                                    if (currentLi && currentLi.previousElementSibling) {
                                        currentLi.parentNode.insertBefore(currentLi, currentLi.previousElementSibling);
                                        updateWizardOrderingButtonStates(orderingListContainer);
                                    }
                                });
                        buttonContainer.appendChild(moveUpBtn);

                                const moveDownBtn = document.createElement('button');
                                moveDownBtn.innerHTML = '↓';
                                moveDownBtn.type = 'button';
                                moveDownBtn.className = 'wizard-move-down-btn px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-300';
                                moveDownBtn.addEventListener('click', () => {
                                    const currentLi = moveDownBtn.closest('li');
                                    if (currentLi && currentLi.nextElementSibling) {
                                        currentLi.parentNode.insertBefore(currentLi, currentLi.nextElementSibling.nextSibling);
                                        updateWizardOrderingButtonStates(orderingListContainer);
                                    }
                                });
                                buttonContainer.appendChild(moveDownBtn);
                                listItem.appendChild(buttonContainer);
                                orderingListContainer.appendChild(listItem);
                            });
                        } else {
                            orderingListContainer.innerHTML = '<p class="text-sm text-gray-500">No hay opciones para ordenar.</p>';
                        }
                        wizardAnswerOptions.appendChild(orderingListContainer);
                        if (orderingListContainer.firstChild) {
                             updateWizardOrderingButtonStates(orderingListContainer);
                        }
                        break;
                    case 'SLIDER':
                        if (!wizardAnswerOptions) break;
                wizardAnswerOptions.innerHTML = ''; // Clear previous content

                const minValue = parseFloat(question.slider_min_value);
                const maxValue = parseFloat(question.slider_max_value);
                const unit = question.slider_unit || "";
                let parsedStep = parseFloat(question.slider_step);
                let stepValue = (question.slider_step == null || isNaN(parsedStep) || parsedStep <= 0) ? 1 : parsedStep;

                let errorMsg = "";
                if (isNaN(minValue)) errorMsg = "Valor mínimo no numérico.";
                else if (isNaN(maxValue)) errorMsg = "Valor máximo no numérico.";
                else if (maxValue <= minValue) errorMsg = "Valor máximo debe ser mayor que el mínimo.";
                else if (isNaN(stepValue)) errorMsg = "Paso (step) inválido.";

                if (errorMsg) {
                    wizardAnswerOptions.innerHTML = `<p class="text-red-500 text-center py-4">Error en config. slider: ${errorMsg}</p>`;
                    if(wizardNextBtn) wizardNextBtn.style.display = 'none';
                    if(wizardFinishBtn) wizardFinishBtn.style.display = 'none';
                    break;
                }

                const sliderContainer = document.createElement('div');
                sliderContainer.className = 'custom-slider-container w-full pt-8 pb-4 relative select-none';

                const trackBackground = document.createElement('div');
                trackBackground.className = 'slider-track-background h-2 bg-gray-300 rounded-full absolute top-1/2 left-0 right-0 -translate-y-1/2';
                sliderContainer.appendChild(trackBackground);

                const thumb = document.createElement('div');
                thumb.className = 'slider-thumb absolute top-1/2 -translate-y-1/2 flex items-stretch h-6 rounded shadow-md border border-gray-400';
                thumb.style.cursor = 'grab';
                thumb.id = `sliderThumb_${question.id}`;

                const yellowZoneLeft = document.createElement('div');
                yellowZoneLeft.className = 'slider-yellow-zone-left bg-yellow-300 border-r border-yellow-400';
                thumb.appendChild(yellowZoneLeft);

                const greenZone = document.createElement('div');
                greenZone.className = 'slider-green-zone bg-green-500 border-l border-r border-green-600';
                thumb.appendChild(greenZone);

                const yellowZoneRight = document.createElement('div');
                yellowZoneRight.className = 'slider-yellow-zone-right bg-yellow-300 border-l border-yellow-400';
                thumb.appendChild(yellowZoneRight);
                sliderContainer.appendChild(thumb);

                const valueDisplay = document.createElement('div');
                valueDisplay.id = `wizardSliderValueDisplay_${question.id}`;
                valueDisplay.className = 'slider-value-display text-center text-lg font-semibold text-gray-700 mt-3 mb-1';
                sliderContainer.appendChild(valueDisplay);

                const labelsContainer = document.createElement('div');
                labelsContainer.className = 'slider-labels flex justify-between text-xs text-gray-500';
                const minLabel = document.createElement('span');
                minLabel.id = `wizardSliderMinLabel_${question.id}`;
                const maxLabel = document.createElement('span');
                maxLabel.id = `wizardSliderMaxLabel_${question.id}`;
                labelsContainer.appendChild(minLabel);
                labelsContainer.appendChild(maxLabel);
                sliderContainer.appendChild(labelsContainer);

                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.id = `hiddenSliderValue_${question.id}`; // Used to store the actual value
                sliderContainer.appendChild(hiddenInput);

                wizardAnswerOptions.appendChild(sliderContainer);

                requestAnimationFrame(() => {
                    const trackWidthPx = trackBackground.offsetWidth;
                    const valueRange = maxValue - minValue;

                    if (valueRange <= 0 || trackWidthPx === 0) {
                        wizardAnswerOptions.innerHTML = '<p class="text-red-500 text-center">Error: Configuración de slider inválida o contenedor no visible.</p>';
                        if(wizardNextBtn) wizardNextBtn.style.display = 'none';
                        if(wizardFinishBtn) wizardFinishBtn.style.display = 'none';
                        return;
                    }
                    const pixelsPerUnit = trackWidthPx / valueRange;
                    const thresholdPartial = parseFloat(question.slider_threshold_partial) || 0;
                    const greenZoneUnitWidth = 1; // Assuming the "exact" point is 1 unit wide on the conceptual slider

                    const greenZonePxWidth = Math.max(2, greenZoneUnitWidth * pixelsPerUnit); // Min 2px width for visibility
                    const yellowZonePxWidth = Math.max(0, thresholdPartial * pixelsPerUnit);

                    greenZone.style.width = `${greenZonePxWidth}px`;
                    yellowZoneLeft.style.width = `${yellowZonePxWidth}px`;
                    yellowZoneRight.style.width = `${yellowZonePxWidth}px`;
                    thumb.style.width = `${greenZonePxWidth + (2 * yellowZonePxWidth)}px`;

                    minLabel.textContent = `${minValue} ${unit}`;
                    maxLabel.textContent = `${maxValue} ${unit}`;

                    let initialValue = parseFloat(existingAnswer?.slider_answer_value ?? minValue);
                    initialValue = Math.max(minValue, Math.min(maxValue, initialValue));
                    let numDecimalPlaces = stepValue.toString().includes('.') ? (stepValue.toString().split('.')[1].length || 0) : 0;
                    initialValue = parseFloat((Math.round((initialValue - minValue) / stepValue) * stepValue + minValue).toFixed(numDecimalPlaces));

                    hiddenInput.value = initialValue;
                    valueDisplay.textContent = `${initialValue} ${unit}`;

                    const valuePointOffsetWithinThumbPx = yellowZonePxWidth + (greenZonePxWidth / 2);
                    let initialValuePointOnTrackPx = ((initialValue - minValue) / valueRange) * trackWidthPx;
                    initialValuePointOnTrackPx = Math.max(0, Math.min(initialValuePointOnTrackPx, trackWidthPx));
                    thumb.style.left = `${initialValuePointOnTrackPx - valuePointOffsetWithinThumbPx}px`;

                    let isDragging = false;
                    let dragStartX;
                    let thumbInitialLeftPx;

                    thumb.onpointerdown = (e) => {
                        if (e.button !== 0) return;
                        isDragging = true;
                        dragStartX = e.clientX;
                        thumbInitialLeftPx = thumb.offsetLeft;
                        thumb.setPointerCapture(e.pointerId);
                        thumb.style.cursor = 'grabbing';
                        document.body.style.userSelect = 'none';

                        document.onpointermove = (evMove) => {
                            if (!isDragging) return;
                            let dx = evMove.clientX - dragStartX;
                            let desiredThumbLeftPx = thumbInitialLeftPx + dx;
                            let desiredValuePointOnTrackPx = desiredThumbLeftPx + valuePointOffsetWithinThumbPx;
                            let clampedValuePointOnTrackPx = Math.max(0, Math.min(desiredValuePointOnTrackPx, trackWidthPx));

                            let currentValue = (clampedValuePointOnTrackPx / trackWidthPx) * valueRange + minValue;
                            currentValue = Math.max(minValue, Math.min(maxValue, currentValue));
                            currentValue = parseFloat((Math.round((currentValue - minValue) / stepValue) * stepValue + minValue).toFixed(numDecimalPlaces));
                            currentValue = Math.max(minValue, Math.min(maxValue, currentValue));

                            hiddenInput.value = currentValue;
                            valueDisplay.textContent = `${currentValue} ${unit}`;

                            let finalValuePointOnTrackPx = ((currentValue - minValue) / valueRange) * trackWidthPx;
                            thumb.style.left = `${finalValuePointOnTrackPx - valuePointOffsetWithinThumbPx}px`;
                        };

                        document.onpointerup = (evUp) => {
                            if (!isDragging) return;
                            isDragging = false;
                            thumb.releasePointerCapture(evUp.pointerId);
                            thumb.style.cursor = 'grab';
                            document.body.style.userSelect = '';
                            document.onpointermove = null;
                            document.onpointerup = null;
                        };
                    };

                    // Scoring Info Display
                    const scoringInfoContainer = document.createElement('div');
                    scoringInfoContainer.className = 'slider-scoring-info mt-3 pt-3 border-t border-gray-200 text-sm text-gray-600';
                    const exactPointsP = document.createElement('p');
                    exactPointsP.className = 'mb-1';
                    exactPointsP.innerHTML = `Puntos por respuesta exacta (zona verde): <strong class="text-green-600">${question.slider_points_exact !== null ? question.slider_points_exact : 'N/A'}</strong>`;
                    scoringInfoContainer.appendChild(exactPointsP);
                    if (question.slider_points_partial !== null && question.slider_points_partial > 0 && thresholdPartial > 0) {
                        const partialPointsP = document.createElement('p');
                        partialPointsP.innerHTML = `Puntos por respuesta parcial (zona amarilla, +/- ${thresholdPartial} ${unit}): <strong class="text-yellow-600">${question.slider_points_partial}</strong>`;
                        scoringInfoContainer.appendChild(partialPointsP);
                    }
                    wizardAnswerOptions.appendChild(scoringInfoContainer);
                });
                break;
            default:
                wizardAnswerOptions.innerHTML = `<p class="text-red-500">Tipo de pregunta '${question.question_type}' no soportado.</p>`;
        }
    } catch (e) {
        console.error('Error rendering question in wizard:', e, 'Question data:', question);
        wizardQuestionText.textContent = 'Error de Visualización';
        wizardAnswerOptions.innerHTML = '<p class="text-red-500 text-center py-4">Error al mostrar pregunta.</p>';
    }

    wizardPrevBtn.style.display = index > 0 ? 'inline-flex' : 'none';
    wizardNextBtn.style.display = index < wizardAllRaceQuestions.length - 1 ? 'inline-flex' : 'none';
    wizardFinishBtn.style.display = index === wizardAllRaceQuestions.length - 1 ? 'inline-flex' : 'none';
}

function saveCurrentWizardAnswer() {
    if (!wizardAllRaceQuestions || wizardCurrentQuestionIndex < 0 || wizardCurrentQuestionIndex >= wizardAllRaceQuestions.length) return;
    const question = wizardAllRaceQuestions[wizardCurrentQuestionIndex];
    if (!question) return;

    switch (question.question_type) {
        case 'FREE_TEXT':
            const textarea = document.getElementById(`wizardFreeTextAnswer_${question.id}`);
            if (textarea) wizardUserAnswers[question.id] = { question_id: question.id, answer_text: textarea.value.trim() };
            break;
        case 'MULTIPLE_CHOICE':
            if (question.is_mc_multiple_correct) {
                const selected_ids = [];
                document.querySelectorAll(`input[name="wizard_q_${question.id}"]:checked`).forEach(cb => selected_ids.push(parseInt(cb.value)));
                wizardUserAnswers[question.id] = { question_id: question.id, selected_option_ids: selected_ids };
            } else {
                const radio = document.querySelector(`input[name="wizard_q_${question.id}"]:checked`);
                wizardUserAnswers[question.id] = { question_id: question.id, selected_option_id: radio ? parseInt(radio.value) : null };
            }
            break;
        case 'ORDERING':
            const listContainer = document.getElementById(`wizardOrderingList_${question.id}`);
            if (listContainer) {
                const ids = Array.from(listContainer.querySelectorAll('li[data-option-id]')).map(li => li.dataset.optionId);
                wizardUserAnswers[question.id] = { question_id: question.id, ordered_options_text: ids.join(',') };
            }
            break;
        case 'SLIDER':
            const slider = document.getElementById(`wizardSliderAnswer_${question.id}`); // Assuming slider input has this ID
            if (slider) {
                 wizardUserAnswers[question.id] = { question_id: question.id, slider_answer_value: parseFloat(slider.value) };
            }
            break;
    }
}

function handleNextWizardQuestion() {
    saveCurrentWizardAnswer();
    if (wizardCurrentQuestionIndex < wizardAllRaceQuestions.length - 1) {
        wizardCurrentQuestionIndex++;
        displayWizardQuestion(wizardCurrentQuestionIndex);
    }
}

function handlePreviousWizardQuestion() {
    saveCurrentWizardAnswer(); // Save before going back, in case user made changes
    if (wizardCurrentQuestionIndex > 0) {
        wizardCurrentQuestionIndex--;
        displayWizardQuestion(wizardCurrentQuestionIndex);
    }
}

// Helper function to update enabled/disabled state of move buttons in wizard ordering list
function updateWizardOrderingButtonStates(ulElement) {
    if (!ulElement) return;
    const listItems = ulElement.querySelectorAll('li[data-option-id]');
    listItems.forEach((li, index) => {
        const upButton = li.querySelector('.wizard-move-up-btn');
        const downButton = li.querySelector('.wizard-move-down-btn');

        if (upButton) {
            upButton.disabled = (index === 0);
            upButton.classList.toggle('opacity-50', upButton.disabled);
            upButton.classList.toggle('cursor-not-allowed', upButton.disabled);
        }
        if (downButton) {
            downButton.disabled = (index === listItems.length - 1);
            downButton.classList.toggle('opacity-50', downButton.disabled);
            downButton.classList.toggle('cursor-not-allowed', downButton.disabled);
        }
    });
}


// Event listeners for wizard buttons should be attached once the modal is in the DOM.
// This can be done in DOMContentLoaded or when the wizard HTML is confirmed to be present.
document.addEventListener('DOMContentLoaded', () => {
    const closeWizardModalBtn = document.getElementById('closeWizardModalBtn');
    const wizardPrevBtn = document.getElementById('wizardPrevBtn');
    const wizardNextBtn = document.getElementById('wizardNextBtn');
    const wizardFinishBtn = document.getElementById('wizardFinishBtn');

    if(closeWizardModalBtn) closeWizardModalBtn.addEventListener('click', closeWizard);
    if(wizardPrevBtn) wizardPrevBtn.addEventListener('click', handlePreviousWizardQuestion);
    if(wizardNextBtn) wizardNextBtn.addEventListener('click', handleNextWizardQuestion);

    if(wizardFinishBtn) {
        wizardFinishBtn.addEventListener('click', () => {
            saveCurrentWizardAnswer();
            if (Object.keys(wizardUserAnswers).length === 0) {
                showNotificationModal("Sin Respuestas", "No has respondido ninguna pregunta aún.", "info");
                return;
            }
            wizardFinishBtn.disabled = true;
            wizardFinishBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Guardando...';

            fetch(`/api/races/${currentRaceIdForWizard}/answers`, { // Use currentRaceIdForWizard
                method: 'POST',
                headers: { 'Content-Type': 'application/json', /* CSRF if needed */ },
                body: JSON.stringify(wizardUserAnswers)
            })
            .then(response => response.json().then(data => ({ ok: response.ok, status: response.status, body: data })))
            .then(result => {
                if (result.ok) {
                    closeWizard();
                    showNotificationModal("Éxito", result.body.message || '¡Respuestas guardadas!', "success");
                    // Consider a mechanism to update the league_detail_view UI if needed, e.g. badges
                } else {
                    showNotificationModal("Error", `Error: ${result.body.message || `Estado ${result.status}`}`, "error");
                }
            })
            .catch(error => {
                console.error('Error saving wizard answers:', error);
                showNotificationModal("Error de Conexión", "No se pudieron guardar las respuestas.", "error");
            })
            .finally(() => {
                wizardFinishBtn.disabled = false;
                wizardFinishBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Finalizar y Guardar';
            });
        });
    }
});
