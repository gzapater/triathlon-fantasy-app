// Global variable to store the current race ID being managed
let currentRaceIdForOfficialAnswers = null;
let questionsDataForOfficialAnswers = []; // To store questions globally for submission
let draggedItem = null; // To store the element being dragged

// Helper function to determine the element to insert before
function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('li[draggable="true"]:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// Helper function to update the enabled/disabled state of move buttons in an ordering list
function updateOrderingButtonStates(ulElement) {
    const listItems = ulElement.querySelectorAll('li[data-option-id]');
    listItems.forEach((li, index) => {
        const upButton = li.querySelector('.move-up-btn');
        const downButton = li.querySelector('.move-down-btn');

        if (upButton) {
            upButton.disabled = (index === 0);
        }
        if (downButton) {
            downButton.disabled = (index === listItems.length - 1);
        }
    });
}

function openOfficialAnswersModal(buttonElement) {
    const raceId = buttonElement.getAttribute('data-race-id');
    const raceTitle = buttonElement.getAttribute('data-race-title');

    currentRaceIdForOfficialAnswers = raceId;
    questionsDataForOfficialAnswers = []; // Reset

    document.getElementById('official-answers-modal-race-title').textContent = raceTitle;
    const formContainer = document.getElementById('official-answers-form-container');
    formContainer.innerHTML = '<p class="text-gray-500 text-center">Cargando preguntas...</p>'; // Loading state
    document.getElementById('official-answers-modal').classList.remove('hidden');
    showLoadingBar();
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
    })
    .finally(() => {
        hideLoadingBar();
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
                const ul = document.createElement('ul');
                ul.className = 'list-none p-0 m-0'; // Basic styling for ul

                if (question.options && question.options.length > 0) {
                    let optionsToRender = [...question.options]; // Default to original order, clone to avoid modifying original

                    if (officialAnswer && officialAnswer.answer_text && officialAnswer.answer_text.trim() !== '') {
                        const orderedIds = officialAnswer.answer_text.split(',').map(idStr => parseInt(idStr.trim(), 10));
                        const optionsMap = new Map(question.options.map(opt => [opt.id, opt]));

                        const sortedOptionsFromAnswer = orderedIds.map(id => optionsMap.get(id)).filter(opt => opt !== undefined);

                        if (sortedOptionsFromAnswer.length === question.options.length) {
                            optionsToRender = sortedOptionsFromAnswer;
                            console.debug(`Options for QID ${question.id} sorted based on official answer: ${officialAnswer.answer_text}`);
                        } else {
                            // This handles cases where some IDs in answer_text might not be in current question.options
                            // or if the number of options has changed since the answer was saved.
                            console.warn(`Could not fully sort options for question ${question.id} based on official answer IDs. Some IDs may be invalid or options may have changed. Displaying in default order.`);
                            // Fallback to original/default order already set in optionsToRender
                        }
                    }

                    optionsToRender.forEach(option => {
                        const li = document.createElement('li');
                        li.dataset.optionId = option.id; // Keep data attribute on li
                        li.draggable = true;
                        // Use flex to arrange text and buttons
                        li.className = 'p-2 border mb-1 bg-gray-100 cursor-grab flex justify-between items-center';

                        const textSpan = document.createElement('span');
                        textSpan.textContent = option.option_text;
                        li.appendChild(textSpan);

                        const buttonContainer = document.createElement('div');
                        buttonContainer.className = 'space-x-1'; // Use space-x for horizontal spacing

                        const moveUpBtn = document.createElement('button');
                        moveUpBtn.innerHTML = '↑'; // Up arrow
                        moveUpBtn.className = 'move-up-btn px-2 py-1 border rounded text-xs hover:bg-gray-200';
                        buttonContainer.appendChild(moveUpBtn);

                        const moveDownBtn = document.createElement('button');
                        moveDownBtn.innerHTML = '↓'; // Down arrow
                        moveDownBtn.className = 'move-down-btn px-2 py-1 border rounded text-xs hover:bg-gray-200';
                        buttonContainer.appendChild(moveDownBtn);

                        li.appendChild(buttonContainer);

                        moveUpBtn.addEventListener('click', () => {
                            const currentLi = moveUpBtn.closest('li');
                            if (currentLi && currentLi.previousElementSibling) {
                                currentLi.parentNode.insertBefore(currentLi, currentLi.previousElementSibling);
                                updateOrderingButtonStates(ul);
                            }
                        });

                        moveDownBtn.addEventListener('click', () => {
                            const currentLi = moveDownBtn.closest('li');
                            if (currentLi && currentLi.nextElementSibling) {
                                // currentLi.parentNode.insertBefore(currentLi.nextElementSibling, currentLi); // This moves next one before current
                                currentLi.parentNode.insertBefore(currentLi, currentLi.nextElementSibling.nextSibling); // Correct way to move currentLi down
                                updateOrderingButtonStates(ul);
                            }
                        });

                        li.addEventListener('dragstart', (event) => {
                            if (event.target === li) { // Ensure drag only starts on li itself
                                draggedItem = event.target;
                                event.dataTransfer.setData('text/plain', event.target.dataset.optionId);
                                setTimeout(() => {
                                    event.target.classList.add('opacity-50', 'dragging');
                                }, 0);
                            } else {
                                event.preventDefault(); // Prevent dragging by buttons
                            }
                        });

                        li.addEventListener('dragend', (event) => {
                            // Clean up classes from the dragged item
                            event.target.classList.remove('opacity-50', 'dragging');
                            // Ensure any target highlighting is removed (if not handled by ul's dragleave/drop)
                            ul.querySelectorAll('.drag-over-target-li').forEach(item => item.classList.remove('drag-over-target-li'));
                            ul.classList.remove('drag-over-active-ul'); // Clean up UL indicator
                            draggedItem = null;
                        });

                        li.addEventListener('dragenter', (event) => {
                            event.preventDefault(); // Important for allowing drop
                            if (event.target.matches('li[draggable="true"]') && event.target !== draggedItem) {
                                event.target.classList.add('bg-gray-200', 'drag-over-target-li'); // Highlight potential drop target li
                            }
                        });

                        li.addEventListener('dragleave', (event) => {
                            if (event.target.matches('li[draggable="true"]') && event.target !== draggedItem) {
                                event.target.classList.remove('bg-gray-200', 'drag-over-target-li');
                            }
                        });

                        ul.appendChild(li);
                    });

                    updateOrderingButtonStates(ul); // Initial call to set button states

                    ul.addEventListener('dragenter', (event) => {
                        event.preventDefault();
                        if (event.target === ul) {
                             ul.classList.add('bg-yellow-100', 'drag-over-active-ul');
                        }
                    });

                    ul.addEventListener('dragleave', (event) => {
                        if (event.target === ul && !ul.contains(event.relatedTarget) || event.relatedTarget && event.relatedTarget.matches('li[draggable="true"]')) {
                           ul.classList.remove('bg-yellow-100', 'drag-over-active-ul');
                        }
                        if (!event.relatedTarget) {
                             ul.classList.remove('bg-yellow-100', 'drag-over-active-ul');
                        }
                    });

                    ul.addEventListener('dragover', (event) => {
                        event.preventDefault(); // This is crucial to allow dropping
                        // Visual feedback for where the item will be placed can be done here
                        // For example, by finding the `afterElement` and drawing a temporary line
                        // For now, we rely on li:dragenter/dragleave and ul:dragenter/dragleave
                        if (!ul.classList.contains('drag-over-active-ul')) {
                            ul.classList.add('bg-yellow-100', 'drag-over-active-ul');
                        }
                    });

                    ul.addEventListener('drop', (event) => {
                        event.preventDefault();
                        if (draggedItem) { // Check if we are actually dragging an item from this list
                            const afterElement = getDragAfterElement(ul, event.clientY);
                            if (afterElement) {
                                ul.insertBefore(draggedItem, afterElement);
                            } else {
                                ul.appendChild(draggedItem);
                            }
                            // Clean up classes on the dragged item itself is handled by li's dragend
                        }
                        // Clean up target highlighting on LIs and UL
                        ul.querySelectorAll('.drag-over-target-li').forEach(item => item.classList.remove('drag-over-target-li', 'bg-gray-200'));
                        ul.classList.remove('bg-yellow-100', 'drag-over-active-ul');

                        updateOrderingButtonStates(ul); // Update button states after drop
                        // draggedItem is cleared in dragend
                    });

                } else {
                    const noOptionsMsg = document.createElement('p');
                    noOptionsMsg.textContent = 'No hay opciones configuradas para esta pregunta de ordenamiento.';
                    noOptionsMsg.className = 'text-sm text-gray-500';
                    ul.appendChild(noOptionsMsg); // Or append to inputContainer directly
                }
                inputContainer.appendChild(ul);

                const originalOrderInfo = document.createElement('p');
                originalOrderInfo.className = 'text-xs text-gray-500 mt-1';
                originalOrderInfo.textContent = 'Opciones originales (para referencia): ' + question.options.map(opt => opt.option_text).join(', ');
                inputContainer.appendChild(originalOrderInfo);
                break;

            case 'SLIDER':
                const sliderInfoContainer = document.createElement('div');
                sliderInfoContainer.className = 'text-sm text-gray-600 space-y-1 mb-2';

                const unitP = document.createElement('p');
                unitP.textContent = `Unidad: ${question.slider_unit || 'N/A'}`;
                sliderInfoContainer.appendChild(unitP);

                const rangeP = document.createElement('p');
                rangeP.textContent = `Rango: ${question.slider_min_value} a ${question.slider_max_value}`;
                sliderInfoContainer.appendChild(rangeP);

                const stepP = document.createElement('p');
                stepP.textContent = `Paso: ${question.slider_step}`;
                sliderInfoContainer.appendChild(stepP);

                inputContainer.appendChild(sliderInfoContainer);

                const sliderCorrectInput = document.createElement('input');
                sliderCorrectInput.type = 'number';
                sliderCorrectInput.name = `question-${question.id}-slider-correct`;
                sliderCorrectInput.step = question.slider_step; // Use question's step for the input
                sliderCorrectInput.min = question.slider_min_value;
                sliderCorrectInput.max = question.slider_max_value;
                sliderCorrectInput.className = 'w-full p-2 border border-gray-300 rounded-md focus:ring-orange-500 focus:border-orange-500';
                if (officialAnswer && officialAnswer.correct_slider_value !== undefined && officialAnswer.correct_slider_value !== null) {
                    sliderCorrectInput.value = officialAnswer.correct_slider_value;
                }
                inputContainer.appendChild(sliderCorrectInput);
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
        // Assumes showNotificationModal is available globally from race_detail.html
        if (typeof showNotificationModal === 'function') {
            showNotificationModal('Error', 'No hay carrera seleccionada o preguntas cargadas.', 'error');
        } else {
            alert('Error: No hay carrera seleccionada o preguntas cargadas.'); // Fallback
        }
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
                const listElement = questionDiv.querySelector('ul');
                if (listElement) {
                    const orderedOptions = Array.from(listElement.querySelectorAll('li[data-option-id]'))
                                              .map(li => li.dataset.optionId);
                    answerData.ordered_options_text = orderedOptions.join(',');
                } else {
                    answerData.ordered_options_text = ''; // Or handle as an error/empty state
                }
                break;

            case 'SLIDER':
                const sliderCorrectInput = questionDiv.querySelector(`input[name="question-${questionId}-slider-correct"]`);
                if (sliderCorrectInput && sliderCorrectInput.value !== '') {
                    answerData.correct_slider_value = parseFloat(sliderCorrectInput.value);
                } else {
                    answerData.correct_slider_value = null; // Send null if empty, backend should validate if it's required
                }
                break;
        }
        submittedAnswers[questionId] = answerData;
    });

    // console.log("Submitting official answers:", submittedAnswers);
    showLoadingBar();
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
        if (typeof showNotificationModal === 'function') {
            showNotificationModal('Éxito', data.message || 'Resultados oficiales guardados con éxito!', 'success');
        } else {
            alert(data.message || 'Resultados oficiales guardados con éxito!'); // Fallback
        }
        closeOfficialAnswersModal();
    })
    .catch(error => {
        console.error('Error saving official answers:', error);
        if (typeof showNotificationModal === 'function') {
            showNotificationModal('Error', 'Error al guardar los resultados: ' + (error.message || 'Error desconocido. Revise la consola.'), 'error');
        } else {
            alert('Error al guardar los resultados: ' + (error.message || 'Error desconocido. Revise la consola.')); // Fallback
        }
    })
    .finally(() => {
        hideLoadingBar();
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
