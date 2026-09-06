/** @type {import('tailwindcss').Config} */
const defaultTheme = require("tailwindcss/defaultTheme")
module.exports = {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue,mjs}"],
  darkMode: "class", // allows toggling dark mode manually
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Roboto",
          "PingFang SC",       // macOS / iOS 中文
          "Hiragino Sans GB",  // macOS 中文
          "Microsoft YaHei",   // Windows 中文
          "Noto Sans CJK SC",  // Linux 中文
          "sans-serif",
          ...defaultTheme.fontFamily.sans,
        ],
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
}
