document.addEventListener('DOMContentLoaded', function() {
    const raceFormatSelect = document.getElementById('raceFormat');
    const raceSegmentsContainer = document.getElementById('raceSegmentsContainer');
    const createRaceForm = document.getElementById('createRaceForm');
    const errorMessagesDiv = document.getElementById('errorMessages');

    // --- Predefined Segment Mappings (Name to ID) ---
    // These should match the IDs from your seeded Segment data.
    // TODO: Fetch these from an API or ensure they are stable if hardcoding.
    const segmentNameToId = {
        "Natación": 1,
        "Ciclismo": 2,
        "Carrera a pie": 3,
        "Transición 1 (T1)": 4,
        "Transición 2 (T2)": 5
    };

    // --- Predefined Race Format to Segments Mapping ---
    // Maps RaceFormat NAME to an array of Segment NAMES.
    const raceFormatToSegments = {
        "Triatlón": ["Natación", "Transición 1 (T1)", "Ciclismo", "Transición 2 (T2)", "Carrera a pie"],
        "Duatlón": ["Carrera a pie", "Transición 1 (T1)", "Ciclismo", "Transición 2 (T2)", "Carrera a pie"],
        "Acuatlón": ["Natación", "Transición 1 (T1)", "Carrera a pie"]
        // Add other formats as needed
    };

    // Fetch Race Formats on page load
    fetch('/api/race-formats')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(formats => {
            formats.forEach(format => {
                const option = document.createElement('option');
                option.value = format.id;
                option.textContent = format.name;
                raceFormatSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error fetching race formats:', error);
            errorMessagesDiv.textContent = 'Error al cargar formatos de carrera. Intente recargar la página.';
        });

    // Handle Race Format change to display segments
    raceFormatSelect.addEventListener('change', function() {
        const selectedFormatName = this.options[this.selectedIndex].text;
        raceSegmentsContainer.innerHTML = ''; // Clear previous segments

        if (selectedFormatName && raceFormatToSegments[selectedFormatName]) {
            const segments = raceFormatToSegments[selectedFormatName];
            segments.forEach((segmentName, index) => {
                const segmentId = segmentNameToId[segmentName];
                if (segmentId === undefined) {
                    console.warn(`Segment ID not found for: ${segmentName}. Skipping.`);
                    return;
                }

                const segmentEntry = document.createElement('div');
                segmentEntry.classList.add('segment-entry');

                const nameLabel = document.createElement('label');
                nameLabel.classList.add('segment-name');
                nameLabel.textContent = segmentName;
                segmentEntry.appendChild(nameLabel);

                const distanceInput = document.createElement('input');
                distanceInput.type = 'number';
                distanceInput.classList.add('segmentDistance');
                distanceInput.placeholder = 'Distancia en km';
                distanceInput.min = "0"; // Allow 0 for transitions
                distanceInput.step = "0.01";
                distanceInput.dataset.segmentId = segmentId; // Store segment ID
                distanceInput.dataset.segmentName = segmentName; // Store segment name for validation messages

                // Transitions often have 0 distance, others usually required
                if (segmentName.toLowerCase().includes("transición")) {
                    distanceInput.value = "0";
                } else {
                    distanceInput.required = true;
                }

                segmentEntry.appendChild(distanceInput);
                raceSegmentsContainer.appendChild(segmentEntry);
            });
        }
    });

    // Handle Form Submission
    createRaceForm.addEventListener('submit', function(event) {
        event.preventDefault();
        errorMessagesDiv.textContent = ''; // Clear previous errors

        const title = document.getElementById('raceTitle').value.trim();
        const description = document.getElementById('raceDescription').value.trim();
        const raceFormatId = parseInt(raceFormatSelect.value);
        const eventDate = document.getElementById('eventDate').value;
        const quinielaCloseDate = document.getElementById('quinielaCloseDate').value; // Added
        const location = document.getElementById('raceLocation').value.trim();
        const promoImageUrl = document.getElementById('promoImageUrl').value.trim();
        const genderCategory = document.getElementById('genderCategory').value;

        // Client-side validation
        let errors = [];
        if (!title) errors.push("Título de la carrera es requerido.");
        if (!raceFormatId) errors.push("Formato de carrera es requerido.");
        if (!eventDate) errors.push("Fecha del evento es requerida.");
        if (!genderCategory) errors.push("Género de la categoría es requerido.");

        const segmentDistances = document.querySelectorAll('.segmentDistance');
        let segmentsPayload = [];
        segmentDistances.forEach(input => {
            const segmentId = parseInt(input.dataset.segmentId);
            const segmentName = input.dataset.segmentName;
            const distance = parseFloat(input.value);

            if (isNaN(distance) || distance < 0) {
                errors.push(`Distancia para ${segmentName} debe ser un número no negativo.`);
            } else if (distance <= 0 && !segmentName.toLowerCase().includes("transición")) {
                 errors.push(`Distancia para ${segmentName} debe ser un número positivo.`);
            }
            segmentsPayload.push({ segment_id: segmentId, distance_km: distance });
        });

        if (segmentsPayload.length === 0 && raceFormatToSegments[raceFormatSelect.options[raceFormatSelect.selectedIndex].text]?.length > 0) {
            errors.push("Debe definir al menos un segmento para el formato de carrera seleccionado.");
        }


        if (errors.length > 0) {
            errorMessagesDiv.innerHTML = errors.map(e => `<div>${e}</div>`).join('');
            return;
        }

        const raceData = {
            title,
            description: description || null,
            race_format_id: raceFormatId,
            event_date: eventDate,
            quiniela_close_date: quinielaCloseDate ? quinielaCloseDate : null, // Added: send as null if empty
            location: location || null,
            promo_image_url: promoImageUrl || null,
            gender_category: genderCategory,
            segments: segmentsPayload
        };

        fetch('/api/races', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Include CSRF token if necessary and available
            },
            body: JSON.stringify(raceData)
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(result => {
            if (result.status === 201) {
                alert('¡Carrera creada exitosamente!');
                window.location.href = '/Hello-world'; // Redirect to main page
            } else {
                errorMessagesDiv.textContent = result.body.message || 'Error al crear la carrera.';
                if (result.body.errors) { // For more detailed errors if API provides them
                    errorMessagesDiv.innerHTML += "<ul>" + Object.entries(result.body.errors).map(([field, messages]) => `<li>${field}: ${messages.join(', ')}</li>`).join('') + "</ul>";
                }
            }
        })
        .catch(error => {
            console.error('Error submitting race:', error);
            errorMessagesDiv.textContent = 'Error de red o el servidor no responde. Intente más tarde.';
        });
    });
});
