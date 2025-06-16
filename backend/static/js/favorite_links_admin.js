// Favorite Links Admin JS
document.addEventListener('DOMContentLoaded', function() {
    // Race ID is available globally from race_detail.html as 'raceId'
    // currentUserRole is also available globally

    // DOM Element References
    const openModalBtn = document.getElementById('openFavoriteLinksModalBtn');
    const modal = document.getElementById('favoriteLinksModal');
    const closeModalHeaderBtn = document.getElementById('closeFavoriteLinksModalHeaderBtn');
    const closeModalFooterBtn = document.getElementById('closeFavoriteLinksModalBtn');

    const existingLinksListDiv = document.getElementById('existingFavoriteLinksList');

    const addLinkForm = document.getElementById('addFavoriteLinkForm');
    const newLinkTitleInput = document.getElementById('newLinkTitle');
    const newLinkUrlInput = document.getElementById('newLinkUrl');
    const newLinkOrderInput = document.getElementById('newLinkOrder');
    const addNewLinkBtn = document.getElementById('addNewFavoriteLinkBtn');

    const editLinkFormContainer = document.getElementById('editFavoriteLinkFormContainer');
    const editingFavoriteLinkIdInput = document.getElementById('editingFavoriteLinkId'); // Hidden input in HTML
    const editLinkTitleInput = document.getElementById('editLinkTitle');
    const editLinkUrlInput = document.getElementById('editLinkUrl');
    const editLinkOrderInput = document.getElementById('editLinkOrder');
    const saveEditedLinkBtn = document.getElementById('saveEditedFavoriteLinkBtn');
    const cancelEditLinkBtn = document.getElementById('cancelEditFavoriteLinkBtn');

    const saveOrderBtn = document.getElementById('saveFavoriteLinksOrderBtn');

    // --- Utility for API calls ---
    async function callApi(endpoint, method = 'GET', body = null) {
        const headers = { 'Content-Type': 'application/json' };
        // Add CSRF token if needed by your Flask setup (e.g., for POST, PUT, DELETE)
        // headers['X-CSRFToken'] = '{{ csrf_token() }}'; // This Jinja won't work in JS file. Get from HTML if needed.

        const config = { method, headers };
        if (body) {
            config.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(endpoint, config);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: response.statusText }));
                throw new Error(errorData.message || `HTTP error ${response.status}`);
            }
            if (response.status === 204) return null; // No content
            return response.json();
        } catch (error) {
            console.error('API Call Error:', error);
            alert(`Error: ${error.message}`);
            throw error; // Re-throw to be caught by caller
        }
    }

    // --- Modal Operations ---
    function openFavoriteLinksModal() {
        if (modal) {
            modal.style.display = 'flex';
            if (typeof raceId !== 'undefined' && raceId) {
                fetchAndRenderExistingFavoriteLinks(raceId);
            } else {
                existingLinksListDiv.innerHTML = '<p class="text-red-500">Error: Race ID no disponible.</p>';
            }
            editLinkFormContainer.style.display = 'none';
            if(addLinkForm) addLinkForm.style.display = 'block';
            if(addLinkForm) addLinkForm.reset();
        }
    }

    function closeFavoriteLinksModal() {
        if (modal) {
            modal.style.display = 'none';
        }
        if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
        if(addLinkForm) addLinkForm.style.display = 'block';
        editingFavoriteLinkIdInput.value = ''; // Clear editing ID
    }

    if (openModalBtn) openModalBtn.addEventListener('click', openFavoriteLinksModal);
    if (closeModalHeaderBtn) closeModalHeaderBtn.addEventListener('click', closeFavoriteLinksModal);
    if (closeModalFooterBtn) closeModalFooterBtn.addEventListener('click', closeFavoriteLinksModal);

    // --- Fetch and Render Existing Links ---
    async function fetchAndRenderExistingFavoriteLinks(currentRaceId) {
        if (!existingLinksListDiv) return;
        existingLinksListDiv.innerHTML = '<p class="text-gray-500">Cargando enlaces...</p>';

        try {
            const links = await callApi(`/api/races/${currentRaceId}/favorite_links`);
            existingLinksListDiv.innerHTML = ''; // Clear loading
            if (links && links.length > 0) {
                links.forEach(link => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'flex items-center justify-between p-2 border border-gray-300 rounded bg-white shadow-sm';
                    itemDiv.dataset.linkId = link.id;

                    itemDiv.innerHTML = `
                        <div class="flex-grow">
                            <span class="font-semibold link-title">${link.title}</span>
                            <a href="${link.url}" target="_blank" class="link-url text-blue-500 hover:underline text-sm ml-2" title="${link.url}">${link.url.substring(0,30)}...</a>
                        </div>
                        <div class="flex items-center">
                            <label for="order-${link.id}" class="text-sm mr-1">Orden:</label>
                            <input type="number" value="${link.order}" id="order-${link.id}" data-link-id="${link.id}" class="link-order-input w-16 p-1 border border-gray-300 rounded text-sm mr-2">
                            <button class="edit-link-btn btn btn-xs bg-blue-500 hover:bg-blue-600 text-white py-1 px-2 mr-1" data-link-id="${link.id}" data-title="${link.title}" data-url="${link.url}" data-order="${link.order}"><i class="fas fa-edit"></i></button>
                            <button class="delete-link-btn btn btn-xs bg-red-500 hover:bg-red-600 text-white py-1 px-2" data-link-id="${link.id}"><i class="fas fa-trash"></i></button>
                        </div>
                    `;
                    existingLinksListDiv.appendChild(itemDiv);
                });

                // Add event listeners to new buttons
                existingLinksListDiv.querySelectorAll('.edit-link-btn').forEach(btn => btn.addEventListener('click', handleEditLinkBtnClick));
                existingLinksListDiv.querySelectorAll('.delete-link-btn').forEach(btn => btn.addEventListener('click', handleDeleteLinkBtnClick));
            } else {
                existingLinksListDiv.innerHTML = '<p class="text-gray-500">No hay enlaces guardados para esta carrera.</p>';
            }
        } catch (error) {
            existingLinksListDiv.innerHTML = '<p class="text-red-500">Error al cargar enlaces.</p>';
        }
    }

    // --- Add New Link ---
    async function handleAddNewFavoriteLink() {
        if (!newLinkTitleInput || !newLinkUrlInput || !newLinkOrderInput || !addNewLinkBtn) return;

        const title = newLinkTitleInput.value.trim();
        const url = newLinkUrlInput.value.trim();
        const order = newLinkOrderInput.value ? parseInt(newLinkOrderInput.value) : 0;

        if (!title || !url) {
            alert('Título y URL son obligatorios.');
            return;
        }
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            alert('URL debe empezar con http:// o https://');
            return;
        }

        addNewLinkBtn.disabled = true; addNewLinkBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Añadiendo...';

        try {
            await callApi(`/api/races/${raceId}/favorite_links`, 'POST', { title, url, order });
            if(addLinkForm) addLinkForm.reset();
            fetchAndRenderExistingFavoriteLinks(raceId); // Refresh list in modal
            if (typeof fetchAndDisplayFavoriteLinks === "function") { // This function is in race_detail.html
                fetchAndDisplayFavoriteLinks(raceId); // Refresh public list
            }
        } finally {
            addNewLinkBtn.disabled = false; addNewLinkBtn.innerHTML = '<i class="fas fa-plus mr-2"></i>Añadir Enlace';
        }
    }
    if (addNewLinkBtn) addNewLinkBtn.addEventListener('click', handleAddNewFavoriteLink);

    // --- Edit Link ---
    function handleEditLinkBtnClick(event) {
        const btn = event.currentTarget;
        editingFavoriteLinkIdInput.value = btn.dataset.linkId;
        editLinkTitleInput.value = btn.dataset.title;
        editLinkUrlInput.value = btn.dataset.url;
        editLinkOrderInput.value = btn.dataset.order;

        if(addLinkForm) addLinkForm.style.display = 'none';
        if(editLinkFormContainer) editLinkFormContainer.style.display = 'block';
    }

    if (cancelEditLinkBtn) {
        cancelEditLinkBtn.addEventListener('click', () => {
            if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
            if(addLinkForm) addLinkForm.style.display = 'block';
            editingFavoriteLinkIdInput.value = '';
        });
    }

    async function handleSaveEditedFavoriteLink() {
        if (!saveEditedLinkBtn || !editingFavoriteLinkIdInput || !editLinkTitleInput || !editLinkUrlInput || !editLinkOrderInput) return;

        const linkId = editingFavoriteLinkIdInput.value;
        const title = editLinkTitleInput.value.trim();
        const url = editLinkUrlInput.value.trim();
        const order = parseInt(editLinkOrderInput.value);

        if (!linkId || !title || !url) {
            alert('Título y URL son obligatorios.');
            return;
        }
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            alert('URL debe empezar con http:// o https://');
            return;
        }
        if (isNaN(order)) {
            alert('Orden debe ser un número.');
            return;
        }

        saveEditedLinkBtn.disabled = true; saveEditedLinkBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Guardando...';

        try {
            await callApi(`/api/favorite_links/${linkId}`, 'PUT', { title, url, order });
            if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
            if(addLinkForm) addLinkForm.style.display = 'block';
            editingFavoriteLinkIdInput.value = '';
            fetchAndRenderExistingFavoriteLinks(raceId); // Refresh list in modal
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId); // Refresh public list
            }
        } finally {
            saveEditedLinkBtn.disabled = false; saveEditedLinkBtn.innerHTML = '<i class="fas fa-save mr-2"></i>Guardar Cambios Enlace';
        }
    }
    if (saveEditedLinkBtn) saveEditedLinkBtn.addEventListener('click', handleSaveEditedFavoriteLink);

    // --- Delete Link ---
    function handleDeleteLinkBtnClick(event) {
        const linkId = event.currentTarget.dataset.linkId;
        if (confirm(`¿Estás seguro de que quieres eliminar este enlace?`)) {
            handleDeleteFavoriteLink(linkId);
        }
    }

    async function handleDeleteFavoriteLink(linkId) {
        // Consider adding loading state to the specific delete button if possible
        try {
            await callApi(`/api/favorite_links/${linkId}`, 'DELETE');
            fetchAndRenderExistingFavoriteLinks(raceId); // Refresh list in modal
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId); // Refresh public list
            }
        } catch (error) {
            // Error already alerted by callApi
        }
    }

    // --- Save Order ---
    async function handleSaveLinksOrder() {
        if (!saveOrderBtn || !existingLinksListDiv) return;

        const linkOrderInputs = existingLinksListDiv.querySelectorAll('.link-order-input');
        let linksData = [];
        linkOrderInputs.forEach(input => {
            linksData.push({
                id: parseInt(input.dataset.linkId),
                order: parseInt(input.value)
            });
        });

        // Sort by the new order values, then by ID for stability if orders are same
        linksData.sort((a, b) => {
            if (a.order === b.order) return a.id - b.id;
            return a.order - b.order;
        });

        const orderedLinkIds = linksData.map(link => link.id);

        if (orderedLinkIds.length === 0) {
            // alert("No hay enlaces para reordenar o no se pudo determinar el orden.");
            // This is fine, maybe user cleared all links or inputs.
            // The API should handle empty list if necessary, or we can skip call.
            // For now, let's proceed, API should handle it.
        }

        saveOrderBtn.disabled = true; saveOrderBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Guardando Orden...';

        try {
            await callApi(`/api/races/${raceId}/favorite_links/reorder`, 'POST', { link_ids: orderedLinkIds });
            fetchAndRenderExistingFavoriteLinks(raceId); // Refresh list in modal
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId); // Refresh public list
            }
            alert('Orden de enlaces guardado.');
        } finally {
            saveOrderBtn.disabled = false; saveOrderBtn.innerHTML = '<i class="fas fa-save mr-2"></i>Guardar Orden';
        }
    }
    if (saveOrderBtn) saveOrderBtn.addEventListener('click', handleSaveLinksOrder);

});
