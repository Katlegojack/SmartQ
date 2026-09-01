import { getCurrentAccount, routeForRole } from "../auth/session.js";

export async function bootstrapHome() {
    const accountLinks = document.querySelectorAll("[data-account-link]");
    if (!accountLinks.length) return;

    try {
        const user = await getCurrentAccount();
        if (!user) return;

        const workspace = routeForRole(user.role);
        for (const link of accountLinks) {
            link.href = workspace;
            link.textContent = "Open workspace";
        }

        const status = document.querySelector("[data-home-session]");
        if (status) {
            status.textContent = `Signed in as ${user.username}`;
        }
    } catch (error) {
        console.error("Smart Q session check failed", error);
    }
}
