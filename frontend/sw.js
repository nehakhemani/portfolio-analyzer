// Portfolio Analyzer - Service Worker for PWA
// Version: 2.0 - Multi-Source Market Data

const CACHE_NAME = 'portfolio-analyzer-v2.0';
const OFFLINE_URL = '/offline.html';

// Core files to cache for offline functionality
const CORE_FILES = [
  '/',
  '/css/style.css',
  '/js/app.js',
  '/manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@latest/dist/chart.min.js',
  'https://cdn.jsdelivr.net/npm/axios@latest/dist/axios.min.js'
];

// API endpoints that should be cached for offline use
const API_CACHE_PATTERNS = [
  '/api/portfolio',
  '/api/cache-stats',
  '/api/status'
];

// Install event - cache core files
self.addEventListener('install', event => {
  console.log('📦 Service Worker installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 Caching core files');
        return cache.addAll(CORE_FILES);
      })
      .then(() => {
        console.log('✅ Service Worker installed');
        // Force activation of new service worker
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('❌ Service Worker install failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('🚀 Service Worker activating...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames
            .filter(cacheName => cacheName !== CACHE_NAME)
            .map(cacheName => {
              console.log('🗑️ Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            })
        );
      })
      .then(() => {
        console.log('✅ Service Worker activated');
        // Take control of all pages immediately
        return self.clients.claim();
      })
      .catch(error => {
        console.error('❌ Service Worker activation failed:', error);
      })
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Handle different types of requests
  if (request.method === 'GET') {
    if (url.pathname.startsWith('/api/')) {
      // API requests - cache-first for portfolio data, network-first for market data
      event.respondWith(handleApiRequest(request));
    } else if (request.destination === 'document') {
      // HTML pages - network-first with offline fallback
      event.respondWith(handleDocumentRequest(request));
    } else {
      // Static assets - cache-first
      event.respondWith(handleStaticRequest(request));
    }
  }
});

// Handle API requests with smart caching
async function handleApiRequest(request) {
  const url = new URL(request.url);
  const pathname = url.pathname;
  
  try {
    // For market data, always try network first (real-time data)
    if (pathname.includes('market-data') || pathname.includes('live-')) {
      return await networkFirst(request);
    }
    
    // For portfolio and cache stats, try cache first (faster loading)
    if (pathname.includes('portfolio') || pathname.includes('cache-stats') || pathname.includes('status')) {
      return await cacheFirst(request);
    }
    
    // Default: network-first for other API calls
    return await networkFirst(request);
    
  } catch (error) {
    console.log('📱 API request failed, serving offline message:', pathname);
    return new Response(
      JSON.stringify({
        error: 'Offline mode - please check your connection',
        cached: true,
        timestamp: new Date().toISOString()
      }),
      { 
        headers: { 'Content-Type': 'application/json' },
        status: 503
      }
    );
  }
}

// Handle document requests
async function handleDocumentRequest(request) {
  try {
    // Try network first for fresh content
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
    
  } catch (error) {
    console.log('📱 Document request failed, serving from cache:', request.url);
    
    // Try to serve from cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Serve root page as fallback for SPA routes
    const rootResponse = await caches.match('/');
    if (rootResponse) {
      return rootResponse;
    }
    
    // Last resort: basic offline page
    return new Response(`
      <!DOCTYPE html>
      <html>
      <head>
          <title>Portfolio Analyzer - Offline</title>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
              body { 
                  font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                  color: white; 
                  text-align: center; 
                  padding: 2rem; 
                  min-height: 100vh;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  flex-direction: column;
              }
              .container { max-width: 400px; }
              h1 { color: #667eea; margin-bottom: 1rem; }
              .icon { font-size: 4rem; margin-bottom: 2rem; }
              button { 
                  background: linear-gradient(135deg, #667eea, #4c63d2); 
                  color: white; 
                  border: none; 
                  padding: 1rem 2rem; 
                  border-radius: 8px; 
                  font-size: 1rem;
                  cursor: pointer;
                  margin-top: 2rem;
              }
              button:hover { transform: translateY(-2px); }
          </style>
      </head>
      <body>
          <div class="container">
              <div class="icon">📊</div>
              <h1>Portfolio Analyzer</h1>
              <p>You're currently offline. Please check your internet connection to access live market data.</p>
              <p>Some cached data may still be available.</p>
              <button onclick="window.location.reload()">Try Again</button>
          </div>
      </body>
      </html>
    `, { 
      headers: { 'Content-Type': 'text/html' }
    });
  }
}

// Handle static asset requests
async function handleStaticRequest(request) {
  try {
    return await cacheFirst(request);
  } catch (error) {
    console.log('📱 Static request failed:', request.url);
    throw error;
  }
}

// Cache-first strategy
async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    console.log('💾 Serving from cache:', request.url);
    
    // Update cache in background for next time
    fetch(request)
      .then(response => {
        if (response.ok) {
          const cache = caches.open(CACHE_NAME);
          cache.then(c => c.put(request, response.clone()));
        }
      })
      .catch(() => {/* Ignore background update failures */});
    
    return cachedResponse;
  }
  
  // Not in cache, fetch from network
  const networkResponse = await fetch(request);
  
  if (networkResponse.ok) {
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, networkResponse.clone());
  }
  
  return networkResponse;
}

// Network-first strategy
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
    
  } catch (error) {
    console.log('🌐 Network failed, trying cache:', request.url);
    
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('💾 Serving stale from cache:', request.url);
      return cachedResponse;
    }
    
    throw error;
  }
}

// Handle background sync for offline actions
self.addEventListener('sync', event => {
  console.log('🔄 Background sync triggered:', event.tag);
  
  if (event.tag === 'portfolio-sync') {
    event.waitUntil(syncPortfolioData());
  }
});

// Sync portfolio data when back online
async function syncPortfolioData() {
  try {
    // Get any queued offline actions
    const cache = await caches.open(CACHE_NAME);
    const offlineActions = await cache.match('/offline-actions');
    
    if (offlineActions) {
      const actions = await offlineActions.json();
      console.log('📤 Syncing offline actions:', actions.length);
      
      // Process each action
      for (const action of actions) {
        try {
          await fetch(action.url, action.options);
          console.log('✅ Synced:', action.type);
        } catch (error) {
          console.error('❌ Sync failed:', action.type, error);
        }
      }
      
      // Clear processed actions
      await cache.delete('/offline-actions');
    }
    
  } catch (error) {
    console.error('❌ Background sync failed:', error);
  }
}

// Push notification event
self.addEventListener('push', event => {
  if (!event.data) return;
  
  const data = event.data.json();
  const options = {
    body: data.body || 'Portfolio update available',
    icon: '/icon-192.png',
    badge: '/badge-72.png',
    tag: 'portfolio-update',
    vibrate: [200, 100, 200],
    actions: [
      {
        action: 'view',
        title: 'View Portfolio'
      },
      {
        action: 'dismiss',
        title: 'Dismiss'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title || 'Portfolio Analyzer', options)
  );
});

// Notification click event
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  if (event.action === 'view') {
    event.waitUntil(
      self.clients.openWindow('/')
    );
  }
});

console.log('🚀 Portfolio Analyzer Service Worker loaded - Multi-Source v2.0');