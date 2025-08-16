// Use current host for API calls (works for any domain/IP)
const API_BASE = `${window.location.protocol}//${window.location.host}/api`;
let currentPortfolio = null;

// Authentication check
async function checkAuthentication() {
    try {
        const response = await fetch(`${API_BASE}/check-auth`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (!data.authenticated) {
            // Redirect to login
            window.location.href = '/login.html';
            return false;
        }
        
        // Show user info
        if (data.username) {
            showUserInfo(data.username);
        }
        
        return true;
    } catch (error) {
        console.error('Authentication check failed:', error);
        window.location.href = '/login.html';
        return false;
    }
}

function showUserInfo(username) {
    // Add user info to header
    const header = document.querySelector('header');
    if (header && !document.getElementById('userInfo')) {
        const userInfo = document.createElement('div');
        userInfo.id = 'userInfo';
        userInfo.innerHTML = `
            <div style="display: flex; align-items: center; gap: 15px; margin-top: 10px;">
                <span style="color: #4cc9f0;">Logged in as: ${username}</span>
                <button onclick="logout()" style="
                    background: rgba(255, 107, 107, 0.2);
                    border: 1px solid #ff6b6b;
                    color: #ff6b6b;
                    padding: 5px 10px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 12px;
                ">Logout</button>
            </div>
        `;
        header.appendChild(userInfo);
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE}/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = '/login.html';
    } catch (error) {
        console.error('Logout failed:', error);
        window.location.href = '/login.html';
    }
}

// Enhanced API call wrapper with authentication
async function authenticatedFetch(url, options = {}) {
    const defaultOptions = {
        credentials: 'include',
        headers: {
            // Only set Content-Type for non-FormData requests
            ...(options.body instanceof FormData ? {} : {'Content-Type': 'application/json'}),
            ...options.headers
        },
        ...options
    };
    
    try {
        const response = await fetch(url, defaultOptions);
        
        if (response.status === 401) {
            // Unauthorized - redirect to login
            window.location.href = '/login.html';
            return null;
        }
        
        if (response.status === 429) {
            alert('Rate limit exceeded. Please wait a moment before trying again.');
            return null;
        }
        
        return response;
    } catch (error) {
        console.error('Network error:', error);
        throw error;
    }
}

// Test API connection with authentication
async function testConnection() {
    console.log('Testing API connection...');
    try {
        const response = await authenticatedFetch(`${API_BASE}/portfolio`);
        if (response && response.ok) {
            console.log('✓ API connection successful');
            const data = await response.json();
            console.log('Portfolio data:', data);
        } else if (response) {
            console.error('✗ API returned error:', response.status);
        }
    } catch (error) {
        console.error('✗ API connection failed:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', async function() {
    console.log('App.js loaded successfully');
    
    // Check authentication first
    const isAuthenticated = await checkAuthentication();
    if (!isAuthenticated) {
        return; // Will redirect to login
    }
    
    testConnection();
    loadPortfolio();
    
    // File upload handler
    const fileInput = document.getElementById('csvFile');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            console.log('File selected:', e.target.files[0]);
            uploadPortfolio(e.target.files[0]);
        });
    } else {
        console.error('File input not found!');
    }
    
    // Add holding form handler
    const holdingForm = document.getElementById('holdingForm');
    if (holdingForm) {
        holdingForm.addEventListener('submit', function(e) {
            e.preventDefault();
            addNewHolding();
        });
    }
});

async function loadPortfolio() {
    console.log('STEP 1: Loading portfolio positions...');
    try {
        const response = await authenticatedFetch(`${API_BASE}/portfolio`);
        if (response && response.ok) {
            const data = await response.json();
            console.log('Portfolio positions loaded:', data);
            currentPortfolio = data;
            
            // Update workflow based on portfolio state
            updateWorkflowSteps(data);
            updateUI();
        }
    } catch (error) {
        console.error('Error loading portfolio:', error);
        // Initialize with empty data
        currentPortfolio = {
            holdings: [],
            summary: {
                total_cost_basis: 0,
                total_current_value: null,
                total_return: null,
                return_percentage: null,
                holdings_count: 0
            }
        };
        updateUI();
    }
}

function updateWorkflowSteps(portfolioData) {
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');
    const step4 = document.getElementById('step4');
    const additionalActions = document.getElementById('additionalActions');
    
    if (!portfolioData.holdings || portfolioData.holdings.length === 0) {
        // No portfolio loaded - show step 1
        step1.classList.add('active');
        step2.style.display = 'none';
        step3.style.display = 'none';
        step4.style.display = 'none';
        additionalActions.style.display = 'none';
    } else if (portfolioData.workflow_step === 'positions_loaded') {
        // Step 1 complete - show step 2
        step1.classList.add('completed');
        step1.classList.remove('active');
        step2.style.display = 'block';
        step2.classList.add('active');
        step3.style.display = 'none';
        step4.style.display = 'none';
        additionalActions.style.display = 'block';
    } else if (portfolioData.workflow_step === 'prices_fetched') {
        // Step 2 complete - show step 3 and 4
        step1.classList.add('completed');
        step2.classList.add('completed');
        step2.classList.remove('active');
        step3.style.display = 'block';
        step4.style.display = 'block';
        step4.classList.add('active');
        additionalActions.style.display = 'block';
        
        // Show step 3 only if there are failed prices
        if (portfolioData.summary?.failed_prices > 0) {
            step3.classList.add('active');
        } else {
            step3.classList.add('completed');
        }
    }
}

async function fetchLivePrices() {
    console.log('STEP 2: Fetching live prices...');
    const btn = document.getElementById('fetchPricesBtn');
    const originalText = btn.textContent;
    
    btn.textContent = 'Fetching prices... (this may take a moment)';
    btn.disabled = true;
    
    try {
        const response = await authenticatedFetch(`${API_BASE}/fetch-live-prices`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response && response.ok) {
            const data = await response.json();
            console.log('Live prices fetched:', data);
            
            // Update portfolio data
            currentPortfolio = data;
            updateWorkflowSteps(data);
            updateUI();
            
            // Show results
            const results = data.price_fetch_results;
            if (results) {
                alert(`Live prices fetched!\n\nSuccess: ${results.successful} tickers\nFailed: ${results.failed} tickers\nSuccess rate: ${results.success_rate}\n\nNext: ${data.next_action}`);
            } else {
                alert('Live prices fetched successfully!');
            }
        } else {
            const errorText = await response.text();
            alert(`Failed to fetch live prices: ${errorText}`);
        }
    } catch (error) {
        console.error('Error fetching live prices:', error);
        alert('Error fetching live prices: ' + error.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function refreshPortfolioWithPrices() {
    // Refresh portfolio by fetching live prices (including manual overrides) without showing alerts
    try {
        const response = await authenticatedFetch(`${API_BASE}/fetch-live-prices`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response && response.ok) {
            const data = await response.json();
            console.log('Portfolio refreshed with updated prices');
            
            // Update portfolio data and UI
            currentPortfolio = data;
            updateWorkflowSteps(data);
            updateUI();
        } else {
            console.error('Failed to refresh portfolio prices');
            // Fallback to basic portfolio load
            await loadPortfolio();
        }
    } catch (error) {
        console.error('Error refreshing portfolio:', error);
        // Fallback to basic portfolio load
        await loadPortfolio();
    }
}

async function runCompleteAnalysis() {
    console.log('STEP 4: Running complete analysis...');
    const btn = document.getElementById('analyzeBtn');
    const originalText = btn.textContent;
    
    btn.textContent = 'Running analysis...';
    btn.disabled = true;
    
    try {
        // Run both ML and statistical analysis
        await generateMLRecommendations();
        // Additional analysis can be added here
        
        alert('Complete portfolio analysis finished! Check the recommendations and charts below.');
    } catch (error) {
        console.error('Error running analysis:', error);
        alert('Error running analysis: ' + error.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function uploadPortfolio(file) {
    console.log('Uploading file:', file.name);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        console.log('Making upload request to:', `${API_BASE}/upload`);
        const response = await authenticatedFetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData,
            // Don't set Content-Type header, let browser set it with boundary for multipart
        });
        
        if (response && response.ok) {
            const data = await response.json();
            // Handle new simplified workflow response
            if (data.workflow_complete && data.steps_completed) {
                const summary = data.summary;
                
                // Show success message
                alert(`✅ Step 1 Complete: Transactions Uploaded!
                
📊 Summary:
• ${summary.transactions_processed} transactions processed
• ${summary.unique_tickers} unique tickers found
• Cost basis: $${summary.total_cost_basis?.toLocaleString() || 'N/A'}

🚀 Next: Click "Fetch Live Market Prices" to continue`);
                
                // Update current portfolio with the returned data
                if (data.portfolio_data) {
                    currentPortfolio = data.portfolio_data;
                    updateWorkflowSteps(currentPortfolio);
                    updateUI();
                } else {
                    // Fallback: reload portfolio from API
                    await loadPortfolio();
                }
            } else {
                // Fallback for old format
                alert('Portfolio uploaded successfully!');
                await loadPortfolio();
            }
        } else if (response) {
            // Check if response is HTML instead of JSON
            const contentType = response.headers.get('content-type');
            console.log('Response content-type:', contentType);
            console.log('Response status:', response.status);
            console.log('Response statusText:', response.statusText);
            console.log('Response URL:', response.url);
            
            // Read the response body only once
            let responseText;
            try {
                responseText = await response.text();
            } catch (readError) {
                alert('Error reading server response: ' + readError.message);
                return;
            }
            
            if (contentType && contentType.includes('text/html')) {
                console.log('HTML response (first 500 chars):', responseText.substring(0, 500));
                
                // Check if it's a Flask error page
                if (responseText.includes('Werkzeug') || responseText.includes('Internal Server Error')) {
                    alert('Server Error: There was an internal server error. Check the server console for details.');
                } else if (responseText.includes('404') || responseText.includes('Not Found')) {
                    alert('Upload Error: Upload endpoint not found. Check server configuration.');
                } else {
                    alert('Server returned HTML instead of JSON. This usually means a server error occurred. Check server logs.');
                }
            } else {
                try {
                    const error = JSON.parse(responseText);
                    console.log('JSON error response:', error);
                    alert('Error uploading portfolio: ' + (error.error || 'Unknown error'));
                } catch (jsonError) {
                    console.log('Non-JSON response text:', responseText);
                    alert('Server error (status ' + response.status + '): ' + responseText.substring(0, 100));
                }
            }
        }
    } catch (error) {
        console.error('Upload error:', error);
        alert('Error uploading portfolio: ' + error.message);
    }
}

async function fetchMarketData() {
    console.log('Fetching market data...');
    const btn = document.getElementById('marketDataBtn');
    btn.textContent = 'Fetching Live Prices...';
    btn.disabled = true;
    
    try {
        const response = await authenticatedFetch(`${API_BASE}/market-data`);
        if (response && response.ok) {
            const data = await response.json();
            // Market data updated successfully
            alert(`Market data updated! Updated ${data.updated_holdings} holdings with live prices.`);
            // Reload portfolio to show updated prices and returns
            await loadPortfolio();
        }
    } catch (error) {
        console.error('Market data error:', error);
        alert('Error fetching market data: ' + error.message);
    } finally {
        btn.textContent = 'Fetch Market Data';
        btn.disabled = false;
    }
}

async function syncPricesBackground() {
    console.log('Starting background price sync...');
    alert('🔧 DEBUG: syncPricesBackground function called successfully!');
    
    const btn = document.getElementById('syncPricesBtn');
    
    if (!btn) {
        alert('Sync Prices button not found! Please refresh the page.');
        return;
    }
    
    console.log('Sync button found, starting sync...');
    btn.textContent = 'Syncing Prices... (This may take several minutes)';
    btn.disabled = true;
    
    // Show progress message
    const progressMsg = document.createElement('div');
    progressMsg.id = 'sync-progress';
    progressMsg.style.cssText = 'background: #4caf50; color: white; padding: 10px; margin: 10px 0; border-radius: 5px; text-align: center;';
    progressMsg.textContent = '🔄 Fetching prices with rate limiting (5 seconds between batches)...';
    btn.parentNode.insertBefore(progressMsg, btn.nextSibling);
    
    try {
        console.log('Making sync-prices request...');
        const response = await authenticatedFetch(`${API_BASE}/sync-prices`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({}) // Empty body - will use portfolio tickers
        });
        
        console.log('Sync-prices response received:', response?.status);
        
        if (response && response.ok) {
            const data = await response.json();
            console.log('Sync-prices data:', data);
            
            // Price sync completed
            const results = data.results;
            if (results) {
                alert(`Price sync completed!\n\nSuccess: ${results.successful}/${results.total_tickers} tickers\nSuccess rate: ${results.success_rate}\n\nNext action: ${data.next_action}`);
            } else {
                alert('Price sync completed successfully!');
            }
            
            // Reload portfolio to show updated prices
            await loadPortfolio();
        } else if (response) {
            const errorText = await response.text();
            console.error('Sync-prices error response:', errorText);
            alert(`Sync-prices failed (${response.status}): ${errorText.substring(0, 200)}`);
        } else {
            alert('No response received from sync-prices endpoint');
        }
    } catch (error) {
        console.error('Price sync error:', error);
        alert('Error syncing prices: ' + error.message);
    } finally {
        btn.textContent = 'Sync Prices';
        btn.disabled = false;
        
        // Remove progress message
        const progressMsg = document.getElementById('sync-progress');
        if (progressMsg) {
            progressMsg.remove();
        }
    }
}


async function exportData() {
    console.log('Exporting data...');
    try {
        const response = await axios.get(`${API_BASE}/export?format=csv`);
        console.log('Export response:', response);
        downloadFile(response.data, 'portfolio_export.csv', 'text/csv');
    } catch (error) {
        console.error('Export error:', error);
        alert('Error exporting data: ' + (error.response?.data?.error || error.message));
    }
}

function updateUI() {
    console.log('Updating UI with portfolio:', currentPortfolio);
    if (!currentPortfolio) return;
    
    // Update summary (handle null values for step 1)
    const summary = currentPortfolio.summary;
    
    // Total Value - use current_value if available, otherwise show cost basis
    const totalValue = summary.total_current_value !== null && summary.total_current_value !== undefined 
        ? summary.total_current_value 
        : (summary.total_cost_basis || 0);
    document.getElementById('totalValue').textContent = `$${totalValue.toLocaleString()} USD`;
    
    // Total Return - only show if we have real data
    if (summary.total_return !== null && summary.total_return !== undefined) {
        document.getElementById('totalReturn').textContent = `$${summary.total_return.toLocaleString()} USD`;
    } else {
        document.getElementById('totalReturn').textContent = 'Fetch prices first';
    }
    
    // Return Percentage - only show if we have real data  
    if (summary.return_percentage !== null && summary.return_percentage !== undefined) {
        document.getElementById('returnPct').textContent = `${summary.return_percentage.toFixed(2)}%`;
    } else {
        document.getElementById('returnPct').textContent = 'Fetch prices first';
    }
    
    document.getElementById('holdingsCount').textContent = summary.holdings_count || 0;
    
    // Show currency conversion info if available
    if (currentPortfolio.currency_info && 
        currentPortfolio.currency_info.conversions && 
        Object.keys(currentPortfolio.currency_info.conversions).length > 0) {
        updateCurrencyInfo(currentPortfolio.currency_info);
    }
    
    // Update last update time
    document.getElementById('lastUpdate').textContent = new Date().toLocaleString();
    
    // Update charts
    updateCharts();
    
    // Update holdings management section
    updateHoldingsManagement();
}


function updateCharts() {
    console.log('Updating charts...');
    if (!currentPortfolio || !currentPortfolio.holdings) {
        console.log('No data for charts');
        return;
    }
    
    // Destroy existing charts if they exist
    if (window.allocationChart && typeof window.allocationChart.destroy === 'function') {
        window.allocationChart.destroy();
    }
    if (window.performanceChart && typeof window.performanceChart.destroy === 'function') {
        window.performanceChart.destroy();
    }
    
   // Allocation Chart - Filter out zero/negative value holdings
    const holdings = currentPortfolio.holdings.filter(h => h.current_value > 0);
    
    if (holdings.length > 0) {
        const allocationCtx = document.getElementById('allocationChart');
        if (allocationCtx) {
            window.allocationChart = new Chart(allocationCtx.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: holdings.map(h => h.ticker),
                    datasets: [{
                        data: holdings.map(h => h.current_value),
                        backgroundColor: generateColors(holdings.length)
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                color: '#e0e0e0'
                            }
                        }
                    }
                }
            });
        }
    }
    
    // Performance Chart - Only show holdings with value
    const validHoldingsForChart = currentPortfolio.holdings.filter(h => h.current_value > 0);
    if (validHoldingsForChart.length > 0) {
        const performanceCtx = document.getElementById('performanceChart');
        if (performanceCtx) {
            const returns = validHoldingsForChart.map(h => {
                return h.cost_basis > 0 ? 
                    ((h.current_value - h.cost_basis) / h.cost_basis * 100) : 0;
            });
            
            window.performanceChart = new Chart(performanceCtx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: validHoldingsForChart.map(h => h.ticker),
                    datasets: [{
                        label: 'Return %',
                        data: returns,
                        backgroundColor: returns.map(r => r >= 0 ? 'rgba(74, 222, 128, 0.8)' : 'rgba(248, 113, 113, 0.8)'),
                        borderColor: returns.map(r => r >= 0 ? '#4ade80' : '#f87171'),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: '#e0e0e0',
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#e0e0e0'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    }
}
function generateColors(count) {
    const colors = [];
    for (let i = 0; i < count; i++) {
        const hue = (i * 360 / count) % 360;
        colors.push(`hsl(${hue}, 70%, 50%)`);
    }
    return colors;
}

// Update holdings management section
function updateHoldingsManagement() {
    if (!currentPortfolio || !currentPortfolio.holdings || currentPortfolio.holdings.length === 0) {
        document.getElementById('holdingsManagement').style.display = 'none';
        return;
    }
    
    // Show ALL holdings - including those that need manual prices
    // Only filter out holdings with zero quantity (fully sold positions)
    const validHoldings = currentPortfolio.holdings.filter(h => h.quantity > 0);
    
    if (validHoldings.length === 0) {
        document.getElementById('holdingsManagement').style.display = 'none';
        return;
    }
    
    const holdingsManagement = document.getElementById('holdingsManagement');
    const holdingsList = document.getElementById('holdingsList');
    
    holdingsManagement.style.display = 'block';
    
    // Create holdings table
    const holdingsHTML = `
        <table class="holdings-table">
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Exchange</th>
                    <th>Currency</th>
                    <th>Quantity</th>
                    <th>Avg Cost</th>
                    <th>Cost Basis</th>
                    <th>Current Price</th>
                    <th>Current Value</th>
                    <th>Return</th>
                    <th>Return %</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${validHoldings.map(holding => {
                    const returnAmount = holding.total_return;
                    const returnPct = holding.return_percentage;
                    
                    // Handle None values for missing price data
                    const currentValueDisplay = holding.current_value !== null ? 
                        formatCurrency(holding.current_value, holding.currency) : 
                        '<span class="no-data">❌ No Price Data</span>';
                    
                    const returnDisplay = returnAmount !== null ? 
                        formatCurrency(returnAmount, holding.currency) : 
                        '<span class="no-data">❌ Set Price First</span>';
                    
                    const returnPctDisplay = returnPct !== null ? 
                        `${returnPct.toFixed(1)}%` : 
                        '<span class="no-data">❌ Set Price First</span>';
                    
                    const returnClass = returnAmount !== null ? 
                        (returnAmount >= 0 ? 'positive' : 'negative') : 'no-data';
                    
                    return `
                        <tr>
                            <td class="ticker">${holding.ticker}</td>
                            <td>${holding.exchange || 'N/A'}</td>
                            <td><span class="currency-badge">${holding.currency || 'USD'}</span></td>
                            <td>${holding.quantity.toFixed(4)}</td>
                            <td>${formatCurrency(holding.avg_cost, holding.currency)}</td>
                            <td>${formatCurrency(holding.cost_basis, holding.currency)}</td>
                            <td>${formatPriceWithStaleness(holding)}</td>
                            <td>${currentValueDisplay}</td>
                            <td class="${returnClass}">
                                ${returnDisplay}
                            </td>
                            <td class="${returnClass}">
                                ${returnPctDisplay}
                            </td>
                            <td>
                                <div class="holding-actions">
                                    <button onclick="showManualPriceDialog('${holding.ticker}', ${holding.current_price || holding.avg_cost})" 
                                            class="manual-price-btn" 
                                            title="Set manual price for ${holding.ticker}">
                                        💰
                                    </button>
                                    <button onclick="deleteHolding('${holding.ticker}')" 
                                            class="delete-btn" 
                                            title="Delete ${holding.ticker}">
                                        ✕
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
    
    holdingsList.innerHTML = holdingsHTML;
}

function downloadFile(content, filename, contentType) {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// Currency formatting function
function formatCurrency(amount, currency) {
    if (typeof amount !== 'number' || isNaN(amount)) {
        return 'N/A';
    }
    
    const currencySymbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CAD': 'C$',
        'AUD': 'A$',
        'CHF': 'CHF ',
        'CNY': '¥',
        'INR': '₹',
        'KRW': '₩',
        'BRL': 'R$',
        'RUB': '₽',
        'SGD': 'S$',
        'HKD': 'HK$',
        'SEK': 'kr',
        'NOK': 'kr',
        'DKK': 'kr',
        'PLN': 'zł',
        'CZK': 'Kč',
        'HUF': 'Ft'
    };
    
    const currencyCode = (currency || 'USD').toUpperCase();
    const symbol = currencySymbols[currencyCode] || currencyCode + ' ';
    
    // Format based on currency (some currencies don't use decimals)
    if (['JPY', 'KRW', 'HUF'].includes(currencyCode)) {
        return `${symbol}${amount.toLocaleString('en-US', {maximumFractionDigits: 0})}`;
    } else {
        return `${symbol}${amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    }
}

function formatPriceWithStaleness(holding) {
    // STRICT: No price data = show manual price required
    if (holding.needs_manual_price || holding.current_price === null || holding.current_price === undefined) {
        return `<div class="price-display error-price">
            <div class="price">❌ No Price Data</div>
            <div class="staleness error">Click 💰 to set manual price</div>
        </div>`;
    }
    
    const price = formatCurrency(holding.current_price, holding.currency);
    const isManual = holding.is_manual;
    const staleness = holding.staleness_level;
    const ageStr = holding.data_age_str;
    
    if (isManual) {
        return `<div class="price-display manual-price">
            <div class="price">${price}</div>
            <div class="staleness manual">💰 Manual (${ageStr})</div>
        </div>`;
    }
    
    if (!staleness || staleness === 'live' || staleness === 'fresh') {
        return `<div class="price-display fresh-price">
            <div class="price">${price}</div>
            <div class="staleness fresh">✅ Live</div>
        </div>`;
    }
    
    const stalenessClass = staleness === 'recent' ? 'recent' : 
                          staleness === 'stale' ? 'stale' : 'very-stale';
    const stalenessIcon = staleness === 'recent' ? '🟡' : 
                         staleness === 'stale' ? '🟠' : '🔴';
    
    return `<div class="price-display ${stalenessClass}-price">
        <div class="price">${price}</div>
        <div class="staleness ${stalenessClass}">${stalenessIcon} ${ageStr}</div>
    </div>`;
}

function showManualPriceDialog(ticker, currentPrice) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <h3>Set Manual Price for ${ticker}</h3>
            <div class="form-group">
                <label>Current Price: ${formatCurrency(currentPrice)}</label>
            </div>
            <div class="form-group">
                <label for="manualPrice">New Price:</label>
                <input type="number" id="manualPrice" step="0.01" min="0.01" placeholder="Enter price..." value="${currentPrice.toFixed(2)}">
            </div>
            <div class="form-group">
                <label for="priceNotes">Notes (optional):</label>
                <input type="text" id="priceNotes" placeholder="e.g., From broker, recent news...">
            </div>
            <div class="form-group">
                <label for="expiresHours">Expires after (hours, optional):</label>
                <select id="expiresHours">
                    <option value="">Never expires</option>
                    <option value="1">1 hour</option>
                    <option value="6">6 hours</option>
                    <option value="24">24 hours</option>
                    <option value="168">1 week</option>
                </select>
            </div>
            <div class="modal-buttons">
                <button onclick="setManualPrice('${ticker}')" class="btn primary">Set Price</button>
                <button onclick="removeManualPrice('${ticker}')" class="btn secondary">Remove Manual</button>
                <button onclick="closeModal()" class="btn">Cancel</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('manualPrice').focus();
}

async function setManualPrice(ticker) {
    try {
        const price = parseFloat(document.getElementById('manualPrice').value);
        const notes = document.getElementById('priceNotes').value;
        const expiresHours = document.getElementById('expiresHours').value;
        
        if (!price || price <= 0) {
            alert('Please enter a valid price');
            return;
        }
        
        const data = {
            ticker: ticker,
            price: price,
            notes: notes || null,
            expires_hours: expiresHours ? parseInt(expiresHours) : null
        };
        
        const response = await authenticatedFetch(`${API_BASE}/manual-price`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (response && response.ok) {
            const result = await response.json();
            alert(`Manual price set: ${ticker} = $${price.toFixed(2)}`);
            closeModal();
            // Reload portfolio with updated prices and recalculated returns
            await refreshPortfolioWithPrices();
        } else if (response) {
            // Handle error response
            try {
                const error = await response.json();
                alert('Error setting manual price: ' + (error.error || 'Unknown error'));
            } catch (parseError) {
                // If JSON parsing fails, show the status
                alert(`Error setting manual price: HTTP ${response.status} - ${response.statusText}`);
            }
        } else {
            // Response is null - likely authentication issue
            alert('Authentication error: Please refresh the page and login again');
            window.location.href = '/login.html';
        }
    } catch (error) {
        alert('Error setting manual price: ' + error.message);
    }
}

async function removeManualPrice(ticker) {
    try {
        const response = await authenticatedFetch(`${API_BASE}/manual-price/${ticker}`, {
            method: 'DELETE'
        });
        
        if (response && response.ok) {
            alert(`Manual price removed for ${ticker}`);
            closeModal();
            await refreshPortfolioWithPrices(); // Refresh to show updated price
        } else if (response) {
            try {
                const error = await response.json();
                alert('Error removing manual price: ' + (error.error || 'Unknown error'));
            } catch (parseError) {
                alert(`Error removing manual price: HTTP ${response.status} - ${response.statusText}`);
            }
        } else {
            alert('Authentication error: Please refresh the page and login again');
            window.location.href = '/login.html';
        }
    } catch (error) {
        alert('Error removing manual price: ' + error.message);
    }
}

function closeModal() {
    const modal = document.querySelector('.modal-overlay');
    if (modal) {
        modal.remove();
    }
}

// Statistical Analysis Functions
function showStatisticalAnalysisButton(ready) {
    let analysisBtn = document.getElementById('statistical-analysis-btn');
    
    if (!analysisBtn) {
        // Create the button
        analysisBtn = document.createElement('button');
        analysisBtn.id = 'statistical-analysis-btn';
        analysisBtn.className = 'btn-statistical';
        analysisBtn.onclick = () => runStatisticalAnalysis();
        
        // Add to controls section
        const controls = document.querySelector('.controls');
        if (controls) {
            controls.appendChild(analysisBtn);
        }
    }
    
    if (ready) {
        analysisBtn.textContent = '📈 Statistical Analysis';
        analysisBtn.disabled = false;
        analysisBtn.title = 'Run comprehensive portfolio analysis';
    } else {
        analysisBtn.textContent = '📈 Statistical Analysis (Need 3+ holdings with prices)';
        analysisBtn.disabled = true;
        analysisBtn.title = 'Need at least 3 holdings with valid prices for analysis';
    }
}

async function runStatisticalAnalysis() {
    const btn = document.getElementById('statistical-analysis-btn');
    if (!btn) return;
    
    btn.textContent = 'Analyzing Portfolio...';
    btn.disabled = true;
    
    try {
        const response = await authenticatedFetch(`${API_BASE}/statistical-analysis`);
        
        if (response && response.ok) {
            const data = await response.json();
            // Statistical analysis completed
            displayStatisticalAnalysis(data.analysis);
        } else {
            const error = await response.json();
            alert('Statistical analysis error: ' + error.error);
        }
    } catch (error) {
        console.error('Statistical analysis error:', error);
        alert('Error running statistical analysis: ' + error.message);
    } finally {
        btn.textContent = '📈 Statistical Analysis';
        btn.disabled = false;
    }
}

function displayStatisticalAnalysis(analysis) {
    // Remove existing analysis
    const existingAnalysis = document.getElementById('statistical-analysis-results');
    if (existingAnalysis) {
        existingAnalysis.remove();
    }
    
    // Create analysis display
    const analysisDiv = document.createElement('div');
    analysisDiv.id = 'statistical-analysis-results';
    analysisDiv.className = 'statistical-analysis';
    
    const overview = analysis.portfolio_overview;
    const returns = analysis.return_distribution;
    const risk = analysis.risk_analysis;
    const concentration = analysis.concentration_analysis;
    const performance = analysis.performance_metrics;
    const recommendations = analysis.recommendations || [];
    
    analysisDiv.innerHTML = `
        <div class="analysis-container">
            <h2>📊 Statistical Portfolio Analysis</h2>
            <p class="analysis-timestamp">Analysis completed: ${new Date(analysis.analysis_timestamp).toLocaleString()}</p>
            <p class="analysis-coverage">Coverage: ${analysis.analysis_coverage} of portfolio analyzed</p>
            
            <div class="analysis-grid">
                <div class="analysis-card">
                    <h3>💰 Portfolio Overview</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <label>Portfolio Return:</label>
                            <span class="${overview.portfolio_return_percentage >= 0 ? 'positive' : 'negative'}">
                                ${overview.portfolio_return_percentage.toFixed(2)}%
                            </span>
                        </div>
                        <div class="metric">
                            <label>Total Value:</label>
                            <span>$${overview.total_current_value.toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <label>Total Return:</label>
                            <span class="${overview.total_return_amount >= 0 ? 'positive' : 'negative'}">
                                $${overview.total_return_amount.toLocaleString()}
                            </span>
                        </div>
                        <div class="metric">
                            <label>Positions:</label>
                            <span>${overview.number_of_positions}</span>
                        </div>
                    </div>
                </div>
                
                <div class="analysis-card">
                    <h3>📈 Return Distribution</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <label>Mean Return:</label>
                            <span>${returns.mean_return.toFixed(2)}%</span>
                        </div>
                        <div class="metric">
                            <label>Win Rate:</label>
                            <span>${returns.win_rate}%</span>
                        </div>
                        <div class="metric">
                            <label>Best Performer:</label>
                            <span class="positive">${returns.max_return.toFixed(2)}%</span>
                        </div>
                        <div class="metric">
                            <label>Worst Performer:</label>
                            <span class="negative">${returns.min_return.toFixed(2)}%</span>
                        </div>
                    </div>
                </div>
                
                <div class="analysis-card">
                    <h3>⚠️ Risk Analysis</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <label>Risk Level:</label>
                            <span class="risk-${risk.risk_level.toLowerCase()}">${risk.risk_level}</span>
                        </div>
                        <div class="metric">
                            <label>Volatility:</label>
                            <span>${risk.portfolio_volatility.toFixed(2)}%</span>
                        </div>
                        <div class="metric">
                            <label>Value at Risk (5%):</label>
                            <span class="negative">${risk.value_at_risk_5pct.toFixed(2)}%</span>
                        </div>
                        <div class="metric">
                            <label>Diversification Score:</label>
                            <span>${risk.diversification_score.toFixed(1)}/10</span>
                        </div>
                    </div>
                    <p class="risk-interpretation">${risk.volatility_interpretation}</p>
                </div>
                
                <div class="analysis-card">
                    <h3>🎯 Concentration</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <label>Concentration Level:</label>
                            <span>${concentration.concentration_level}</span>
                        </div>
                        <div class="metric">
                            <label>Top Position:</label>
                            <span>${concentration.top_position_weight.toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <label>Top 3 Holdings:</label>
                            <span>${concentration.top_3_concentration.toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <label>Concentration Risk:</label>
                            <span class="risk-${concentration.concentration_risk.toLowerCase()}">${concentration.concentration_risk}</span>
                        </div>
                    </div>
                </div>
                
                <div class="analysis-card">
                    <h3>🏆 Performance Metrics</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <label>Sharpe Ratio:</label>
                            <span>${performance.sharpe_ratio}</span>
                        </div>
                        <div class="metric">
                            <label>Sortino Ratio:</label>
                            <span>${performance.sortino_ratio}</span>
                        </div>
                        <div class="metric">
                            <label>Performance Ranking:</label>
                            <span class="ranking-${performance.performance_ranking.toLowerCase()}">${performance.performance_ranking}</span>
                        </div>
                    </div>
                </div>
                
                ${recommendations.length > 0 ? `
                <div class="analysis-card recommendations-card">
                    <h3>💡 Recommendations</h3>
                    <div class="recommendations-list">
                        ${recommendations.map(rec => `
                            <div class="recommendation priority-${rec.priority.toLowerCase()}">
                                <div class="rec-header">
                                    <span class="rec-type">${rec.type}</span>
                                    <span class="rec-priority">${rec.priority} Priority</span>
                                </div>
                                <p class="rec-text">${rec.recommendation}</p>
                                <p class="rec-action"><strong>Action:</strong> ${rec.action}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        </div>
    `;
    
    // Add to page
    const container = document.querySelector('.container');
    if (container) {
        container.appendChild(analysisDiv);
        
        // Scroll to analysis
        analysisDiv.scrollIntoView({ behavior: 'smooth' });
    }
}

// Initialize statistical analysis button on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the button as disabled
    setTimeout(() => {
        showStatisticalAnalysisButton(false);
    }, 1000);
});

// Update currency conversion info display
function updateCurrencyInfo(currencyInfo) {
    // Remove existing currency info
    const existingInfo = document.getElementById('currencyInfo');
    if (existingInfo) {
        existingInfo.remove();
    }
    
    // Create currency info section
    const conversions = currencyInfo.conversions;
    if (Object.keys(conversions).length === 0) return;
    
    const summaryCards = document.querySelector('.summary-cards');
    const currencyInfoDiv = document.createElement('div');
    currencyInfoDiv.id = 'currencyInfo';
    currencyInfoDiv.className = 'currency-info';
    
    const conversionsList = Object.entries(conversions)
        .map(([currency, info]) => `<span class="conversion-item">${currency}: ${info.rate} USD</span>`)
        .join('');
    
    currencyInfoDiv.innerHTML = `
        <div class="currency-header">
            <span class="currency-icon">💱</span>
            <span>Exchange Rates (to USD)</span>
        </div>
        <div class="conversions-list">${conversionsList}</div>
        <div class="currency-note">${currencyInfo.conversion_note}</div>
    `;
    
    summaryCards.insertAdjacentElement('afterend', currencyInfoDiv);
}

async function generateMLRecommendations() {
    console.log('Statistical ML Recommendations button clicked!');
    
    // Show loading state
    const button = event.target;
    const originalText = button.textContent;
    button.textContent = 'Loading Statistical Analysis...';
    button.disabled = true;
    
    // Remove previous analysis info
    const existingInfo = document.querySelector('.ml-features-info');
    if (existingInfo) {
        existingInfo.remove();
    }
    
    // Update info section
    const infoDiv = document.getElementById('recommendationInfo');
    if (infoDiv) {
        infoDiv.innerHTML = `
            <strong>📊 Statistical ML Analysis</strong> - Using portfolio performance data, smart statistical modeling, and ticker-specific intelligence. Fast and reliable without external data dependencies.
        `;
        infoDiv.style.borderColor = '#4f46e5';
        infoDiv.style.background = 'rgba(79, 70, 229, 0.1)';
    }
    
    try {
        console.log('Fetching statistical ML recommendations from:', `${API_BASE}/ml-recommendations`);
        const response = await authenticatedFetch(`${API_BASE}/ml-recommendations`);
        if (!response || !response.ok) return;
        const data = await response.json();
        // ML recommendations loaded
        
        displayMLRecommendations(data.recommendations);
        
        // Show statistical features used
        if (data.features) {
            const featuresHTML = data.features.map(f => `<li>${f}</li>`).join('');
            const featuresDiv = document.createElement('div');
            featuresDiv.className = 'ml-features-info';
            featuresDiv.style.borderColor = '#4f46e5';
            featuresDiv.innerHTML = `
                <h3>📊 Statistical ML Features Used:</h3>
                <ul>${featuresHTML}</ul>
                <p style="color: #4f46e5; font-size: 0.9em; margin-top: 10px;">
                    <strong>Data Sources:</strong> Portfolio performance, statistical models, ticker profiles, and smart estimations. No external API dependencies.
                </p>
            `;
            document.querySelector('.recommendations').insertAdjacentElement('afterbegin', featuresDiv);
        }
        
        console.log('Statistical ML recommendations displayed successfully');
    } catch (error) {
        console.error('Error generating statistical ML recommendations:', error);
        alert('Error generating statistical ML recommendations: ' + error.message);
    } finally {
        // Restore button state
        button.textContent = originalText;
        button.disabled = false;
    }
}

// Generate ML recommendations with live market data
async function generateLiveMLRecommendations(event) {
    if (!event) event = { target: document.getElementById('liveMLRecommendationsBtn') };
    const button = event.target;
    const originalText = button.textContent;
    button.textContent = 'Loading Live Data + ML...';
    button.disabled = true;
    
    // Remove previous analysis info
    const existingInfo = document.querySelector('.ml-features-info');
    if (existingInfo) {
        existingInfo.remove();
    }
    
    // Update info section
    const infoDiv = document.getElementById('recommendationInfo');
    if (infoDiv) {
        infoDiv.innerHTML = `
            <strong>🔴 Live Data + ML Analysis</strong> - Using real-time market data, news sentiment, social media trends, and advanced ML models. This may take longer due to data fetching...
        `;
        infoDiv.style.borderColor = '#dc2626';
        infoDiv.style.background = 'rgba(220, 38, 38, 0.1)';
    }
    
    try {
        console.log('Fetching live ML recommendations from:', `${API_BASE}/live-ml-recommendations`);
        const response = await authenticatedFetch(`${API_BASE}/live-ml-recommendations`);
        if (!response || !response.ok) return;
        const data = await response.json();
        // Live ML recommendations loaded
        
        displayMLRecommendations(data.recommendations);
        
        // Show enhanced features used
        if (data.features) {
            const featuresHTML = data.features.map(f => `<li>${f}</li>`).join('');
            const featuresDiv = document.createElement('div');
            featuresDiv.className = 'ml-features-info';
            featuresDiv.style.borderColor = '#dc2626';
            featuresDiv.innerHTML = `
                <h3>🔴 Live Data + ML Features Used:</h3>
                <ul>${featuresHTML}</ul>
                <p style="color: #dc2626; font-size: 0.9em; margin-top: 10px;">
                    <strong>Live Data Sources:</strong> Real-time market data, news sentiment analysis, social media trends, analyst recommendations, and market indicators.
                </p>
            `;
            document.querySelector('.recommendations').insertAdjacentElement('afterbegin', featuresDiv);
        }
        
        console.log('Live ML recommendations displayed successfully');
    } catch (error) {
        console.error('Error generating live ML recommendations:', error);
        alert('Error generating live ML recommendations: ' + error.message);
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}

function displayMLRecommendations(recommendations) {
    const tbody = document.getElementById('recommendationsBody');
    tbody.innerHTML = '';
    
    // Clear any existing ML features info
    const existingInfo = document.querySelector('.ml-features-info');
    if (existingInfo) {
        existingInfo.remove();
    }
    
    recommendations.forEach(rec => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td class="ticker">${rec.ticker}</td>
            <td>$${(rec.current_value || 0).toLocaleString()}</td>
            <td class="${(rec.return_percentage || 0) >= 0 ? 'positive' : 'negative'}">
                ${(rec.return_percentage || 0).toFixed(1)}%
            </td>
            <td>
                <span class="recommendation ${rec.recommendation.toLowerCase()}">
                    ${rec.recommendation}
                </span>
            </td>
            <td class="action">${rec.action}</td>
            <td>
                ${rec.rationale}
                <br><small>Confidence: ${rec.confidence}% | ML Score: ${rec.ml_score}</small>
            </td>
        `;
        
        // Add technical indicators tooltip
        if (rec.technical_indicators) {
            const indicators = Object.entries(rec.technical_indicators)
                .map(([key, value]) => `${key}: ${value}`)
                .join(' | ');
            row.title = indicators;
        }
    });
}
// Toggle add holding form visibility
function toggleAddHoldingForm() {
    const form = document.getElementById('addHoldingForm');
    const btn = document.getElementById('addHoldingBtn');
    
    if (form.style.display === 'none' || form.style.display === '') {
        form.style.display = 'block';
        btn.textContent = 'Cancel';
        // Clear form and initialize
        document.getElementById('holdingForm').reset();
        initializeTransactionForm();
    } else {
        form.style.display = 'none';
        btn.textContent = 'Add New Transaction';
    }
}

// Add new transaction to portfolio
async function addNewHolding() {
    const form = document.getElementById('holdingForm');
    const formData = new FormData(form);
    
    // Convert FormData to transaction format
    const transactionData = {
        trade_date: formData.get('tradeDate'),
        ticker: formData.get('ticker').toUpperCase(),
        exchange: formData.get('exchange'),
        quantity: parseFloat(formData.get('quantity')) || 0,
        price: parseFloat(formData.get('price')) || 0,
        transaction_type: formData.get('transactionType'),
        currency: formData.get('currency') || 'USD',
        amount: parseFloat(formData.get('amount')),
        fees: parseFloat(formData.get('fees')) || 0,
        transaction_method: formData.get('transactionType') // Use transaction type as method
    };
    
    // Validate required fields
    if (!transactionData.ticker || !transactionData.trade_date || !transactionData.transaction_type || !transactionData.amount) {
        alert('Please fill in all required fields (Ticker, Date, Transaction Type, Amount)');
        return;
    }
    
    // Additional validation for BUY/SELL transactions
    if (transactionData.transaction_type !== 'DIVIDEND' && (!transactionData.quantity || !transactionData.price)) {
        alert('For BUY/SELL transactions, Quantity and Price are required');
        return;
    }
    
    try {
        console.log('Adding new transaction:', transactionData);
        
        const response = await authenticatedFetch(`${API_BASE}/add-transaction`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(transactionData)
        });
        
        if (response && response.ok) {
            const result = await response.json();
            console.log('Transaction added successfully:', result);
            
            // Show success message
            alert(`${transactionData.transaction_type} transaction for ${transactionData.ticker} added successfully!`);
            
            // Hide form and reset button
            toggleAddHoldingForm();
            
            // Reload portfolio to show updated holdings
            await loadPortfolio();
            
        } else if (response) {
            const error = await response.json();
            alert('Error adding transaction: ' + (error.error || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error adding holding:', error);
        alert('Error adding holding: ' + error.message);
    }
}

// Delete holding from portfolio
async function deleteHolding(ticker) {
    if (!confirm(`Are you sure you want to delete ${ticker} from your portfolio?`)) {
        return;
    }
    
    try {
        const response = await authenticatedFetch(`${API_BASE}/delete-holding/${ticker}`, {
            method: 'DELETE'
        });
        
        if (response && response.ok) {
            const result = await response.json();
            console.log('Holding deleted:', result);
            alert(`${ticker} removed from portfolio`);
            
            // Reload portfolio
            await loadPortfolio();
        } else if (response) {
            const error = await response.json();
            alert('Error deleting holding: ' + (error.error || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error deleting holding:', error);
        alert('Error deleting holding: ' + error.message);
    }
}

// Clear entire portfolio
async function clearPortfolio() {
    if (!confirm('Are you sure you want to clear the entire portfolio? This will delete all holdings.')) {
        return;
    }
    
    try {
        const response = await authenticatedFetch(`${API_BASE}/clear-portfolio`, {
            method: 'POST'
        });
        
        if (response && response.ok) {
            const result = await response.json();
            console.log('Portfolio cleared:', result);
            alert('Portfolio cleared successfully!');
            
            // Reload portfolio to show empty state
            await loadPortfolio();
        } else if (response) {
            const error = await response.json();
            alert('Error clearing portfolio: ' + (error.error || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error clearing portfolio:', error);
        alert('Error clearing portfolio: ' + error.message);
    }
}

async function showCacheStats() {
    try {
        const response = await fetch(`${API_BASE}/cache-stats`);
        if (response && response.ok) {
            const stats = await response.json();
            
            // Build API sources info
            let apiInfo = '\n🌐 API Sources Status:\n';
            if (stats.api_sources) {
                for (const [key, source] of Object.entries(stats.api_sources)) {
                    const status = source.available ? '🟢' : '🔴';
                    const reliability = (source.reliability * 100).toFixed(1);
                    apiInfo += `${status} ${source.name}: ${reliability}% reliable (${source.usage_count}/${source.rate_limit} calls)\n`;
                }
            }
            
            // Build source usage info
            let usageInfo = '';
            if (stats.source_usage && Object.keys(stats.source_usage).length > 0) {
                usageInfo = '\n📈 24hr Source Usage:\n';
                for (const [source, usage] of Object.entries(stats.source_usage)) {
                    usageInfo += `• ${source}: ${usage.requests_24h} requests\n`;
                }
            }
            
            const message = `
📊 Multi-Source Market Data Statistics:

🗂️ Total Cached Tickers: ${stats.total_cached_tickers}
📈 Average Reliability: ${stats.average_reliability}
🕒 Last Update: ${stats.last_update}
⚡ Recent Updates (1hr): ${stats.recent_updates}
💾 Memory Cache Size: ${stats.memory_cache_size}${apiInfo}${usageInfo}
🚀 System: ${stats.system_version || stats.service_version || 'v2.0'}
📅 Retrieved: ${new Date(stats.timestamp).toLocaleString()}

Multiple APIs ensure 99.9% uptime even when Yahoo Finance fails!
            `;
            
            alert(message);
        } else {
            alert('Could not retrieve cache statistics');
        }
    } catch (error) {
        console.error('Error getting cache stats:', error);
        alert('Error retrieving cache stats: ' + error.message);
    }
}

// Download sample CSV files
function downloadSample(type) {
    const csvContent = type === 'transactions' ? 
        `Trade date,Instrument code,Market code,Quantity,Price,Transaction type,Currency,Amount,Transaction fee,Transaction method
2024-01-15,AAPL,NASDAQ,100,150.00,BUY,USD,15000.00,9.95,BUY
2024-01-20,MSFT,NASDAQ,50,300.00,BUY,USD,15000.00,9.95,BUY
2024-02-10,AAPL,NASDAQ,50,160.00,BUY,USD,8000.00,9.95,BUY
2024-02-15,GOOGL,NASDAQ,25,120.00,BUY,USD,3000.00,9.95,BUY
2024-03-10,AAPL,NASDAQ,25,180.00,SELL,USD,4500.00,9.95,SELL
2024-03-15,MSFT,NASDAQ,10,320.00,SELL,USD,3200.00,9.95,SELL
2024-03-20,AAPL,NASDAQ,0,0.00,DIVIDEND,USD,125.00,0.00,DIVIDEND
2024-03-25,MSFT,NASDAQ,0,0.00,DIVIDEND,USD,80.00,0.00,DIVIDEND
2024-04-01,GOOGL,NASDAQ,0,0.00,DIVIDEND,USD,25.00,0.00,DIVIDEND
2024-04-10,TSLA,NASDAQ,30,200.00,BUY,USD,6000.00,9.95,BUY
2024-04-15,NVDA,NASDAQ,20,450.00,BUY,USD,9000.00,9.95,BUY
2024-05-01,TSLA,NASDAQ,10,220.00,SELL,USD,2200.00,9.95,SELL` :
        `Investment ticker symbol,Exchange,Currency,Starting investment dollar value,Ending investment dollar value,Starting share price,Ending share price,Dividends and distributions,Transaction fees
AAPL,NASDAQ,USD,15000.00,18000.00,150.00,180.00,125.00,19.90
MSFT,NASDAQ,USD,12000.00,13500.00,300.00,337.50,80.00,19.90
GOOGL,NASDAQ,USD,3000.00,3500.00,120.00,140.00,25.00,9.95
TSLA,NASDAQ,USD,4000.00,4400.00,200.00,220.00,0.00,19.90
NVDA,NASDAQ,USD,9000.00,10800.00,450.00,540.00,0.00,9.95`;

    const filename = type === 'transactions' ? 'sample_transactions.csv' : 'sample_portfolio.csv';
    
    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    // Show success message
    showAlert(`Downloaded ${filename} successfully!`, 'success');
}

// Handle transaction form field visibility
function toggleTransactionFields() {
    const transactionType = document.getElementById('transactionType').value;
    const shareFields = document.getElementById('shareFields');
    const quantityField = document.getElementById('quantity');
    const priceField = document.getElementById('price');
    
    if (transactionType === 'DIVIDEND') {
        // Hide share fields for dividends
        shareFields.style.display = 'none';
        quantityField.required = false;
        priceField.required = false;
        quantityField.value = '0';
        priceField.value = '0';
    } else {
        // Show share fields for BUY/SELL
        shareFields.style.display = 'flex';
        quantityField.required = true;
        priceField.required = true;
    }
}

// Set default date to today
function initializeTransactionForm() {
    const dateField = document.getElementById('tradeDate');
    if (dateField) {
        const today = new Date().toISOString().split('T')[0];
        dateField.value = today;
    }
    toggleTransactionFields(); // Initialize field visibility
}

// Make functions globally available
window.fetchMarketData = fetchMarketData;
window.exportData = exportData;
window.generateMLRecommendations = generateMLRecommendations;
window.generateLiveMLRecommendations = generateLiveMLRecommendations;
window.toggleAddHoldingForm = toggleAddHoldingForm;
window.addNewHolding = addNewHolding;
window.deleteHolding = deleteHolding;
window.downloadSample = downloadSample;
window.clearPortfolio = clearPortfolio;
window.showCacheStats = showCacheStats;
window.toggleTransactionFields = toggleTransactionFields;