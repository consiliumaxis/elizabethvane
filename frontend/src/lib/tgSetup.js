export const initTelegramApp = async () => {
    const tg = window.Telegram?.WebApp;
    
    if (!tg) {
        throw new Error("SDK не найден");
    }

    tg.ready();

    const platform = (tg.platform || "").toLowerCase();
    const isMobile = platform === "android" || platform === "ios";

    tg.expand();

    const canFullscreen =
        typeof tg.requestFullscreen === "function" &&
        (typeof tg.isVersionAtLeast !== "function" || tg.isVersionAtLeast("8.0"));

    if (canFullscreen && isMobile) {
        try {
            await tg.requestFullscreen();
        } catch (e) {
            console.warn("Fullscreen error:", e);
        }
    }

    return tg;
};