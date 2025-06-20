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
    // New title select and custom input for Add form
    const newLinkTitleSelect = document.getElementById('newLinkTitleSelect');
    const newLinkCustomTitleInput = document.getElementById('newLinkCustomTitle');
    const newLinkUrlInput = document.getElementById('newLinkUrl');
    const newLinkOrderInput = document.getElementById('newLinkOrder');
    const addNewLinkBtn = document.getElementById('addNewFavoriteLinkBtn');

    const editLinkFormContainer = document.getElementById('editFavoriteLinkFormContainer');
    const editingFavoriteLinkIdInput = document.getElementById('editingFavoriteLinkId');
    // New title select and custom input for Edit form
    const editLinkTitleSelect = document.getElementById('editLinkTitleSelect');
    const editLinkCustomTitleInput = document.getElementById('editLinkCustomTitle');
    const editLinkUrlInput = document.getElementById('editLinkUrl');
    const editLinkOrderInput = document.getElementById('editLinkOrder');
    const saveEditedLinkBtn = document.getElementById('saveEditedFavoriteLinkBtn');
    const cancelEditLinkBtn = document.getElementById('cancelEditFavoriteLinkBtn');

    const saveOrderBtn = document.getElementById('saveFavoriteLinksOrderBtn');

    // --- Utility for API calls ---
    async function callApi(endpoint, method = 'GET', body = null) {
        const headers = { 'Content-Type': 'application/json' };
        const config = { method, headers };
        if (body) {
            config.body = JSON.stringify(body);
        }
        showLoadingBar();
        try {
            const response = await fetch(endpoint, config);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: response.statusText }));
                throw new Error(errorData.message || `HTTP error ${response.status}`);
            }
            if (response.status === 204) return null;
            return response.json();
        } catch (error) {
            console.error('API Call Error:', error);
            // Assumes showNotificationModal is available globally from race_detail.html
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Error de API', error.message, 'error');
            } else {
                alert(`Error: ${error.message}`); // Fallback
            }
            throw error;
        } finally {
            hideLoadingBar();
        }
    }

    // --- Custom Title Visibility Logic ---
    function handleTitleDropdownChange(dropdownElement, customTitleInputElement) {
        if (dropdownElement.value === "Otros") {
            customTitleInputElement.style.display = "block";
        } else {
            customTitleInputElement.style.display = "none";
            customTitleInputElement.value = ""; // Clear custom title if not "Otros"
        }
    }

    if (newLinkTitleSelect && newLinkCustomTitleInput) {
        newLinkTitleSelect.addEventListener('change', () => handleTitleDropdownChange(newLinkTitleSelect, newLinkCustomTitleInput));
    }
    if (editLinkTitleSelect && editLinkCustomTitleInput) {
        editLinkTitleSelect.addEventListener('change', () => handleTitleDropdownChange(editLinkTitleSelect, editLinkCustomTitleInput));
    }

    // --- Modal Operations ---
    function openFavoriteLinksModal() {
        if (modal) {
            modal.style.display = 'flex';
            if (typeof raceId !== 'undefined' && raceId) {
                fetchAndRenderExistingFavoriteLinks(raceId);
            } else {
                if(existingLinksListDiv) existingLinksListDiv.innerHTML = '<p class="text-red-500">Error: Race ID no disponible.</p>';
            }
            if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
            if(addLinkForm) {
                addLinkForm.style.display = 'block';
                addLinkForm.reset(); // Reset add form
            }
            if(newLinkTitleSelect) newLinkTitleSelect.value = newLinkTitleSelect.options[0].value; // Reset select
            if(newLinkCustomTitleInput) { // Reset custom title field
                newLinkCustomTitleInput.value = '';
                newLinkCustomTitleInput.style.display = 'none';
            }
        }
    }

    function closeFavoriteLinksModal() {
        if (modal) {
            modal.style.display = 'none';
        }
        if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
        if(addLinkForm) addLinkForm.style.display = 'block';
        if(editingFavoriteLinkIdInput) editingFavoriteLinkIdInput.value = '';
        // Reset edit form fields as well
        if(editLinkTitleSelect) editLinkTitleSelect.value = editLinkTitleSelect.options[0].value;
        if(editLinkCustomTitleInput) {
            editLinkCustomTitleInput.value = '';
            editLinkCustomTitleInput.style.display = 'none';
        }
        if(editLinkUrlInput) editLinkUrlInput.value = '';
        if(editLinkOrderInput) editLinkOrderInput.value = '';
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
            existingLinksListDiv.innerHTML = '';
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
        if (!newLinkTitleSelect || !newLinkCustomTitleInput || !newLinkUrlInput || !newLinkOrderInput || !addNewLinkBtn) return;

        let title = newLinkTitleSelect.value;
        if (title === "Otros") {
            title = newLinkCustomTitleInput.value.trim();
            if (!title) {
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('Validación Fallida', "El título personalizado no puede estar vacío si se selecciona 'Otros'.", 'validation');
                } else {
                    alert("El título personalizado no puede estar vacío si se selecciona 'Otros'.");
                }
                return;
            }
        }

        const url = newLinkUrlInput.value.trim();
        const order = newLinkOrderInput.value ? parseInt(newLinkOrderInput.value) : 0;

        if (!title || !url) {
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Validación Fallida', 'Título y URL son obligatorios.', 'validation');
            } else {
                alert('Título y URL son obligatorios.');
            }
            return;
        }
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Validación Fallida', 'URL debe empezar con http:// o https://', 'validation');
            } else {
                alert('URL debe empezar con http:// o https://');
            }
            return;
        }

        addNewLinkBtn.disabled = true; addNewLinkBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Añadiendo...';

        try {
            await callApi(`/api/races/${raceId}/favorite_links`, 'POST', { title, url, order });
            if(addLinkForm) addLinkForm.reset();
            newLinkTitleSelect.value = newLinkTitleSelect.options[0].value; // Reset select
            newLinkCustomTitleInput.value = ''; // Reset custom input
            newLinkCustomTitleInput.style.display = 'none'; // Hide custom input

            fetchAndRenderExistingFavoriteLinks(raceId);
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId);
            }
        } finally {
            addNewLinkBtn.disabled = false; addNewLinkBtn.innerHTML = '<i class="fas fa-plus mr-2"></i>Añadir Enlace';
        }
    }
    if (addNewLinkBtn) addNewLinkBtn.addEventListener('click', handleAddNewFavoriteLink);

    // --- Edit Link ---
    function handleEditLinkBtnClick(event) {
        const btn = event.currentTarget;
        const linkData = {
            id: btn.dataset.linkId,
            title: btn.dataset.title,
            url: btn.dataset.url,
            order: btn.dataset.order
        };
        populateEditLinkForm(linkData);
    }

    function populateEditLinkForm(linkData) {
        editingFavoriteLinkIdInput.value = linkData.id;
        editLinkUrlInput.value = linkData.url;
        editLinkOrderInput.value = linkData.order;

        const currentTitle = linkData.title;
        let isPredefined = false;
        for (let option of editLinkTitleSelect.options) {
            if (option.value === currentTitle && option.value !== "Otros") {
                isPredefined = true;
                break;
            }
        }

        if (isPredefined) {
            editLinkTitleSelect.value = currentTitle;
            editLinkCustomTitleInput.value = "";
            editLinkCustomTitleInput.style.display = "none";
        } else {
            editLinkTitleSelect.value = "Otros";
            editLinkCustomTitleInput.value = currentTitle; // Could be "" if title was "Otros" literally
            editLinkCustomTitleInput.style.display = "block";
        }

        if(addLinkForm) addLinkForm.style.display = 'none';
        if(editLinkFormContainer) editLinkFormContainer.style.display = 'block';
    }

    if (cancelEditLinkBtn) {
        cancelEditLinkBtn.addEventListener('click', () => {
            if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
            if(addLinkForm) addLinkForm.style.display = 'block';
            if(editingFavoriteLinkIdInput) editingFavoriteLinkIdInput.value = '';
            // Reset edit form select and custom input too
            if(editLinkTitleSelect) editLinkTitleSelect.value = editLinkTitleSelect.options[0].value;
            if(editLinkCustomTitleInput) {
                editLinkCustomTitleInput.value = '';
                editLinkCustomTitleInput.style.display = 'none';
            }
        });
    }

    async function handleSaveEditedFavoriteLink() {
        if (!saveEditedLinkBtn || !editingFavoriteLinkIdInput || !editLinkTitleSelect || !editLinkCustomTitleInput || !editLinkUrlInput || !editLinkOrderInput) return;

        const linkId = editingFavoriteLinkIdInput.value;
        let title = editLinkTitleSelect.value;
        if (title === "Otros") {
            title = editLinkCustomTitleInput.value.trim();
            if (!title) {
                if (typeof showNotificationModal === 'function') {
                    showNotificationModal('Validación Fallida', "El título personalizado no puede estar vacío si se selecciona 'Otros'.", 'validation');
                } else {
                    alert("El título personalizado no puede estar vacío si se selecciona 'Otros'.");
                }
                return;
            }
        }

        const url = editLinkUrlInput.value.trim();
        const order = parseInt(editLinkOrderInput.value);

        if (!linkId || !title || !url) {
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Validación Fallida', 'ID, Título y URL son obligatorios.', 'validation');
            } else {
                alert('ID, Título y URL son obligatorios.');
            }
            return;
        }
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Validación Fallida', 'URL debe empezar con http:// o https://', 'validation');
            } else {
                alert('URL debe empezar con http:// o https://');
            }
            return;
        }
        if (isNaN(order)) {
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Validación Fallida', 'Orden debe ser un número.', 'validation');
            } else {
                alert('Orden debe ser un número.');
            }
            return;
        }

        saveEditedLinkBtn.disabled = true; saveEditedLinkBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Guardando...';

        try {
            await callApi(`/api/favorite_links/${linkId}`, 'PUT', { title, url, order });
            if(editLinkFormContainer) editLinkFormContainer.style.display = 'none';
            if(addLinkForm) addLinkForm.style.display = 'block';
            if(editingFavoriteLinkIdInput) editingFavoriteLinkIdInput.value = '';

            fetchAndRenderExistingFavoriteLinks(raceId);
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId);
            }
        } finally {
            saveEditedLinkBtn.disabled = false; saveEditedLinkBtn.innerHTML = '<i class="fas fa-save mr-2"></i>Guardar Cambios Enlace';
        }
    }
    if (saveEditedLinkBtn) saveEditedLinkBtn.addEventListener('click', handleSaveEditedFavoriteLink);

    // --- Delete Link ---
    function handleDeleteLinkBtnClick(event) {
        const linkId = event.currentTarget.dataset.linkId;
        const linkTitle = event.currentTarget.closest('.flex.items-center.justify-between').querySelector('.link-title').textContent;

        const title = 'Confirmar Eliminación';
        const message = `¿Estás seguro de que quieres eliminar el enlace "${linkTitle}"?`;

        // Assuming showConfirmDeleteRaceModal is generic enough or we'll create a new one.
        // For now, let's use the existing one if available, understanding it might need adjustment or a dedicated function.
        if (typeof showConfirmDeleteRaceModal === 'function') {
            showConfirmDeleteRaceModal(title, message, () => {
                actualDeleteFavoriteLink(linkId);
            });
        } else if (confirm(message)) { // Fallback to original confirm
            actualDeleteFavoriteLink(linkId);
        }
    }

    async function actualDeleteFavoriteLink(linkId) {
        try {
            await callApi(`/api/favorite_links/${linkId}`, 'DELETE');
            // showNotificationModal is assumed to be available for success message
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Éxito', 'Enlace eliminado correctamente.', 'success');
            } else {
                // alert('Enlace eliminado correctamente.'); // No alert on success if modal not found, error handled by callApi
            }
            fetchAndRenderExistingFavoriteLinks(raceId);
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId);
            }
        } catch (error) {
            // Error already alerted by callApi (which now uses showNotificationModal)
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
                order: parseInt(input.value) || 0 // Default to 0 if NaN or empty
            });
        });

        linksData.sort((a, b) => {
            if (a.order === b.order) return a.id - b.id;
            return a.order - b.order;
        });

        const orderedLinkIds = linksData.map(link => link.id);

        saveOrderBtn.disabled = true; saveOrderBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Guardando Orden...';

        try {
            await callApi(`/api/races/${raceId}/favorite_links/reorder`, 'POST', { link_ids: orderedLinkIds });
            fetchAndRenderExistingFavoriteLinks(raceId);
            if (typeof fetchAndDisplayFavoriteLinks === "function") {
                fetchAndDisplayFavoriteLinks(raceId);
            }
            if (typeof showNotificationModal === 'function') {
                showNotificationModal('Éxito', 'Orden de enlaces guardado.', 'success');
            } else {
                alert('Orden de enlaces guardado.'); // Fallback
            }
        } finally {
            saveOrderBtn.disabled = false; saveOrderBtn.innerHTML = '<i class="fas fa-save mr-2"></i>Guardar Orden';
        }
    }
    if (saveOrderBtn) saveOrderBtn.addEventListener('click', handleSaveLinksOrder);

});
