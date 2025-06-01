document.addEventListener('DOMContentLoaded', () => {
    const helloButton = document.getElementById('helloButton');
    const messageArea = document.getElementById('messageArea');

    helloButton.addEventListener('click', () => {
        fetch('https://triathlon-fantasy.duckdns.org/api/hello')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                messageArea.textContent = data.message;
            })
            .catch(error => {
                console.error('Fetch error:', error);
                messageArea.textContent = 'Error fetching message from backend.';
            });
    });
});
