/**
 * Finance Strategy Engine - Frontend Logic
 */

function initDtiChart(obligations, freeCashflow) {
    const ctx = document.getElementById('dtiChart').getContext('2d');
    
    // Check if chart already exists to prevent canvas errors
    if (window.dtiChartInstance) {
        window.dtiChartInstance.destroy();
    }

    window.dtiChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Obligations (Bills + Min Debt)', 'Free Cashflow'],
            datasets: [{
                data: [obligations, freeCashflow],
                backgroundColor: [
                    '#f43f5e', // Danger/Red
                    '#10b981'  // Success/Green
                ],
                hoverOffset: 15,
                borderWidth: 0,
                borderRadius: 5
            }]
        },
        options: {
            cutout: '75%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94a3b8',
                        padding: 20,
                        font: { size: 12, weight: '500' }
                    }
                }
            }
        }
    });
}