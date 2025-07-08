// /static/js/auth.js
import { api } from './api.js';

export async function protectPage() {
    try {
        await api.getCurrentUser();
        await updateNavWithUserInfo();
    } catch (error) {
        console.error("Auth check failed, redirecting to login.");
        window.location.href = '/auth/login.html';
    }
}

export async function updateNavWithUserInfo() {
    try {
        const user = await api.getCurrentUser();
        const userNameElement = document.getElementById('userDisplayName');
        const userProfileImage = document.getElementById('userProfileImage');

        if (user && userNameElement) {
            userNameElement.textContent = user.full_name || user.email;
            if(user.picture && userProfileImage) {
                userProfileImage.src = user.picture;
            } else if (userProfileImage) {
                userProfileImage.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.full_name || user.email)}&background=0D6EFD&color=fff`;
            }

            const logoutBtn = document.querySelector('[onclick="handleLogout()"]');
            if (logoutBtn) {
                logoutBtn.addEventListener('click', () => api.logout());
            }
        }
    } catch (error) {
        console.error("Could not update user info in nav.");
        // Don't redirect here - let protectPage handle it
    }
}

window.handleLogout = () => {
    api.logout();
};