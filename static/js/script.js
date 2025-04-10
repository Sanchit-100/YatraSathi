document.addEventListener('DOMContentLoaded', function() {
    // Fetch routes when the page loads
    fetch('/api/routes')
        .then(response => response.json())
        .then(transports => {
            displayTransports(transports);
        })
        .catch(error => {
            console.error('Error fetching data:', error);
            document.getElementById('routes-container').innerHTML = 
                '<p>Error loading data. Please try again later.</p>';
        });
});


function displayTransports(transports) {
    const container = document.getElementById('routes-container');
    
    if (transports.length === 0) {
        container.innerHTML = '<p>No transport options available.</p>';
        return;
    }
    
    let html = '';
    
    transports.forEach(transport => {
        html += `
            <div class="route-card">
                <span class="route-type ${transport.type}">${transport.type}</span>
                <h3>${transport.name}</h3>
                <div class="route-details">
                    <div>
                        <strong>Operator:</strong> ${transport.operator}
                    </div>
                    <div>
                        <strong>Status:</strong> ${transport.status}
                    </div>
                </div>
                <div class="route-distance">Total Seats: ${transport.total_seats}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}