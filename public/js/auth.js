class AuthManager {
    constructor() {
        this.currentUser = null;
        this.authToken = localStorage.getItem('authToken');
        this.isInitialized = false;
        this.init();
    }
    
    async init() {
        await this.loadUser();
        this.isInitialized = true;
        this.runPageProtection();
    }
    
    async loadUser() {
        if (this.authToken) {
            try {
                const response = await fetch('/api/user', {
                    headers: { 'Authorization': this.authToken }
                });
                if (response.ok) {
                    this.currentUser = await response.json();
                } else {
                    this.clearAuth();
                }
            } catch (error) {
                console.error('Failed to load user:', error);
                this.clearAuth();
            }
        }
    }
    
    async login(username, password) {
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            if (response.ok) {
                const data = await response.json();
                this.authToken = data.token;
                this.currentUser = data.user;
                localStorage.setItem('authToken', this.authToken);
                return { success: true, user: data.user };
            } else {
                const error = await response.json();
                return { success: false, error: error.error };
            }
        } catch (error) {
            return { success: false, error: 'Network error' };
        }
    }
    
    async logout() {
        console.log('Logout initiated');
        try {
            console.log('Calling server logout endpoint');
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: this.getAuthHeader()
            });
            console.log('Server response:', response.status, await response.text());
        } catch (error) {
            console.error('Logout API call failed:', error);
        } finally {
            console.log('Clearing client auth');
            this.clearAuth();
            window.location.href = '/login.html';
        }
    }
    
    clearAuth() {
        this.currentUser = null;
        this.authToken = null;
        localStorage.removeItem('authToken');
    }
    
    isLoggedIn() {
        return this.currentUser !== null;
    }
    
    isAdmin() {
        return this.currentUser && this.currentUser.role === 'admin';
    }
    
    getAuthHeader() {
        return this.authToken ? { 'Authorization': this.authToken } : {};
    }
    
    runPageProtection() {
        if (window.location.pathname.includes('login.html')) {
            return;
        }
        if (window.location.pathname.includes('admin') || 
            window.location.pathname.includes('edit') ||
            window.location.pathname.includes('team_summary') ||
            window.location.pathname.includes('rankings')){
            this.protectAdminPages();
        }
        this.updateUIForAuth();
    }
    
    protectAdminPages() {
        if (!this.isLoggedIn()) {
            const currentPath = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.href = `/login.html?redirect=${currentPath}`;
            return;
        }
        if (!this.isAdmin()) {
            document.querySelectorAll('.admin-only').forEach(el => {
                el.style.display = 'none';
            });
            if (window.location.pathname.includes('admin') || 
                window.location.pathname.includes('edit')) {
                document.body.innerHTML = `
                    <div class="container">
                        <h2>Access Denied</h2>
                        <p>You need administrator privileges to access this page.</p>
                        <a href="/">Return to Home</a>
                    </div>
                `;
            }
        }
    }
    
    updateUIForAuth() {
        const adminNavItems = document.querySelectorAll('a[href*="edit"], a[href*="admin"]');
        if (this.isLoggedIn()) {
            if (this.isAdmin()) {
                adminNavItems.forEach(item => {
                    item.style.display = '';
                });
            } else {
                adminNavItems.forEach(item => {
                    item.style.display = 'none';
                });
            }
            this.addLogoutButton();
        } else {
            adminNavItems.forEach(item => {
                item.style.display = 'none';
            });
        }
    }
    
    addLogoutButton() {
        const existingButtons = document.querySelectorAll('#logout-btn, #logout-btn-mobile, #logout-btn-desktop');
        existingButtons.forEach(btn => btn.remove());
        const logoutBtn = document.createElement('button');
        logoutBtn.id = 'logout-btn';
        logoutBtn.className = 'btn btn-red';
        logoutBtn.textContent = `Logout (${this.currentUser.username})`;
        logoutBtn.setAttribute('data-action', 'logout');
        const mobileMenu = document.getElementById('mobileMenu');
        if (mobileMenu) {
            const logoutMobile = logoutBtn.cloneNode(true);
            logoutMobile.id = 'logout-btn-mobile';
            mobileMenu.appendChild(logoutMobile);
        }
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            const logoutDesktop = logoutBtn.cloneNode(true);
            logoutDesktop.id = 'logout-btn-desktop';
            navbar.appendChild(logoutDesktop);
        }
        this.setupLogoutEventListener();
    }
    
    setupLogoutEventListener() {
        document.removeEventListener('click', this.logoutEventHandler);
        this.logoutEventHandler = (event) => {
            if (event.target.matches('[data-action="logout"]') || 
                event.target.closest('[data-action="logout"]')) {
                this.logout();
                event.preventDefault();
            }
        };
        document.addEventListener('click', this.logoutEventHandler);
    }
}

if (!window.auth) {
    window.auth = new AuthManager();
} else {
    auth.runPageProtection();
}