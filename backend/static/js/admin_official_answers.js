// Global variable to store the current race ID being managed
let currentRaceIdForOfficialAnswers = null;
let questionsDataForOfficialAnswers = []; // To store questions globally for submission

function openOfficialAnswersModal(buttonElement) {
    const raceId = buttonElement.getAttribute('data-race-id');
    const raceTitle = buttonElement.getAttribute('data-race-title');

    currentRaceIdForOfficialAnswers = raceId;
    questionsDataForOfficialAnswers = []; // Reset

    document.getElementById('official-answers-modal-race-title').textContent = raceTitle;
    const formContainer = document.getElementById('official-answers-form-container');
    formContainer.innerHTML = '<p class="text-gray-500 text-center">Cargando preguntas...</p>'; // Loading state
    document.getElementById('official-answers-modal').classList.remove('hidden');

    // Fetch questions and existing official answers
    Promise.all([
        fetch(`/api/races/${raceId}/questions`).then(res => res.ok ? res.json() : Promise.reject(res)),
        fetch(`/api/races/${raceId}/official_answers`).then(res => res.ok ? res.json() : Promise.reject(res))
    ])
    .then(([questions, officialAnswers]) => {
        questionsDataForOfficialAnswers = questions; // Store for later use during submission
        renderOfficialAnswersForm(questions, officialAnswers, formContainer);
    })
    .catch(error => {
        console.error('Error fetching data for official answers:', error);
        formContainer.innerHTML = '<p class="text-red-500 text-center">Error al cargar los datos. Por favor, inténtelo de nuevo.</p>';
    });
}

function closeOfficialAnswersModal() {
    document.getElementById('official-answers-modal').classList.add('hidden');
    document.getElementById('official-answers-form-container').innerHTML = ''; // Clear content
    currentRaceIdForOfficialAnswers = null;
    questionsDataForOfficialAnswers = [];
}

function renderOfficialAnswersForm(questions, officialAnswers, container) {
    container.innerHTML = ''; // Clear loading state

    if (!questions || questions.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-center">No hay preguntas configuradas para esta carrera.</p>';
        return;
    }

    questions.forEach(question => {
        const officialAnswer = officialAnswers.find(oa => oa.question_id === question.id);

        const questionDiv = document.createElement('div');
        questionDiv.className = 'mb-6 p-4 border border-gray-200 rounded-lg shadow-sm';
        questionDiv.dataset.questionId = question.id; // Store question ID

        const questionTitle = document.createElement('h4');
        questionTitle.className = 'font-semibold text-gray-700 mb-2';
        questionTitle.textContent = `${question.text} (Tipo: ${question.question_type})`;
        questionDiv.appendChild(questionTitle);

        const inputContainer = document.createElement('div');
        inputContainer.className = 'space-y-2';

        switch (question.question_type) {
            case 'FREE_TEXT':
                const textarea = document.createElement('textarea');
                textarea.className = 'w-full p-2 border border-gray-300 rounded-md focus:ring-orange-500 focus:border-orange-500';
                textarea.rows = 3;
                textarea.name = `question-${question.id}`;
                textarea.value = officialAnswer ? officialAnswer.answer_text || '' : '';
                inputContainer.appendChild(textarea);
                break;

            case 'MULTIPLE_CHOICE':
                if (!question.options || question.options.length === 0) {
                    inputContainer.innerHTML = '<p class="text-sm text-gray-500">No hay opciones para esta pregunta.</p>';
                    break;
                }
                question.options.forEach(option => {
                    const optionDiv = document.createElement('div');
                    optionDiv.className = 'flex items-center';
                    const input = document.createElement('input');
                    input.value = option.id;

                    if (question.is_mc_multiple_correct) { // Checkbox for multiple correct
                        input.type = 'checkbox';
                        input.name = `question-${question.id}-option`;
                        input.className = 'h-4 w-4 text-orange-600 border-gray-300 rounded focus:ring-orange-500';
                        if (officialAnswer && officialAnswer.selected_mc_options && officialAnswer.selected_mc_options.some(sa => sa.option_id === option.id)) {
                            input.checked = true;
                        }
                    } else { // Radio for single correct
                        input.type = 'radio';
                        input.name = `question-${question.id}`; // Same name for radio group
                        input.className = 'h-4 w-4 text-orange-600 border-gray-300 focus:ring-orange-500';
                        if (officialAnswer && officialAnswer.selected_option_id === option.id) {
                            input.checked = true;
                        }
                    }

                    const label = document.createElement('label');
                    label.className = 'ml-2 block text-sm text-gray-700';
                    label.htmlFor = input.id = `q${question.id}-opt${option.id}`; // Unique ID for label association
                    label.textContent = option.option_text;

                    optionDiv.appendChild(input);
                    optionDiv.appendChild(label);
                    inputContainer.appendChild(optionDiv);
                });
                break;

            case 'ORDERING':
                const orderingTextarea = document.createElement('textarea');
                orderingTextarea.className = 'w-full p-2 border border-gray-300 rounded-md focus:ring-orange-500 focus:border-orange-500';
                orderingTextarea.rows = question.options.length > 0 ? question.options.length + 1 : 4;
                orderingTextarea.name = `question-${question.id}`;
                orderingTextarea.placeholder = "Escriba cada opción en una nueva línea, en el orden correcto.";

                if (officialAnswer && officialAnswer.answer_text) {
                    orderingTextarea.value = officialAnswer.answer_text;
                } else {
                    // Pre-fill with options for easier editing, if no answer yet
                    // orderingTextarea.value = question.options.map(opt => opt.option_text).join('\n');
                }
                inputContainer.appendChild(orderingTextarea);

                const originalOrderInfo = document.createElement('p');
                originalOrderInfo.className = 'text-xs text-gray-500 mt-1';
                originalOrderInfo.textContent = 'Opciones originales (para referencia): ' + question.options.map(opt => opt.option_text).join(', ');
                inputContainer.appendChild(originalOrderInfo);
                break;

            default:
                inputContainer.innerHTML = `<p class="text-sm text-red-500">Tipo de pregunta no soportado: ${question.question_type}</p>`;
        }
        questionDiv.appendChild(inputContainer);
        container.appendChild(questionDiv);
    });
}

document.getElementById('save-official-answers-btn').addEventListener('click', function() {
    if (!currentRaceIdForOfficialAnswers || !questionsDataForOfficialAnswers) {
        alert('Error: No hay carrera seleccionada o preguntas cargadas.');
        return;
    }

    const submittedAnswers = {};
    const formContainer = document.getElementById('official-answers-form-container');

    questionsDataForOfficialAnswers.forEach(question => {
        const questionId = question.id;
        const questionDiv = formContainer.querySelector(`div[data-question-id="${questionId}"]`);
        if (!questionDiv) return;

        const answerData = {};

        switch (question.question_type) {
            case 'FREE_TEXT':
                const textarea = questionDiv.querySelector(`textarea[name="question-${questionId}"]`);
                if (textarea) {
                    answerData.answer_text = textarea.value;
                }
                break;

            case 'MULTIPLE_CHOICE':
                if (question.is_mc_multiple_correct) {
                    const selectedCheckboxes = questionDiv.querySelectorAll(`input[name="question-${questionId}-option"]:checked`);
                    answerData.selected_option_ids = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));
                } else {
                    const selectedRadio = questionDiv.querySelector(`input[name="question-${questionId}"]:checked`);
                    answerData.selected_option_id = selectedRadio ? parseInt(selectedRadio.value) : null;
                }
                break;

            case 'ORDERING':
                const orderingTextarea = questionDiv.querySelector(`textarea[name="question-${questionId}"]`);
                if (orderingTextarea) {
                    answerData.ordered_options_text = orderingTextarea.value;
                }
                break;
        }
        submittedAnswers[questionId] = answerData;
    });

    // console.log("Submitting official answers:", submittedAnswers);

    fetch(`/api/races/${currentRaceIdForOfficialAnswers}/official_answers`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            // CSRF token might be needed if backend is configured for it
        },
        body: JSON.stringify(submittedAnswers)
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(err => Promise.reject(err));
        }
    })
    .then(data => {
        alert(data.message || 'Resultados oficiales guardados con éxito!');
        closeOfficialAnswersModal();
    })
    .catch(error => {
        console.error('Error saving official answers:', error);
        alert('Error al guardar los resultados: ' + (error.message || 'Error desconocido. Revise la consola.'));
    });
});

// Ensure modal is also closable by clicking its backdrop (if such element exists and is desired)
// This was in the example modal, but the new modal might not have a separate backdrop element.
// If `official-answers-modal` is the backdrop itself:
document.getElementById('official-answers-modal').addEventListener('click', function(e) {
    if (e.target === this) { // Check if the click is on the modal backdrop itself
        closeOfficialAnswersModal();
    }
});

// Prevent clicks inside the modal content from closing it
document.querySelector('#official-answers-modal > div').addEventListener('click', function(e) {
    e.stopPropagation();
});
