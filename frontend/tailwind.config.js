/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                cricket: {
                    green: "#00ff88",
                    orange: "#ffaa00",
                    dark: "#0a0a0c",
                    card: "#121216",
                }
            }
        },
    },
    plugins: [],
}
