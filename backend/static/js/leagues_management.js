document.addEventListener('DOMContentLoaded', function () {
    const openModalBtn = document.getElementById('openCreateLeagueModalBtn');
    const leagueModal = document.getElementById('leagueModal');
    const leagueModalDialog = document.getElementById('leagueModalDialog');
    const closeModalBtn = document.getElementById('closeLeagueModalBtn');
    const leagueForm = document.getElementById('leagueForm');
    const leagueModalTitle = document.getElementById('leagueModalTitle');
    const leagueIdInput = document.getElementById('leagueId');
    const leagueNameInput = document.getElementById('leagueName');
    const leagueDescriptionInput = document.getElementById('leagueDescription');
    const racesCheckboxContainer = document.getElementById('racesCheckboxContainer');
    const racesLoadingSpinner = document.getElementById('racesLoadingSpinner');
    const noRacesMessage = document.getElementById('noRacesForLeagueMessage');
    const leaguesTableBody = document.getElementById('leaguesTableBody');
    const leaguesLoadingSpinner = document.getElementById('leaguesLoadingSpinner');
    const noLeaguesMessage = document.getElementById('noLeaguesMessage');
    const saveLeagueBtn = document.getElementById('saveLeagueBtn');
    const saveLeagueBtnText = document.getElementById('saveLeagueBtnText');
    const saveLeagueSpinner = document.getElementById('saveLeagueSpinner');

    let availableRaces = []; // To store fetched races for reuse

    // --- Modal Handling ---
    function openModal(mode = 'create', league = null) {
        leagueForm.reset();
        leagueIdInput.value = '';
        racesCheckboxContainer.innerHTML = ''; // Clear previous race checkboxes
        noRacesMessage.classList.add('hidden');
        racesLoadingSpinner.classList.remove('hidden');

        if (mode === 'edit' && league) {
            leagueModalTitle.textContent = 'Editar Liga';
            leagueIdInput.value = league.id;
            leagueNameInput.value = league.name;
            leagueDescriptionInput.value = league.description || '';
            fetchAndPopulateRaces(league.race_ids || []);
        } else {
            leagueModalTitle.textContent = 'Crear Nueva Liga';
            fetchAndPopulateRaces([]);
        }
        leagueModal.classList.remove('hidden');
        setTimeout(() => { // Start transition after display:flex is applied
            leagueModalDialog.classList.remove('scale-95', 'opacity-0');
            leagueModalDialog.classList.add('scale-100', 'opacity-100');
        }, 20);
    }

    function closeModal() {
        leagueModalDialog.classList.add('scale-95', 'opacity-0');
        leagueModalDialog.classList.remove('scale-100', 'opacity-100');
        setTimeout(() => {
            leagueModal.classList.add('hidden');
        }, 300); // Duration of the transition
    }

    if (openModalBtn) {
        openModalBtn.addEventListener('click', () => openModal('create'));
    }
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }
    // Close modal on escape key
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !leagueModal.classList.contains('hidden')) {
            closeModal();
        }
    });
    // Close modal on outside click
    leagueModal.addEventListener('click', (event) => {
        if (event.target === leagueModal) {
            closeModal();
        }
    });

    // --- Race Population ---
    async function fetchAndPopulateRaces(selectedRaceIds = []) {
        racesLoadingSpinner.classList.remove('hidden');
        racesCheckboxContainer.innerHTML = '';
        noRacesMessage.classList.add('hidden');

        try {
            const response = await fetch('/api/races/planned_for_league_creation');
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to fetch races');
            }
            availableRaces = await response.json();

            racesLoadingSpinner.classList.add('hidden');
            if (availableRaces.length === 0) {
                noRacesMessage.classList.remove('hidden');
                return;
            }

            availableRaces.forEach(race => {
                const isChecked = selectedRaceIds.includes(race.id);
                const raceDiv = document.createElement('div');
                raceDiv.classList.add('flex', 'items-center', 'mb-2', 'p-2', 'hover:bg-gray-50', 'rounded-md');
                raceDiv.innerHTML = `
                    <input id="race-${race.id}" name="race_ids" value="${race.id}" type="checkbox" ${isChecked ? 'checked' : ''}
                           class="h-4 w-4 text-orange-600 border-gray-300 rounded focus:ring-orange-500">
                    <label for="race-${race.id}" class="ml-3 text-sm text-gray-700">
                        ${race.title} <span class="text-xs text-gray-500">(${new Date(race.event_date + 'T00:00:00').toLocaleDateString()})</span>
                    </label>
                `;
                racesCheckboxContainer.appendChild(raceDiv);
            });

        } catch (error) {
            console.error('Error fetching races:', error);
            racesLoadingSpinner.classList.add('hidden');
            racesCheckboxContainer.innerHTML = `<p class="text-red-500 text-sm">Error al cargar carreras: ${error.message}</p>`;
        }
    }

    // --- League Form Submission ---
    if (leagueForm) {
        leagueForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            showSavingSpinner(true);

            const leagueId = leagueIdInput.value;
            const name = leagueNameInput.value;
            const description = leagueDescriptionInput.value;
            const selectedRaceIds = Array.from(document.querySelectorAll('input[name="race_ids"]:checked'))
                                       .map(cb => parseInt(cb.value));

            const leagueData = { name, description, race_ids: selectedRaceIds };
            const method = leagueId ? 'PUT' : 'POST';
            const url = leagueId ? `/api/leagues/${leagueId}` : '/api/leagues';

            try {
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(leagueData),
                });

                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.message || (leagueId ? 'Failed to update league' : 'Failed to create league'));
                }

                showToast(result.message || (leagueId ? 'Liga actualizada con éxito' : 'Liga creada con éxito'), 'success');
                closeModal();
                fetchAndDisplayLeagues(); // Refresh the table
            } catch (error) {
                console.error('Error saving league:', error);
                showToast(error.message, 'error');
            } finally {
                showSavingSpinner(false);
            }
        });
    }

    function showSavingSpinner(isLoading) {
        if (isLoading) {
            saveLeagueBtnText.textContent = leagueIdInput.value ? 'Actualizando...' : 'Creando...';
            saveLeagueSpinner.classList.remove('hidden');
            saveLeagueBtn.disabled = true;
        } else {
            saveLeagueBtnText.textContent = leagueIdInput.value ? 'Guardar Cambios' : 'Guardar Liga';
            saveLeagueSpinner.classList.add('hidden');
            saveLeagueBtn.disabled = false;
        }
    }


    // --- Fetch and Display Leagues ---
    async function fetchAndDisplayLeagues() {
        if (!leaguesTableBody) return;
        leaguesLoadingSpinner.classList.remove('hidden');
        noLeaguesMessage.classList.add('hidden');
        leaguesTableBody.innerHTML = ''; // Clear existing rows except for loading/no message templates

        try {
            const response = await fetch('/api/leagues');
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to fetch leagues');
            }
            const leagues = await response.json();
            leaguesLoadingSpinner.classList.add('hidden');

            if (leagues.length === 0) {
                // Keep the colspan="5" row, but show the noLeaguesMessage inside it or a new row
                leaguesTableBody.innerHTML = `<tr><td colspan="5" class="text-center py-10 px-5"><p class="text-gray-500">No se encontraron ligas. ¡Crea una nueva!</p></td></tr>`;
                return;
            }

            leagues.forEach(league => {
                const row = leaguesTableBody.insertRow();
                row.classList.add('border-b', 'border-gray-200', 'hover:bg-gray-100');
                row.innerHTML = `
                    <td class="px-5 py-4 text-sm">${league.name}</td>
                    <td class="px-5 py-4 text-sm">${league.description || 'N/A'}</td>
                    <td class="px-5 py-4 text-sm">${league.admin_username || 'N/A'}</td>
                    <td class="px-5 py-4 text-sm">${league.race_ids ? league.race_ids.length : 0}</td>
                    <td class="px-5 py-4 text-sm">
                        <button class="edit-league-btn text-blue-600 hover:text-blue-800 mr-3 transition duration-150" data-league-id="${league.id}" title="Editar Liga">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="delete-league-btn text-red-600 hover:text-red-800 transition duration-150" data-league-id="${league.id}" title="Eliminar Liga">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                `;
            });
            addEventListenersToButtons();

        } catch (error) {
            console.error('Error fetching leagues:', error);
            leaguesLoadingSpinner.classList.add('hidden');
            leaguesTableBody.innerHTML = `<tr><td colspan="5" class="text-center py-10 px-5"><p class="text-red-500">Error al cargar ligas: ${error.message}</p></td></tr>`;
        }
    }

    function addEventListenersToButtons() {
        document.querySelectorAll('.edit-league-btn').forEach(button => {
            button.addEventListener('click', async function() {
                const leagueId = this.dataset.leagueId;
                // Fetch full league details for editing
                try {
                    const response = await fetch(`/api/leagues/${leagueId}`);
                    if (!response.ok) throw new Error('Failed to fetch league details');
                    const leagueData = await response.json();
                    openModal('edit', leagueData);
                } catch (error) {
                    console.error('Error fetching league for edit:', error);
                    showToast(error.message, 'error');
                }
            });
        });

        document.querySelectorAll('.delete-league-btn').forEach(button => {
            button.addEventListener('click', async function() {
                const leagueId = this.dataset.leagueId;
                if (confirm('¿Estás seguro de que quieres eliminar esta liga? Esta acción no se puede deshacer.')) {
                    try {
                        const response = await fetch(`/api/leagues/${leagueId}`, { method: 'DELETE' });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.message || 'Failed to delete league');

                        showToast(result.message || 'Liga eliminada con éxito', 'success');
                        fetchAndDisplayLeagues(); // Refresh
                    } catch (error) {
                        console.error('Error deleting league:', error);
                        showToast(error.message, 'error');
                    }
                }
            });
        });
    }

    // --- Toast Notification ---
    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('flash-messages-container') || createToastContainer();
        const toastId = `toast-${Date.now()}`;
        const bgColor = type === 'success' ? 'bg-green-100 border-green-300 text-green-700' :
                        type === 'error' ? 'bg-red-100 border-red-300 text-red-700' :
                        'bg-blue-100 border-blue-300 text-blue-700';
        const icon = type === 'success' ? '<i class="fas fa-check-circle"></i> Éxito:' :
                     type === 'error' ? '<i class="fas fa-times-circle"></i> Error:' :
                     '<i class="fas fa-info-circle"></i> Info:';

        const toastHTML = `
            <div id="${toastId}" class="alert-flash p-4 mb-3 text-sm rounded-lg shadow-md ${bgColor}" role="alert">
                <div class="flex items-center">
                    <span class="font-medium mr-2">${icon}</span>
                    <span>${message}</span>
                    <button type="button" class="ml-auto -mx-1.5 -my-1.5 bg-transparent text-current rounded-lg focus:ring-2 p-1.5 inline-flex h-8 w-8 hover:bg-opacity-20"
                            onclick="this.closest('.alert-flash').remove();" aria-label="Dismiss">
                        <span class="sr-only">Dismiss</span>
                        <svg aria-hidden="true" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
                    </button>
                </div>
            </div>
        `;
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);

        const toastElement = document.getElementById(toastId);
        setTimeout(() => {
            if (toastElement) {
                toastElement.style.transition = 'opacity 0.5s ease-out';
                toastElement.style.opacity = '0';
                setTimeout(() => toastElement.remove(), 500);
            }
        }, 5000); // Auto-dismiss after 5 seconds
    }

    function createToastContainer() {
        let container = document.getElementById('flash-messages-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'flash-messages-container';
            container.className = 'fixed top-5 left-1/2 transform -translate-x-1/2 z-[1000] w-full max-w-xl px-4';
            container.style.marginTop = '60px'; // Consistent with _header.html
            document.body.appendChild(container);
        }
        return container;
    }

    // Initial load
    if (leaguesTableBody) { // Only run if on the leagues management page
        fetchAndDisplayLeagues();
    }
});
