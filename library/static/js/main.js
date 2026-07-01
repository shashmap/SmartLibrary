document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Sidebar Toggle
    const sidebarToggle = document.getElementById('sidebar_toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('show');
        });
        
        // Close sidebar if clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth < 992 && sidebar.classList.contains('show') && !sidebar.contains(e.target)) {
                sidebar.classList.remove('show');
            }
        });
    }

    // 2. Autocomplete & Recent Searches Engine
    const searchInput = document.getElementById('navbar_search');
    
    if (searchInput) {
        // Create dropdown container dynamically if not present
        let dropdown = document.querySelector('.autocomplete-dropdown');
        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.className = 'autocomplete-dropdown';
            searchInput.parentNode.appendChild(dropdown);
        }

        // Helper to load recent searches from LocalStorage
        const getRecentSearches = () => {
            try {
                return JSON.parse(localStorage.getItem('library_recent_searches')) || [];
            } catch (e) {
                return [];
            }
        };

        // Helper to add a search term to LocalStorage
        const addRecentSearch = (term) => {
            if (!term || term.trim() === '') return;
            term = term.trim();
            let searches = getRecentSearches();
            searches = searches.filter(s => s.toLowerCase() !== term.toLowerCase());
            searches.unshift(term);
            searches = searches.slice(0, 5); // Keep last 5
            localStorage.setItem('library_recent_searches', JSON.stringify(searches));
        };

        // Show recent searches when search input is focused and empty
        const showRecentSearches = () => {
            const searches = getRecentSearches();
            if (searches.length === 0) {
                dropdown.style.display = 'none';
                return;
            }

            dropdown.innerHTML = `
                <div class="px-3 py-2 text-muted fw-bold border-bottom" style="font-size: 0.75rem;">RECENT SEARCHES</div>
            `;
            
            searches.forEach(term => {
                const item = document.createElement('div');
                item.className = 'autocomplete-item';
                item.innerHTML = `
                    <div class="type-icon"><i class="bi bi-clock-history"></i></div>
                    <div class="item-details">
                        <div class="item-title">${term}</div>
                    </div>
                `;
                item.addEventListener('click', () => {
                    searchInput.value = term;
                    addRecentSearch(term);
                    window.location.href = `/books/?q=${encodeURIComponent(term)}`;
                });
                dropdown.appendChild(item);
            });
            dropdown.style.display = 'block';
        };

        // Event listener for focus
        searchInput.addEventListener('focus', () => {
            if (searchInput.value.trim() === '') {
                showRecentSearches();
            }
        });

        // Event listener for keyboard typing
        let debounceTimer;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            const query = searchInput.value.trim();
            
            if (query === '') {
                showRecentSearches();
                return;
            }

            debounceTimer = setTimeout(() => {
                fetch(`/api/search/suggestions/?q=${encodeURIComponent(query)}`)
                    .rel = 'stylesheet'
                    .then(response => response.json())
                    .then(data => {
                        dropdown.innerHTML = '';
                        const suggestions = data.suggestions;
                        
                        if (suggestions.length === 0) {
                            dropdown.innerHTML = `<div class="p-3 text-muted text-center" style="font-size: 0.85rem;">No results found</div>`;
                            return;
                        }

                        // Header
                        const header = document.createElement('div');
                        header.className = 'px-3 py-2 text-muted fw-bold border-bottom';
                        header.style.fontSize = '0.75rem';
                        header.innerText = 'SEARCH SUGGESTIONS';
                        dropdown.appendChild(header);

                        suggestions.forEach(item => {
                            const row = document.createElement('div');
                            row.className = 'autocomplete-item';
                            
                            const icon = item.type === 'category' ? 'bi-tags' : 'bi-book';
                            const meta = item.type === 'category' ? 'Category' : `Book by ${item.author}`;
                            
                            row.innerHTML = `
                                <div class="type-icon"><i class="bi ${icon}"></i></div>
                                <div class="item-details">
                                    <div class="item-title">${item.text}</div>
                                    <div class="item-meta">${meta}</div>
                                </div>
                            `;
                            
                            row.addEventListener('click', () => {
                                addRecentSearch(item.type === 'title' ? item.text : query);
                                window.location.href = item.url;
                            });
                            dropdown.appendChild(row);
                        });
                        dropdown.style.display = 'block';
                    });
            }, 250); // 250ms debounce
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });

        // Add to recent searches when submitting search form
        const searchForm = searchInput.closest('form');
        if (searchForm) {
            searchForm.addEventListener('submit', () => {
                addRecentSearch(searchInput.value);
            });
        }
    }

    // 3. Auto-Dismiss Alerts (Django Messages)
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            // Check if bootstrap Alert is available and trigger close
            if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                // Vanilla fallback
                alert.style.transition = 'opacity 0.5s ease';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            }
        }, 5000); // 5 seconds
    });
});
