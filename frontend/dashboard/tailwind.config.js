/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: "#0288d1",
        "primary-dark": "#01579b",
        danger: "#e74c3c",
        warning: "#f39c12",
        success: "#2ecc71",
        "bg-light": "#f0f7ff",
      },
    },
  },
  plugins: [],
};
